from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from backend import main
from backend.database import Base, get_db
from backend.models import ActivityEvent, Membership, User
from backend.manage import import_records


@pytest.fixture
def client(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    def test_db():
        with Session(engine, expire_on_commit=False) as db:
            yield db

    original = main.engine
    main.engine = engine
    main.app.dependency_overrides[get_db] = test_db
    with TestClient(main.app) as client:
        client.engine = engine
        yield client
    main.app.dependency_overrides.clear()
    main.engine = original
    engine.dispose()


def signup(client, number):
    response = client.post(
        "/api/auth/signup",
        json={
            "email": f"student{number}@example.org",
            "display_name": f"Student {number}",
            "password": "password123",
        },
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def create_opportunity(client, headers, category="hackathon"):
    response = client.post(
        "/api/opportunities",
        headers=headers,
        json={
            "title": "Campus activity",
            "description": "Join us",
            "category": category,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.mark.parametrize(
    "category", ["hackathon", "course_project", "study_group", "trek_sport"]
)
def test_complete_journey_for_each_category(client, category):
    owner, student = signup(client, 1), signup(client, 2)
    profile = {
        "display_name": "Student 2",
        "skills": {"Python": 4},
        "availability": ["evening"],
        "courses": ["CS101"],
        "experience": ["hiking"],
        "contact": "private@example.org",
    }
    assert client.put("/api/profile", headers=student, json=profile).status_code == 200
    opportunity_id = create_opportunity(client, owner, category)
    assert (
        client.post(
            f"/api/opportunities/{opportunity_id}/interest", headers=student
        ).status_code
        == 200
    )
    team = client.post(
        f"/api/opportunities/{opportunity_id}/teams",
        headers=owner,
        json={
            "name": "Team A",
            "capacity": 2,
            "skills": {"Python": 4},
            "availability": ["evening"],
            "course": "CS101",
            "experience": ["hiking"],
            "group_link": "https://example.org/group",
        },
    ).json()
    recommendations = client.get(
        f"/api/opportunities/{opportunity_id}/recommendations", headers=student
    ).json()
    assert recommendations[0]["id"] == team["id"]
    assert recommendations[0]["explanation"]
    assert (
        "group_link"
        not in client.get(f"/api/teams/{team['id']}", headers=student).json()
    )
    assert (
        client.get(f"/api/teams/{team['id']}/messages", headers=student).status_code
        == 403
    )
    request = client.post(f"/api/teams/{team['id']}/requests", headers=student).json()
    reviewed = client.get(f"/api/teams/{team['id']}/requests", headers=owner).json()
    assert reviewed[0]["match"]["explanation"]
    assert (
        client.post(f"/api/requests/{request['id']}/approve", headers=owner).json()[
            "status"
        ]
        == "approved"
    )
    member_view = client.get(f"/api/teams/{team['id']}", headers=owner).json()
    assert member_view["member_count"] == 2
    assert any(
        person["contact"] == "private@example.org" for person in member_view["members"]
    )
    assert (
        client.post(
            f"/api/teams/{team['id']}/messages",
            headers=student,
            json={"text": "Hello team"},
        ).status_code
        == 201
    )
    assert (
        client.get(f"/api/teams/{team['id']}/messages", headers=owner).json()[0]["text"]
        == "Hello team"
    )


def test_duplicates_and_open_signup(client):
    headers = signup(client, 1)
    item = {
        "title": "AI challenge",
        "description": "Details",
        "category": "hackathon",
        "official_url": "https://EXAMPLE.org/event/",
    }
    assert (
        client.post("/api/opportunities", headers=headers, json=item).status_code == 201
    )
    assert (
        client.post(
            "/api/opportunities",
            headers=headers,
            json={**item, "official_url": "https://example.org/event"},
        ).status_code
        == 409
    )
    response = client.post(
        "/api/opportunities", headers=headers, json={**item, "official_url": None}
    )
    assert response.status_code == 409
    assert (
        client.post(
            "/api/opportunities",
            headers=headers,
            json={**item, "official_url": None, "confirm_similar": True},
        ).status_code
        == 201
    )
    assert (
        client.get("/api/opportunities?category=hackathon&source=student").status_code
        == 200
    )


def test_login_and_authorization(client):
    headers = signup(client, 1)
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "student1@example.org", "password": "wrong"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "student1@example.org", "password": "password123"},
        ).status_code
        == 200
    )
    assert client.get("/api/admin/reports", headers=headers).status_code == 403
    assert client.post("/api/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/profile", headers=headers).status_code == 401


def test_ten_simultaneous_approvals_cannot_overfill(client):
    owner = signup(client, 0)
    opportunity_id = create_opportunity(client, owner)
    team_id = client.post(
        f"/api/opportunities/{opportunity_id}/teams",
        headers=owner,
        json={"name": "Team", "capacity": 4},
    ).json()["id"]
    requests = []
    for number in range(1, 11):
        headers = signup(client, number)
        response = client.post(f"/api/teams/{team_id}/requests", headers=headers)
        requests.append(response.json()["id"])
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(
            pool.map(
                lambda request_id: client.post(
                    f"/api/requests/{request_id}/approve", headers=owner
                ),
                requests,
            )
        )
    assert sum(response.status_code == 200 for response in results) == 3
    with Session(client.engine) as db:
        assert (
            len(
                db.scalars(
                    select(Membership).where(Membership.team_id == team_id)
                ).all()
            )
            == 4
        )


def test_admin_hides_and_suspends(client):
    admin, target = signup(client, 1), signup(client, 2)
    with Session(client.engine) as db:
        person = db.scalar(select(User).where(User.email == "student1@example.org"))
        person.is_admin = True
        db.commit()
    opportunity_id = create_opportunity(client, target)
    report = client.post(
        "/api/reports",
        headers=target,
        json={
            "target_type": "opportunity",
            "target_id": opportunity_id,
            "reason": "Incorrect",
        },
    )
    assert report.status_code == 201
    assert len(client.get("/api/admin/reports", headers=admin).json()) == 1
    assert (
        client.post(
            f"/api/admin/hide-opportunity/{opportunity_id}", headers=admin
        ).status_code
        == 200
    )
    assert client.get(f"/api/opportunities/{opportunity_id}").status_code == 404
    assert client.post("/api/admin/suspend-user/2", headers=admin).status_code == 200
    assert client.get("/api/profile", headers=target).status_code == 401
    with Session(client.engine) as db:
        assert (
            db.scalar(select(ActivityEvent).where(ActivityEvent.name == "signup"))
            is not None
        )


def test_date_and_required_availability_exclude_ineligible_candidates(client):
    owner, student = signup(client, 1), signup(client, 2)
    response = client.post(
        "/api/opportunities",
        headers=owner,
        json={
            "title": "Dated event",
            "description": "Details",
            "category": "study_group",
            "event_date": "2026-11-28",
        },
    )
    opportunity_id = response.json()["id"]
    team = client.post(
        f"/api/opportunities/{opportunity_id}/teams",
        headers=owner,
        json={
            "name": "Evening group",
            "capacity": 3,
            "availability": ["evening"],
            "availability_required": True,
        },
    ).json()
    assert (
        client.get(
            f"/api/opportunities/{opportunity_id}/recommendations", headers=student
        ).json()
        == []
    )
    assert (
        client.post(f"/api/teams/{team['id']}/requests", headers=student).status_code
        == 409
    )
    assert (
        client.put(
            "/api/profile",
            headers=student,
            json={
                "display_name": "Student",
                "available_dates": ["2026-11-28"],
                "availability": ["evening"],
            },
        ).status_code
        == 200
    )
    assert (
        len(
            client.get(
                f"/api/opportunities/{opportunity_id}/recommendations", headers=student
            ).json()
        )
        == 1
    )


def test_same_user_cannot_join_two_teams_on_concurrent_approval(client):
    owner1, owner2, student = signup(client, 1), signup(client, 2), signup(client, 3)
    opportunity_id = create_opportunity(client, owner1)
    team1 = client.post(
        f"/api/opportunities/{opportunity_id}/teams",
        headers=owner1,
        json={"name": "First", "capacity": 3},
    ).json()["id"]
    team2 = client.post(
        f"/api/opportunities/{opportunity_id}/teams",
        headers=owner2,
        json={"name": "Second", "capacity": 3},
    ).json()["id"]
    request1 = client.post(f"/api/teams/{team1}/requests", headers=student).json()["id"]
    request2 = client.post(f"/api/teams/{team2}/requests", headers=student).json()["id"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                client.post, f"/api/requests/{request1}/approve", headers=owner1
            ),
            pool.submit(
                client.post, f"/api/requests/{request2}/approve", headers=owner2
            ),
        ]
        results = [future.result() for future in futures]
    assert sorted(response.status_code for response in results) == [200, 409]
    with Session(client.engine) as db:
        assert (
            len(
                db.scalars(
                    select(Membership).where(
                        Membership.user_id == 3,
                        Membership.opportunity_id == opportunity_id,
                    )
                ).all()
            )
            == 1
        )


