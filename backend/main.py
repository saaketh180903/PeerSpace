"""PeerSpace API. Run with: uvicorn backend.main:app --reload"""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
import os
from urllib.parse import urlsplit, urlunsplit

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .matching import eligibility_reasons, score_match
from .models import (
    ActivityEvent,
    Interest,
    JoinRequest,
    LoginSession,
    Membership,
    ModerationAction,
    Opportunity,
    Report,
    Team,
    TeamMessage,
    User,
)
from .schemas import (
    Login,
    MessageInput,
    OpportunityInput,
    Profile,
    ReportInput,
    Signup,
    TeamInput,
)
from .security import check_password, create_token, hash_password, hash_token


@asynccontextmanager
async def lifespan(_app):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="PeerSpace API", lifespan=lifespan)
allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


def record(db, name, user_id, opportunity_id=None):
    db.add(ActivityEvent(name=name, user_id=user_id, opportunity_id=opportunity_id))


def current_user(
    authorization: str | None = Header(default=None), db: Session = Depends(get_db)
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Please sign in")
    session = db.get(LoginSession, hash_token(authorization[7:]))
    if not session:
        raise HTTPException(401, "Invalid session")
    expires = session.expires_at.replace(tzinfo=timezone.utc)
    user = db.get(User, session.user_id)
    if expires <= datetime.now(timezone.utc) or not user or user.suspended:
        raise HTTPException(401, "Session expired or account unavailable")
    return user


def admin_user(user: User = Depends(current_user)):
    if not user.is_admin:
        raise HTTPException(403, "Administrator access required")
    return user


def public_user(user):
    return {
        "id": user.id,
        "display_name": user.display_name,
        "skills": user.skills,
        "interests": user.interests,
        "availability": user.availability,
        "courses": user.courses,
        "experience": user.experience,
    }


def own_user(user):
    return {
        **public_user(user),
        "email": user.email,
        "contact": user.contact,
        "available_dates": user.available_dates,
        "is_admin": user.is_admin,
    }


def issue_token(db, user):
    token = create_token()
    db.add(
        LoginSession(
            token_hash=hash_token(token),
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
    )
    db.commit()
    return {"token": token, "user": own_user(user)}


def opportunity_or_404(db, opportunity_id):
    opportunity = db.get(Opportunity, opportunity_id)
    if not opportunity or opportunity.hidden:
        raise HTTPException(404, "Opportunity not found")
    return opportunity


def team_or_404(db, team_id):
    team = db.get(Team, team_id)
    if not team:
        raise HTTPException(404, "Team not found")
    opportunity_or_404(db, team.opportunity_id)
    return team


def member_count(db, team_id):
    return db.scalar(
        select(func.count())
        .select_from(Membership)
        .where(Membership.team_id == team_id)
    )


def is_member(db, team_id, user_id):
    return (
        db.scalar(
            select(Membership.id).where(
                Membership.team_id == team_id, Membership.user_id == user_id
            )
        )
        is not None
    )


def team_view(db, team, user=None):
    count = member_count(db, team.id)
    result = {
        "id": team.id,
        "opportunity_id": team.opportunity_id,
        "owner_id": team.owner_id,
        "name": team.name,
        "capacity": team.capacity,
        "member_count": count,
        "skills": team.skills,
        "availability": team.availability,
        "availability_required": team.availability_required,
        "course": team.course,
        "experience": team.experience,
    }
    if user and is_member(db, team.id, user.id):
        members = db.scalars(
            select(User)
            .join(Membership, Membership.user_id == User.id)
            .where(Membership.team_id == team.id)
        ).all()
        result["group_link"] = team.group_link
        result["members"] = [
            {**public_user(person), "contact": person.contact} for person in members
        ]
    return result


def opportunity_view(db, item):
    return {
        "id": item.id,
        "title": item.title,
        "description": item.description,
        "category": item.category,
        "source": item.source,
        "organizer": item.organizer,
        "official_url": item.official_url,
        "event_date": item.event_date,
        "team_count": db.scalar(
            select(func.count()).select_from(Team).where(Team.opportunity_id == item.id)
        ),
        "looking_count": db.scalar(
            select(func.count())
            .select_from(Interest)
            .where(Interest.opportunity_id == item.id, Interest.looking.is_(True))
        ),
    }


def normalize_url(value):
    if not value:
        return None
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        raise HTTPException(422, "Enter a valid http or https URL")
    if (
        parsed.scheme.lower() not in ("http", "https")
        or not parsed.netloc
        or parsed.username
        or parsed.password
    ):
        raise HTTPException(422, "Enter a valid http or https URL")
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            parsed.query,
            "",
        )
    )


