from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from backend import main
from backend.database import Base, get_db
from backend.models import Membership


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
    with TestClient(main.app) as test_client:
        test_client.engine = engine
        yield test_client
    main.app.dependency_overrides.clear()
    main.engine = original
    engine.dispose()


def signup(client, number, interests=None, skills=None):
    response = client.post("/api/auth/signup", json={
        "email": f"student{number}@example.org", "display_name": f"Student {number}",
        "password": "password123", "bio": "I enjoy working on campus projects together.",
        "interests": interests or ["hackathon"], "skills": skills or ["Python"],
    })
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def opportunity(client, owner, category="hackathon", schedule=None, **extra):
    response = client.post("/api/opportunities", headers=owner, json={
        "title": f"Campus activity {category}", "description": "Join us",
        "category": category, "skills": ["Python"],
        "schedule": schedule or {"kind": "undecided"}, **extra,
    })
    assert response.status_code == 201, response.text
    return response.json()["id"]


def team(client, owner, activity, capacity=2, schedule=None):
    response = client.post(f"/api/opportunities/{activity}/teams", headers=owner, json={
        "name": "Team A", "capacity": capacity, "skills": ["Python"],
        "goal": "Build something useful", "question": "What can you contribute?",
        "schedule": schedule or {"kind": "undecided"},
    })
    assert response.status_code == 201, response.text
    return response.json()["id"]


def apply(client, student, team_id, dates=None, weekdays=None):
    return client.post(f"/api/teams/{team_id}/requests", headers=student, json={
        "date_answers": {"dates": dates or [], "weekdays": weekdays or []},
        "motivation": "I want to contribute", "question_answer": "Python",
    })


@pytest.mark.parametrize("category", ["hackathon", "course_project", "study_group", "trek_sport"])
def test_full_journey_and_fit_for_each_category(client, category):
    owner = signup(client, 1)
    student = signup(client, 2, interests=[category])
    activity = opportunity(client, owner, category)
    team_id = team(client, owner, activity)
    listings = client.get("/api/opportunities", headers=student).json()
    assert listings[0]["fit"]["band"] in ("Low", "Medium", "High")
    assert listings[0]["fit"]["explanation"]
    assert client.get(f"/api/teams/{team_id}/messages", headers=student).status_code == 403
    pool = client.post(f"/api/opportunities/{activity}/interest", headers=student, json={
        "date_answers": {"dates": [], "weekdays": []}
    })
    assert pool.status_code == 200, pool.text
    request = apply(client, student, team_id)
    assert request.status_code == 201, request.text
    reviewed = client.get(f"/api/teams/{team_id}/requests", headers=owner).json()[0]
    assert reviewed["motivation"] == "I want to contribute"
    assert reviewed["question_answer"] == "Python"
    assert reviewed["match"]["score"] >= 0
    assert reviewed["match"]["breakdown"]
    assert client.get(f"/api/teams/{team_id}/requests", headers=student).status_code == 403
    approved = client.post(f"/api/requests/{request.json()['id']}/approve", headers=owner)
    assert approved.status_code == 200, approved.text
    assert client.get(f"/api/teams/{team_id}/messages", headers=student).status_code == 200
    assert client.post(f"/api/teams/{team_id}/messages", headers=student, json={"text": "Hello"}).status_code == 201
    assert client.get("/api/me/notifications", headers=student).json()["unread_count"] >= 1
    assert client.post(f"/api/teams/{team_id}/leave", headers=student, json={"return_to_pool": True}).status_code == 200
    assert client.get(f"/api/teams/{team_id}/messages", headers=student).status_code == 403
    assert client.get(f"/api/teams/{team_id}", headers=student).json().get("members") is None
    assert client.get(f"/api/opportunities/{activity}/participation", headers=student).json()["looking"]


def test_required_dates_and_invitations(client):
    owner, student = signup(client, 1), signup(client, 2)
    schedule = {"kind": "single", "start_date": "2026-11-21", "required_dates": ["2026-11-21"]}
    activity = opportunity(client, owner, schedule=schedule)
    team_id = team(client, owner, activity, schedule=schedule)
    bad = apply(client, student, team_id, dates=["2026-11-22"])
    assert bad.status_code == 409
    pool = client.post(f"/api/opportunities/{activity}/interest", headers=student, json={
        "date_answers": {"dates": ["2026-11-21"], "weekdays": []}
    })
    assert pool.status_code == 200
    invite = client.post(f"/api/teams/{team_id}/invitations?candidate_id=2", headers=owner)
    assert invite.status_code == 201, invite.text
    accepted = client.post(f"/api/invitations/{invite.json()['id']}/accept", headers=student)
    assert accepted.status_code == 200, accepted.text
    assert client.get(f"/api/teams/{team_id}", headers=student).json()["member_count"] == 2
    notice = client.get("/api/me/notifications", headers=student).json()["items"][0]
    assert client.post(f"/api/me/notifications/{notice['id']}/read", headers=student).status_code == 200