def test_import_sources_and_insights(client):
    headers = signup(client, 1)
    with Session(client.engine, expire_on_commit=False) as db:
        creator = db.get(User, 1)
        items = [
            {
                "title": "Curated event",
                "description": "Details",
                "category": "hackathon",
                "official_url": "https://example.org/a",
            },
            {
                "title": "Bad date",
                "description": "Details",
                "category": "hackathon",
                "event_date": "wrong",
            },
        ]
        assert import_records(db, items, "curated", creator) == (1, 1)
        assert import_records(db, items[:1], "scraped", creator) == (0, 1)
        assert import_records(
            db,
            [
                {
                    "title": "RSS event",
                    "description": "Details",
                    "category": "study_group",
                    "official_url": "https://example.org/b",
                }
            ],
            "scraped",
            creator,
        ) == (1, 0)
    assert len(client.get("/api/opportunities?source=curated").json()) == 1
    assert len(client.get("/api/opportunities?source=scraped").json()) == 1
    insights = client.get("/api/insights", headers=headers).json()
    assert insights["team_fill"]["rate"] is None
    assert insights["time_to_join"]["sample_size"] == 0


def test_insights_keep_interest_history_after_withdrawal(client):
    owner, student = signup(client, 1), signup(client, 2)
    opportunity_id = create_opportunity(client, owner)
    assert (
        client.post(
            f"/api/opportunities/{opportunity_id}/interest", headers=student
        ).status_code
        == 200
    )
    assert (
        client.delete(
            f"/api/opportunities/{opportunity_id}/interest", headers=student
        ).status_code
        == 200
    )
    insights = client.get("/api/insights", headers=owner).json()
    assert insights["demand"]["hackathon"] == 1