def write_lock(db):
    # Authentication performs a read first. End that transaction, then take the
    # SQLite write lock before checking capacity or membership.
    db.rollback()
    db.execute(text("BEGIN IMMEDIATE"))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/auth/signup", status_code=201)
def signup(data: Signup, db: Session = Depends(get_db)):
    if db.scalar(select(User.id).where(User.email == data.email)):
        raise HTTPException(409, "An account already exists for this email")
    user = User(
        email=data.email,
        display_name=data.display_name.strip(),
        password_hash=hash_password(data.password),
    )
    db.add(user)
    try:
        db.flush()
        record(db, "signup", user.id)
        return issue_token(db, user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An account already exists for this email")


@app.post("/api/auth/login")
def login(data: Login, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email.strip().lower()))
    if (
        not user
        or user.suspended
        or not check_password(data.password, user.password_hash)
    ):
        raise HTTPException(401, "Invalid email or password")
    return issue_token(db, user)


@app.post("/api/auth/logout")
def logout(
    authorization: str | None = Header(default=None),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    session = db.get(LoginSession, hash_token(authorization[7:]))
    if session:
        db.delete(session)
        db.commit()
    return {"ok": True}


@app.get("/api/profile")
def get_profile(user: User = Depends(current_user)):
    return own_user(user)


@app.put("/api/profile")
def update_profile(
    data: Profile, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    for key, value in data.model_dump().items():
        setattr(
            user,
            key,
            [day.isoformat() for day in value] if key == "available_dates" else value,
        )
    db.commit()
    return own_user(user)


@app.get("/api/opportunities")
def list_opportunities(
    q: str = "",
    category: str = "",
    source: str = "",
    suggest: bool = False,
    db: Session = Depends(get_db),
):
    query = select(Opportunity).where(Opportunity.hidden.is_(False))
    if q.strip() and not suggest:
        query = query.where(Opportunity.title.ilike(f"%{q.strip()}%"))
    if category:
        query = query.where(Opportunity.category == category)
    if source:
        query = query.where(Opportunity.source == source)
    items = db.scalars(query.order_by(Opportunity.created_at.desc())).all()
    if q.strip() and suggest:
        needle = " ".join(q.lower().split())

        def relevance(item):
            title = " ".join(item.title.lower().split())
            if needle in title:
                return 1.0
            words = needle.split()
            word_match = sum(1 for word in words if word in title) / len(words)
            return max(SequenceMatcher(None, needle, title).ratio(), word_match * 0.9)

        items = [item for item in items if relevance(item) >= 0.45]
        items.sort(key=lambda item: (-relevance(item), item.title.lower(), item.id))
    return [opportunity_view(db, item) for item in items]


@app.post("/api/opportunities", status_code=201)
def create_opportunity(
    data: OpportunityInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    url = normalize_url(data.official_url)
    duplicate = (
        db.scalar(select(Opportunity).where(Opportunity.official_url == url))
        if url
        else None
    )
    if duplicate:
        raise HTTPException(
            409,
            {
                "message": "This official link is already listed",
                "existing_id": duplicate.id,
            },
        )
    event_date = data.event_date.isoformat() if data.event_date else None
    candidates = db.scalars(
        select(Opportunity).where(
            Opportunity.hidden.is_(False), Opportunity.category == data.category
        )
    ).all()
    similar = [
        item
        for item in candidates
        if SequenceMatcher(
            None, item.title.lower().strip(), data.title.lower().strip()
        ).ratio()
        >= 0.8
        and item.event_date == event_date
        and (item.organizer or "").lower() == (data.organizer or "").lower()
    ]
    if similar and not data.confirm_similar:
        raise HTTPException(
            409,
            {
                "message": "Similar opportunities exist",
                "similar": [opportunity_view(db, item) for item in similar],
            },
        )
    item = Opportunity(
        title=data.title.strip(),
        description=data.description.strip(),
        category=data.category,
        source="student",
        organizer=data.organizer,
        official_url=url,
        event_date=event_date,
        created_by=user.id,
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This official link is already listed")
    return opportunity_view(db, item)


@app.get("/api/opportunities/{opportunity_id}")
def get_opportunity(opportunity_id: int, db: Session = Depends(get_db)):
    return opportunity_view(db, opportunity_or_404(db, opportunity_id))


@app.post("/api/opportunities/{opportunity_id}/interest")
def express_interest(
    opportunity_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    user_id = user.id
    write_lock(db)
    opportunity_or_404(db, opportunity_id)
    if db.scalar(
        select(Membership.id).where(
            Membership.opportunity_id == opportunity_id, Membership.user_id == user_id
        )
    ):
        raise HTTPException(409, "You already belong to a team for this opportunity")
    interest = db.scalar(
        select(Interest).where(
            Interest.opportunity_id == opportunity_id, Interest.user_id == user_id
        )
    )
    if not interest:
        interest = Interest(
            opportunity_id=opportunity_id, user_id=user_id, looking=True
        )
        db.add(interest)
        record(db, "interest", user_id, opportunity_id)
    else:
        interest.looking = True
    db.commit()
    return {"looking": True}


@app.delete("/api/opportunities/{opportunity_id}/interest")
def withdraw_interest(
    opportunity_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    interest = db.scalar(
        select(Interest).where(
            Interest.opportunity_id == opportunity_id, Interest.user_id == user.id
        )
    )
    if interest:
        db.delete(interest)
        db.commit()
    return {"looking": False}


@app.get("/api/opportunities/{opportunity_id}/teams")
def list_teams(opportunity_id: int, db: Session = Depends(get_db)):
    opportunity_or_404(db, opportunity_id)
    return [
        team_view(db, team)
        for team in db.scalars(
            select(Team).where(Team.opportunity_id == opportunity_id)
        ).all()
    ]


@app.get("/api/opportunities/{opportunity_id}/participation")
def participation(
    opportunity_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    opportunity_or_404(db, opportunity_id)
    interest = db.scalar(
        select(Interest).where(
            Interest.opportunity_id == opportunity_id, Interest.user_id == user.id
        )
    )
    membership = db.scalar(
        select(Membership).where(
            Membership.opportunity_id == opportunity_id, Membership.user_id == user.id
        )
    )
    requests = db.execute(
        select(JoinRequest, Team)
        .join(Team, Team.id == JoinRequest.team_id)
        .where(Team.opportunity_id == opportunity_id, JoinRequest.user_id == user.id)
    ).all()
    return {
        "looking": bool(interest and interest.looking),
        "team": (
            {"id": membership.team_id, "name": db.get(Team, membership.team_id).name}
            if membership
            else None
        ),
        "requests": [
            {
                "id": request.id,
                "team_id": team.id,
                "team_name": team.name,
                "status": request.status,
            }
            for request, team in requests
        ],
    }


@app.get("/api/opportunities/{opportunity_id}/team-options")
def team_options(
    opportunity_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    opportunity = opportunity_or_404(db, opportunity_id)
    membership = db.scalar(
        select(Membership.id).where(
            Membership.opportunity_id == opportunity_id, Membership.user_id == user.id
        )
    )
    teams = db.scalars(select(Team).where(Team.opportunity_id == opportunity_id)).all()
    eligible = []
    full_count = 0
    hidden_count = 0
    reasons = set()
    for team in teams:
        if member_count(db, team.id) >= team.capacity:
            full_count += 1
            continue
        if membership:
            continue
        blocked = eligibility_reasons(user, team, opportunity)
        if blocked:
            hidden_count += 1
            reasons.update(blocked)
            continue
        eligible.append({**team_view(db, team), **score_match(user, team, opportunity)})
    eligible.sort(key=lambda item: (-item["score"], item["id"]))
    return {
        "teams": eligible,
        "total_teams": len(teams),
        "full_count": full_count,
        "hidden_count": hidden_count,
        "hidden_reasons": sorted(reasons),
        "already_joined": bool(membership),
    }


@app.get("/api/opportunities/{opportunity_id}/recommendations")
def recommendations(
    opportunity_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    opportunity = opportunity_or_404(db, opportunity_id)
    if db.scalar(
        select(Membership.id).where(
            Membership.opportunity_id == opportunity_id, Membership.user_id == user.id
        )
    ):
        return []
    results = []
    for team in db.scalars(
        select(Team).where(Team.opportunity_id == opportunity_id)
    ).all():
        if member_count(db, team.id) >= team.capacity:
            continue
        score = score_match(user, team, opportunity)
        if score is not None:
            results.append({**team_view(db, team), **score})
    return sorted(results, key=lambda item: (-item["score"], item["id"]))


@app.post("/api/opportunities/{opportunity_id}/teams", status_code=201)
def create_team(
    opportunity_id: int,
    data: TeamInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    user_id = user.id
    write_lock(db)
    opportunity_or_404(db, opportunity_id)
    if db.scalar(
        select(Membership.id).where(
            Membership.opportunity_id == opportunity_id, Membership.user_id == user_id
        )
    ):
        raise HTTPException(409, "You already belong to a team for this opportunity")
    values = data.model_dump()
    values["group_link"] = normalize_url(values["group_link"])
    team = Team(opportunity_id=opportunity_id, owner_id=user_id, **values)
    db.add(team)
    db.flush()
    db.add(Membership(team_id=team.id, opportunity_id=opportunity_id, user_id=user_id))
    interest = db.scalar(
        select(Interest).where(
            Interest.opportunity_id == opportunity_id, Interest.user_id == user_id
        )
    )
    if interest:
        interest.looking = False
    db.commit()
    return team_view(db, team, db.get(User, user_id))


@app.get("/api/teams/{team_id}")
def get_team(
    team_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    return team_view(db, team_or_404(db, team_id), user)


@app.post("/api/teams/{team_id}/requests", status_code=201)
def request_join(
    team_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    user_id = user.id
    write_lock(db)
    team = team_or_404(db, team_id)
    if member_count(db, team.id) >= team.capacity:
        record(db, "team_full", user_id, team.opportunity_id)
        db.commit()
        raise HTTPException(409, "Team is full")
    if db.scalar(
        select(Membership.id).where(
            Membership.opportunity_id == team.opportunity_id,
            Membership.user_id == user_id,
        )
    ):
        raise HTTPException(409, "You already belong to a team for this opportunity")
    if (
        score_match(
            db.get(User, user_id), team, opportunity_or_404(db, team.opportunity_id)
        )
        is None
    ):
        raise HTTPException(
            409, "Your profile does not meet the team's required date or availability"
        )
    if db.scalar(
        select(JoinRequest.id).where(
            JoinRequest.team_id == team_id, JoinRequest.user_id == user_id
        )
    ):
        raise HTTPException(409, "You have already requested this team")
    request = JoinRequest(team_id=team_id, user_id=user_id, status="pending")
    db.add(request)
    record(db, "request", user_id, team.opportunity_id)
    db.commit()
    return {"id": request.id, "status": request.status}


@app.get("/api/teams/{team_id}/requests")
def team_requests(
    team_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    team = team_or_404(db, team_id)
    if team.owner_id != user.id:
        raise HTTPException(403, "Only the team owner can view requests")
    opportunity = opportunity_or_404(db, team.opportunity_id)
    return [
        {
            "id": request.id,
            "status": request.status,
            "user": public_user(db.get(User, request.user_id)),
            "match": score_match(db.get(User, request.user_id), team, opportunity),
        }
        for request in db.scalars(
            select(JoinRequest).where(JoinRequest.team_id == team_id)
        ).all()
    ]


@app.post("/api/requests/{request_id}/{decision}")
def decide_request(
    request_id: int,
    decision: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if decision not in ("approve", "decline"):
        raise HTTPException(404, "Decision not found")
    user_id = user.id
    write_lock(db)
    request = db.get(JoinRequest, request_id)
    if not request:
        raise HTTPException(404, "Request not found")
    team = team_or_404(db, request.team_id)
    if team.owner_id != user_id:
        raise HTTPException(403, "Only the team owner can decide")
    if request.status != "pending":
        raise HTTPException(409, "Request is no longer pending")
    if decision == "decline":
        request.status = "declined"
        record(db, "rejection", request.user_id, team.opportunity_id)
    else:
        count = member_count(db, team.id)
        if count >= team.capacity:
            record(db, "team_full", request.user_id, team.opportunity_id)
            db.commit()
            raise HTTPException(409, "Team is full")
        if db.scalar(
            select(Membership.id).where(
                Membership.opportunity_id == team.opportunity_id,
                Membership.user_id == request.user_id,
            )
        ):
            raise HTTPException(
                409, "Applicant already belongs to a team for this opportunity"
            )
        applicant = db.get(User, request.user_id)
        if (
            not applicant
            or applicant.suspended
            or score_match(applicant, team, opportunity_or_404(db, team.opportunity_id))
            is None
        ):
            raise HTTPException(409, "Applicant is no longer eligible for this team")
        db.add(
            Membership(
                team_id=team.id,
                opportunity_id=team.opportunity_id,
                user_id=request.user_id,
            )
        )
        request.status = "approved"
        interest = db.scalar(
            select(Interest).where(
                Interest.opportunity_id == team.opportunity_id,
                Interest.user_id == request.user_id,
            )
        )
        if interest:
            interest.looking = False
        record(db, "approval", request.user_id, team.opportunity_id)
        if count + 1 == team.capacity:
            for other in db.scalars(
                select(JoinRequest).where(
                    JoinRequest.team_id == team.id,
                    JoinRequest.status == "pending",
                    JoinRequest.id != request.id,
                )
            ).all():
                other.status = "closed"
    db.commit()
    return {"status": request.status}


@app.get("/api/teams/{team_id}/candidates")
def candidates(
    team_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    team = team_or_404(db, team_id)
    if team.owner_id != user.id:
        raise HTTPException(403, "Only the team owner can view candidates")
    if member_count(db, team.id) >= team.capacity:
        return []
    opportunity = opportunity_or_404(db, team.opportunity_id)
    people = db.scalars(
        select(User)
        .join(Interest, Interest.user_id == User.id)
        .where(
            Interest.opportunity_id == team.opportunity_id,
            Interest.looking.is_(True),
            User.suspended.is_(False),
            User.hidden.is_(False),
        )
    ).all()
    result = []
    for person in people:
        if db.scalar(
            select(Membership.id).where(
                Membership.user_id == person.id,
                Membership.opportunity_id == team.opportunity_id,
            )
        ):
            continue
        score = score_match(person, team, opportunity)
        if score is not None:
            result.append({"user": public_user(person), **score})
    return sorted(result, key=lambda item: (-item["score"], item["user"]["id"]))


@app.get("/api/teams/{team_id}/messages")
def get_messages(
    team_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    team_or_404(db, team_id)
    if not is_member(db, team_id, user.id):
        raise HTTPException(403, "Only team members can read messages")
    return [
        {
            "id": item.id,
            "author": db.get(User, item.author_id).display_name,
            "text": item.text,
            "created_at": item.created_at,
        }
        for item in db.scalars(
            select(TeamMessage)
            .where(TeamMessage.team_id == team_id)
            .order_by(TeamMessage.id)
        ).all()
    ]


@app.post("/api/teams/{team_id}/messages", status_code=201)
def post_message(
    team_id: int,
    data: MessageInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    team = team_or_404(db, team_id)
    if not is_member(db, team_id, user.id):
        raise HTTPException(403, "Only team members can post messages")
    message = TeamMessage(team_id=team_id, author_id=user.id, text=data.text.strip())
    db.add(message)
    record(db, "message", user.id, team.opportunity_id)
    db.commit()
    return {"id": message.id, "text": message.text}


@app.post("/api/reports", status_code=201)
def create_report(
    data: ReportInput, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    target = db.get(
        User if data.target_type == "profile" else Opportunity, data.target_id
    )
    if not target:
        raise HTTPException(404, "Report target not found")
    report = Report(reporter_id=user.id, **data.model_dump())
    db.add(report)
    db.commit()
    return {"id": report.id, "status": report.status}


@app.get("/api/admin/reports")
def list_reports(_admin: User = Depends(admin_user), db: Session = Depends(get_db)):
    return [
        {
            "id": item.id,
            "target_type": item.target_type,
            "target_id": item.target_id,
            "reason": item.reason,
            "status": item.status,
        }
        for item in db.scalars(select(Report).order_by(Report.id.desc())).all()
    ]


@app.post("/api/admin/{action}/{target_id}")
def moderate(
    action: str,
    target_id: int,
    admin: User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    if action not in ("hide-opportunity", "hide-profile", "suspend-user"):
        raise HTTPException(404, "Action not found")
    target = db.get(Opportunity if action == "hide-opportunity" else User, target_id)
    if not target:
        raise HTTPException(404, "Target not found")
    if action == "suspend-user":
        target.suspended = True
    else:
        target.hidden = True
    db.add(ModerationAction(admin_id=admin.id, action=action, target_id=target_id))
    db.commit()
    return {"ok": True}


@app.get("/api/me/teams")
def my_teams(user: User = Depends(current_user), db: Session = Depends(get_db)):
    teams = db.scalars(
        select(Team)
        .join(Membership, Membership.team_id == Team.id)
        .where(Membership.user_id == user.id)
    ).all()
    return [
        team_view(db, team, user)
        for team in teams
        if not db.get(Opportunity, team.opportunity_id).hidden
    ]


@app.get("/api/me/requests")
def my_requests(user: User = Depends(current_user), db: Session = Depends(get_db)):
    requests = db.scalars(
        select(JoinRequest)
        .where(JoinRequest.user_id == user.id)
        .order_by(JoinRequest.id.desc())
    ).all()
    return [
        {
            "id": item.id,
            "status": item.status,
            "team_id": item.team_id,
            "team_name": db.get(Team, item.team_id).name,
            "opportunity_id": db.get(Team, item.team_id).opportunity_id,
        }
        for item in requests
    ]


@app.get("/api/insights")
def insights(_user: User = Depends(current_user), db: Session = Depends(get_db)):
    opportunities = db.scalars(
        select(Opportunity).where(Opportunity.hidden.is_(False))
    ).all()
    demand = {}
    skill_counts = {}
    total_capacity = total_members = 0
    waiting_seconds = []
    for opportunity in opportunities:
        demand.setdefault(opportunity.category, set())
        interest_events = db.scalars(
            select(ActivityEvent)
            .where(
                ActivityEvent.opportunity_id == opportunity.id,
                ActivityEvent.name == "interest",
            )
            .order_by(ActivityEvent.created_at)
        ).all()
        first_interest = {}
        for event in interest_events:
            first_interest.setdefault(event.user_id, event.created_at)
        for user_id, interested_at in first_interest.items():
            demand[opportunity.category].add(user_id)
            membership = db.scalar(
                select(Membership).where(
                    Membership.opportunity_id == opportunity.id,
                    Membership.user_id == user_id,
                )
            )
            if membership and membership.created_at >= interested_at:
                waiting_seconds.append(
                    (membership.created_at - interested_at).total_seconds()
                )
        for team in db.scalars(
            select(Team).where(Team.opportunity_id == opportunity.id)
        ).all():
            total_capacity += team.capacity
            total_members += member_count(db, team.id)
            for skill in team.skills:
                skill_counts[skill] = skill_counts.get(skill, 0) + 1
    return {
        "period": "all recorded data",
        "demand": {key: len(value) for key, value in demand.items()},
        "team_fill": {
            "members": total_members,
            "capacity": total_capacity,
            "rate": total_members / total_capacity if total_capacity else None,
        },
        "time_to_join": {
            "sample_size": len(waiting_seconds),
            "average_seconds": (
                sum(waiting_seconds) / len(waiting_seconds) if waiting_seconds else None
            ),
        },
        "missing_skills": dict(
            sorted(skill_counts.items(), key=lambda item: (-item[1], item[0]))
        ),
    }