@pytest.mark.parametrize("schedule,answer,expected", [
    ({"kind": "single", "start_date": "2026-11-20", "required_dates": ["2026-11-20"]}, ["2026-11-20"], 201),
    ({"kind": "range", "start_date": "2026-11-20", "end_date": "2026-11-22", "required_dates": ["2026-11-21"]}, ["2026-11-20"], 409),
    ({"kind": "range", "start_date": "2026-11-20", "end_date": "2026-11-22", "required_dates": ["2026-11-21"]}, ["2026-11-21"], 201),
    ({"kind": "recurring", "start_date": "2026-11-16", "end_date": "2026-11-23", "weekdays": [0], "required_weekdays": [0]}, [], 409),
    ({"kind": "undecided"}, [], 201),
])
def test_schedule_rules(client, schedule, answer, expected):
    owner, student = signup(client, 1), signup(client, 2)
    activity = opportunity(client, owner, schedule=schedule)
    team_id = team(client, owner, activity, schedule=schedule)
    response = apply(client, student, team_id, dates=answer)
    assert response.status_code == expected, response.text


def test_remove_transfer_and_close(client):
    owner, student, another = signup(client, 1), signup(client, 2), signup(client, 3)
    activity = opportunity(client, owner)
    team_id = team(client, owner, activity, capacity=3)
    for headers in (student, another):
        request = apply(client, headers, team_id)
        assert request.status_code == 201
        assert client.post(f"/api/requests/{request.json()['id']}/approve", headers=owner).status_code == 200
    removed = client.post(f"/api/teams/{team_id}/remove/2", headers=owner)
    assert removed.status_code == 200, removed.text
    assert apply(client, student, team_id).status_code == 409
    assert client.get(f"/api/teams/{team_id}/messages", headers=student).status_code == 403
    assert client.post(f"/api/teams/{team_id}/transfer", headers=owner, json={"user_id": 3}).status_code == 200
    assert client.post(f"/api/teams/{team_id}/close", headers=another).status_code == 200
    assert client.get(f"/api/teams/{team_id}/messages", headers=another).status_code == 403


def test_concurrent_approvals_keep_capacity(client):
    owner = signup(client, 1)
    activity = opportunity(client, owner)
    team_id = team(client, owner, activity, capacity=4)
    requests = []
    for number in range(2, 12):
        student = signup(client, number)
        requests.append(apply(client, student, team_id).json()["id"])
    with ThreadPoolExecutor(max_workers=10) as executor:
        responses = list(executor.map(
            lambda request_id: client.post(f"/api/requests/{request_id}/approve", headers=owner),
            requests,
        ))
    assert sum(response.status_code == 200 for response in responses) == 3
    with Session(client.engine) as db:
        assert len(db.scalars(select(Membership).where(Membership.team_id == team_id)).all()) == 4


def test_invitation_and_request_compete_for_last_spot(client):
    owner, requester, invitee = signup(client, 1), signup(client, 2), signup(client, 3)
    activity = opportunity(client, owner)
    team_id = team(client, owner, activity)
    request = apply(client, requester, team_id).json()
    client.post(f"/api/opportunities/{activity}/interest", headers=invitee, json={
        "date_answers": {"dates": [], "weekdays": []}
    })
    invite = client.post(f"/api/teams/{team_id}/invitations?candidate_id=3", headers=owner).json()
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda action: action(), [
            lambda: client.post(f"/api/requests/{request['id']}/approve", headers=owner),
            lambda: client.post(f"/api/invitations/{invite['id']}/accept", headers=invitee),
        ]))
    assert sum(response.status_code == 200 for response in responses) == 1
    with Session(client.engine) as db:
        assert len(db.scalars(select(Membership).where(Membership.team_id == team_id)).all()) == 2


def test_duplicate_and_profile_privacy(client):
    owner, student = signup(client, 1), signup(client, 2)
    item = {"title": "AI challenge", "description": "Details", "category": "hackathon", "official_url": "https://example.org/event"}
    activity = client.post("/api/opportunities", headers=owner, json=item)
    assert activity.status_code == 201
    assert client.post("/api/opportunities", headers=owner, json=item).status_code == 409
    assert client.put("/api/profile", headers=student, json={
        "display_name": "Student 2", "bio": "I enjoy working on campus projects together.",
        "skills": ["Python", "Design"], "interests": ["hackathon"],
        "courses": [], "experience": [], "contact": "private@example.org",
    }).status_code == 200
    activity_id = activity.json()["id"]
    team_id = team(client, owner, activity_id)
    apply(client, student, team_id)
    viewed = client.get(f"/api/teams/{team_id}/requests", headers=owner).json()[0]["user"]
    assert "email" not in viewed and "contact" not in viewed
    assert viewed["skills"] == ["Python", "Design"]


def test_incomplete_legacy_profile_has_no_misleading_fit(client):
    owner, student = signup(client, 1), signup(client, 2)
    activity = opportunity(client, owner)
    team_id = team(client, owner, activity)
    with Session(client.engine) as db:
        person = db.get(main.User, 2)
        person.bio = ""
        db.commit()
    item = client.get(f"/api/opportunities/{activity}", headers=student).json()
    assert "fit" not in item
    choices = client.get(f"/api/opportunities/{activity}/team-options", headers=student).json()
    assert choices["teams"][0]["id"] == team_id
    assert "score" not in choices["teams"][0]