def test_search_suggestions_and_participation_state(client):
    owner, student = signup(client, 1), signup(client, 2)
    opportunity_id = create_opportunity(client, owner)
    found = client.get(
        "/api/opportunities", params={"q": "campus activty", "suggest": "true"}
    ).json()
    assert any(item["id"] == opportunity_id for item in found)
    assert (
        client.get(f"/api/opportunities/{opportunity_id}/participation").status_code
        == 401
    )
    assert (
        client.post(
            f"/api/opportunities/{opportunity_id}/interest", headers=student
        ).status_code
        == 200
    )
    team_id = client.post(
        f"/api/opportunities/{opportunity_id}/teams",
        headers=owner,
        json={"name": "Team", "capacity": 2},
    ).json()["id"]
    request_id = client.post(f"/api/teams/{team_id}/requests", headers=student).json()[
        "id"
    ]
    participation = client.get(
        f"/api/opportunities/{opportunity_id}/participation", headers=student
    ).json()
    assert participation["looking"] is True
    assert participation["team"] is None
    assert participation["requests"][0]["status"] == "pending"
    assert (
        client.post(f"/api/requests/{request_id}/approve", headers=owner).status_code
        == 200
    )
    participation = client.get(
        f"/api/opportunities/{opportunity_id}/participation", headers=student
    ).json()
    assert participation["looking"] is False
    assert participation["team"]["id"] == team_id
    assert participation["requests"][0]["status"] == "approved"


def test_team_options_report_hidden_and_full_counts(client):
    owner, student = signup(client, 1), signup(client, 2)
    item = client.post(
        "/api/opportunities",
        headers=owner,
        json={
            "title": "Scheduled",
            "description": "Details",
            "category": "study_group",
            "event_date": "2026-11-28",
        },
    ).json()
    team_id = client.post(
        f"/api/opportunities/{item['id']}/teams",
        headers=owner,
        json={
            "name": "Evening",
            "capacity": 2,
            "availability": ["evening"],
            "availability_required": True,
        },
    ).json()["id"]
    options = client.get(
        f"/api/opportunities/{item['id']}/team-options", headers=student
    ).json()
    assert options["teams"] == []
    assert options["hidden_count"] == 1
    assert set(options["hidden_reasons"]) == {"event_date", "availability"}
    assert "Evening" not in str(options)
    client.put(
        "/api/profile",
        headers=student,
        json={
            "display_name": "Student",
            "available_dates": ["2026-11-28"],
            "availability": ["evening"],
        },
    )
    options = client.get(
        f"/api/opportunities/{item['id']}/team-options", headers=student
    ).json()
    assert options["teams"][0]["id"] == team_id
    request_id = client.post(f"/api/teams/{team_id}/requests", headers=student).json()[
        "id"
    ]
    client.post(f"/api/requests/{request_id}/approve", headers=owner)
    options = client.get(
        f"/api/opportunities/{item['id']}/team-options", headers=student
    ).json()
    assert options["already_joined"] is True
    assert options["full_count"] == 1
