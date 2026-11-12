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
from .migrate import migrate
from .matching import activity_match, date_fit, eligibility_reasons, score_match
from .models import (
    ActivityEvent,
    Interest,
    Invitation,
    JoinRequest,
    LoginSession,
    Membership,
    MembershipExit,
    ModerationAction,
    Notification,
    Opportunity,
    Report,
    Team,
    TeamMessage,
    User,
)
from .schemas import (
    Login,
    JoinInput,
    InterestInput,
    MembershipExitInput,
    MessageInput,
    OpportunityInput,
    Profile,
    ReportInput,
    Signup,
    Schedule,
    TeamInput,
    OwnerTransferInput,
)
from .security import check_password, create_token, hash_password, hash_token


@asynccontextmanager
async def lifespan(_app):
    migrate(engine)
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
        "bio": user.bio,
        "skills": user.skills,
        "interests": user.interests,
        "topics": user.topics,
        "courses": user.courses,
        "experience": user.experience,
    }


def own_user(user):
    return {
        **public_user(user),
        "email": user.email,
        "contact": user.contact,
        "profile_complete": bool(user.bio and user.skills and user.interests),
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
    opportunity = db.get(Opportunity, team.opportunity_id)
    count = member_count(db, team.id)
    result = {
        "id": team.id,
        "opportunity_id": team.opportunity_id,
        "owner_id": team.owner_id,
        "name": team.name,
        "activity_title": opportunity.title,
        "category": opportunity.category,
        "goal": team.goal,
        "schedule": team.schedule or opportunity.schedule,
        "question": team.question,
        "closed": team.closed,
        "capacity": team.capacity,
        "member_count": count,
        "skills": team.skills,
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


def opportunity_view(db, item, user=None):
    result = {
        "id": item.id,
        "title": item.title,
        "description": item.description,
        "category": item.category,
        "source": item.source,
        "organizer": item.organizer,
        "official_url": item.official_url,
        "event_date": item.event_date,
        "topics": item.topics,
        "skills": item.skills,
        "course": item.course,
        "experience": item.experience,
        "eligibility": item.eligibility,
        "schedule": item.schedule,
        "team_count": db.scalar(
            select(func.count()).select_from(Team).where(Team.opportunity_id == item.id, Team.closed.is_(False))
        ),
        "looking_count": db.scalar(
            select(func.count())
            .select_from(Interest)
            .where(Interest.opportunity_id == item.id, Interest.looking.is_(True))
        ),
    }
    if user:
        result["fit"] = activity_match(user, item)
    return result


def optional_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        return None
    session = db.get(LoginSession, hash_token(authorization[7:]))
    if not session or session.expires_at.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc):
        return None
    user = db.get(User, session.user_id)
    return user if user and not user.suspended else None


def notify(db, user_id, text, team=None, opportunity_id=None):
    db.add(Notification(
        user_id=user_id, text=text, team_id=team.id if team else None,
        opportunity_id=opportunity_id or (team.opportunity_id if team else None),
    ))


def normalized_schedule(schedule):
    try:
        return schedule.normalized()
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


def saved_answers(data):
    return data.date_answers.model_dump(mode="json")


def ensure_profile(user):
    if not (user.bio and user.skills and user.interests):
        raise HTTPException(409, "Complete your profile before participating")


def close_pending(db, team):
    for request in db.scalars(select(JoinRequest).where(
        JoinRequest.team_id == team.id, JoinRequest.status == "pending"
    )).all():
        request.status = "closed"
        notify(db, request.user_id, f"{team.name} is full; your request closed", team)
    for invite in db.scalars(select(Invitation).where(
        Invitation.team_id == team.id, Invitation.status == "pending"
    )).all():
        invite.status = "closed"
        notify(db, invite.user_id, f"{team.name} is full; your invitation closed", team)


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
        bio=data.bio.strip(),
        interests=list(dict.fromkeys(data.interests)),
        skills=list(dict.fromkeys(skill.strip() for skill in data.skills if skill.strip())),
        topics=data.topics,
        courses=data.courses,
        experience=data.experience,
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
        setattr(user, key, value)
    db.commit()
    return own_user(user)


@app.get("/api/opportunities")
def list_opportunities(
    q: str = "",
    category: str = "",
    source: str = "",
    suggest: bool = False,
    user: User | None = Depends(optional_user),
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
    return [opportunity_view(db, item, user) for item in items]


@app.post("/api/opportunities", status_code=201)
def create_opportunity(
    data: OpportunityInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    ensure_profile(user)
    schedule = normalized_schedule(data.schedule)
    if data.event_date and schedule["kind"] == "undecided":
        schedule = {"kind": "single", "start_date": data.event_date.isoformat(), "required_dates": [data.event_date.isoformat()]}
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
    event_date = schedule.get("start_date")
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
        topics=data.topics,
        skills=data.skills,
        course=data.course,
        experience=data.experience,
        eligibility=data.eligibility,
        schedule=schedule,
        created_by=user.id,
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This official link is already listed")
    return opportunity_view(db, item, user)


@app.get("/api/opportunities/{opportunity_id}")
def get_opportunity(opportunity_id: int, user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    return opportunity_view(db, opportunity_or_404(db, opportunity_id), user)


@app.post("/api/opportunities/{opportunity_id}/interest")
def express_interest(
    opportunity_id: int,
    data: InterestInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    user_id = user.id
    ensure_profile(user)
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
            opportunity_id=opportunity_id, user_id=user_id, looking=True,
            date_answers=saved_answers(data),
        )
        db.add(interest)
        record(db, "interest", user_id, opportunity_id)
    else:
        interest.looking = True
        interest.date_answers = saved_answers(data)
    db.commit()
    return {"looking": True, "date_answers": interest.date_answers}


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
            select(Team).where(Team.opportunity_id == opportunity_id, Team.closed.is_(False))
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
        "date_answers": interest.date_answers if interest else {},
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
        "invitations": [
            {"id": invite.id, "team_id": team.id, "team_name": team.name, "status": invite.status}
            for invite, team in db.execute(
                select(Invitation, Team).join(Team, Team.id == Invitation.team_id)
                .where(Team.opportunity_id == opportunity_id, Invitation.user_id == user.id)
            ).all()
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
    teams = db.scalars(select(Team).where(Team.opportunity_id == opportunity_id, Team.closed.is_(False))).all()
    interest = db.scalar(select(Interest).where(Interest.opportunity_id == opportunity_id, Interest.user_id == user.id))
    answers = interest.date_answers if interest else None
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
        eligible.append({**team_view(db, team), **score_match(user, team, opportunity, answers)})
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
        select(Team).where(Team.opportunity_id == opportunity_id, Team.closed.is_(False))
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
    ensure_profile(user)
    schedule = normalized_schedule(data.schedule)
    write_lock(db)
    opportunity = opportunity_or_404(db, opportunity_id)
    if schedule["kind"] == "undecided" and (opportunity.schedule or {}).get("kind") != "undecided":
        schedule = opportunity.schedule
    if db.scalar(
        select(Membership.id).where(
            Membership.opportunity_id == opportunity_id, Membership.user_id == user_id
        )
    ):
        raise HTTPException(409, "You already belong to a team for this opportunity")
    values = data.model_dump(exclude={"schedule"})
    values["schedule"] = schedule
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
    team_id: int, data: JoinInput, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    user_id = user.id
    ensure_profile(user)
    write_lock(db)
    team = team_or_404(db, team_id)
    if team.closed:
        raise HTTPException(409, "Team is closed")
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
    opportunity = opportunity_or_404(db, team.opportunity_id)
    answers = saved_answers(data)
    if eligibility_reasons(user, team, opportunity, answers):
        raise HTTPException(409, "You cannot attend a required team date")
    previous = db.scalar(
        select(JoinRequest).where(
            JoinRequest.team_id == team_id, JoinRequest.user_id == user_id
        )
    )
    if previous and previous.status != "closed":
        raise HTTPException(409, "You have already requested this team")
    if db.scalar(select(MembershipExit.id).where(
        MembershipExit.team_id == team_id, MembershipExit.user_id == user_id,
        MembershipExit.reason == "removed",
    )):
        raise HTTPException(409, "The owner must invite you to rejoin this team")
    request = previous or JoinRequest(team_id=team_id, user_id=user_id)
    request.status = "pending"
    request.date_answers = answers
    request.motivation = data.motivation.strip()
    request.question_answer = data.question_answer.strip()
    if team.question and not request.question_answer:
        raise HTTPException(422, "Please answer the team's question")
    db.add(request)
    interest = db.scalar(select(Interest).where(Interest.opportunity_id == team.opportunity_id, Interest.user_id == user_id))
    if interest:
        interest.date_answers = answers
    notify(db, team.owner_id, f"New request for {team.name}", team)
    record(db, "request", user_id, team.opportunity_id)
    db.commit()
    return {"id": request.id, "status": request.status}


@app.put("/api/requests/{request_id}")
def update_request(request_id: int, data: JoinInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    request = db.get(JoinRequest, request_id)
    if not request or request.user_id != user.id:
        raise HTTPException(404, "Request not found")
    if request.status != "pending":
        raise HTTPException(409, "Only pending requests can be updated")
    team = team_or_404(db, request.team_id)
    answers = saved_answers(data)
    if eligibility_reasons(user, team, opportunity_or_404(db, team.opportunity_id), answers):
        raise HTTPException(409, "You cannot attend a required team date")
    request.date_answers = answers
    request.motivation = data.motivation.strip()
    request.question_answer = data.question_answer.strip()
    notify(db, team.owner_id, f"Request updated for {team.name}", team)
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
            "match": score_match(db.get(User, request.user_id), team, opportunity, request.date_answers),
            "date_answers": request.date_answers,
            "motivation": request.motivation,
            "question_answer": request.question_answer,
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
    if team.closed:
        raise HTTPException(409, "Team is closed")
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
        opportunity = opportunity_or_404(db, team.opportunity_id)
        fit = date_fit(team.schedule or opportunity.schedule, request.date_answers)
        if not applicant or applicant.suspended or fit["status"] in ("ineligible", "not_confirmed"):
            raise HTTPException(409, "Applicant must confirm all required dates before approval")
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
            close_pending(db, team)
    notify(db, request.user_id, f"Your request for {team.name} was {request.status}", team)
    db.commit()
    return {"status": request.status}


@app.get("/api/teams/{team_id}/candidates")
def candidates(
    team_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    team = team_or_404(db, team_id)
    if team.owner_id != user.id:
        raise HTTPException(403, "Only the team owner can view candidates")
    if team.closed or member_count(db, team.id) >= team.capacity:
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
        interest = db.scalar(select(Interest).where(Interest.user_id == person.id, Interest.opportunity_id == team.opportunity_id))
        score = score_match(person, team, opportunity, interest.date_answers)
        result.append({"user": public_user(person), "date_answers": interest.date_answers, **score})
    return sorted(result, key=lambda item: (-item["score"], item["user"]["id"]))


@app.post("/api/teams/{team_id}/invitations", status_code=201)
def invite_candidate(team_id: int, candidate_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    write_lock(db)
    team = team_or_404(db, team_id)
    if team.owner_id != user.id:
        raise HTTPException(403, "Only the owner can invite")
    if team.closed or member_count(db, team_id) >= team.capacity:
        raise HTTPException(409, "Team is not open")
    interest = db.scalar(select(Interest).where(
        Interest.user_id == candidate_id, Interest.opportunity_id == team.opportunity_id,
        Interest.looking.is_(True),
    ))
    if not interest:
        raise HTTPException(409, "Only students in this activity's looking pool can be invited")
    if db.scalar(select(Membership.id).where(
        Membership.user_id == candidate_id, Membership.opportunity_id == team.opportunity_id,
    )):
        raise HTTPException(409, "Student already joined a team")
    invite = db.scalar(select(Invitation).where(Invitation.team_id == team_id, Invitation.user_id == candidate_id))
    if invite and invite.status == "pending":
        raise HTTPException(409, "Invitation already pending")
    invite = invite or Invitation(team_id=team_id, user_id=candidate_id)
    invite.status = "pending"
    db.add(invite)
    notify(db, candidate_id, f"{team.name} invited you to join", team)
    db.commit()
    return {"id": invite.id, "status": invite.status}


@app.post("/api/invitations/{invitation_id}/{decision}")
def decide_invitation(invitation_id: int, decision: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if decision not in ("accept", "decline"):
        raise HTTPException(404, "Decision not found")
    write_lock(db)
    invite = db.get(Invitation, invitation_id)
    if not invite or invite.user_id != user.id:
        raise HTTPException(404, "Invitation not found")
    if invite.status != "pending":
        raise HTTPException(409, "Invitation is no longer pending")
    team = team_or_404(db, invite.team_id)
    if decision == "accept":
        if team.closed or member_count(db, team.id) >= team.capacity:
            raise HTTPException(409, "Team is no longer open")
        if db.scalar(select(Membership.id).where(Membership.user_id == user.id, Membership.opportunity_id == team.opportunity_id)):
            raise HTTPException(409, "You already belong to a team for this activity")
        interest = db.scalar(select(Interest).where(Interest.user_id == user.id, Interest.opportunity_id == team.opportunity_id))
        opportunity = opportunity_or_404(db, team.opportunity_id)
        fit = date_fit(team.schedule or opportunity.schedule, interest.date_answers if interest else None)
        if fit["status"] in ("ineligible", "not_confirmed"):
            raise HTTPException(409, "Confirm the required dates in the looking pool before accepting")
        db.add(Membership(team_id=team.id, opportunity_id=team.opportunity_id, user_id=user.id))
        if interest:
            interest.looking = False
        invite.status = "accepted"
        if member_count(db, team.id) == team.capacity:
            close_pending(db, team)
    else:
        invite.status = "declined"
    notify(db, team.owner_id, f"{user.display_name} {invite.status} your invitation to {team.name}", team)
    db.commit()
    return {"status": invite.status}


def member_exit(db, membership, team, reason):
    db.add(MembershipExit(
        user_id=membership.user_id, team_id=team.id,
        opportunity_id=team.opportunity_id, reason=reason,
    ))
    db.delete(membership)
    previous = db.scalar(select(JoinRequest).where(
        JoinRequest.team_id == team.id, JoinRequest.user_id == membership.user_id,
        JoinRequest.status == "approved",
    ))
    if previous:
        previous.status = "closed"


@app.post("/api/teams/{team_id}/leave")
def leave_team(team_id: int, data: MembershipExitInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    write_lock(db)
    team = team_or_404(db, team_id)
    if team.owner_id == user.id:
        raise HTTPException(409, "Transfer ownership or close the team first")
    membership = db.scalar(select(Membership).where(Membership.team_id == team_id, Membership.user_id == user.id))
    if not membership:
        raise HTTPException(403, "Only members can leave")
    member_exit(db, membership, team, "left")
    if data.return_to_pool:
        interest = db.scalar(select(Interest).where(Interest.user_id == user.id, Interest.opportunity_id == team.opportunity_id))
        if not interest:
            interest = Interest(user_id=user.id, opportunity_id=team.opportunity_id)
            db.add(interest)
        interest.looking = True
    notify(db, team.owner_id, f"{user.display_name} left {team.name}", team)
    db.commit()
    return {"ok": True}


@app.post("/api/teams/{team_id}/remove/{member_id}")
def remove_member(team_id: int, member_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    write_lock(db)
    team = team_or_404(db, team_id)
    if team.owner_id != user.id or member_id == user.id:
        raise HTTPException(403, "Only the owner can remove another member")
    membership = db.scalar(select(Membership).where(Membership.team_id == team_id, Membership.user_id == member_id))
    if not membership:
        raise HTTPException(404, "Member not found")
    member_exit(db, membership, team, "removed")
    notify(db, member_id, f"You were removed from {team.name}", team)
    db.commit()
    return {"ok": True}


@app.post("/api/teams/{team_id}/transfer")
def transfer_owner(team_id: int, data: OwnerTransferInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    write_lock(db)
    team = team_or_404(db, team_id)
    if team.owner_id != user.id:
        raise HTTPException(403, "Only the owner can transfer ownership")
    if data.user_id == user.id or not is_member(db, team_id, data.user_id):
        raise HTTPException(409, "Choose another accepted member")
    team.owner_id = data.user_id
    notify(db, data.user_id, f"You now own {team.name}", team)
    db.commit()
    return {"ok": True}


@app.post("/api/teams/{team_id}/close")
def close_team(team_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    write_lock(db)
    team = team_or_404(db, team_id)
    if team.owner_id != user.id:
        raise HTTPException(403, "Only the owner can close the team")
    if team.closed:
        raise HTTPException(409, "Team already closed")
    team.closed = True
    close_pending(db, team)
    for membership in db.scalars(select(Membership).where(Membership.team_id == team_id)).all():
        notify(db, membership.user_id, f"{team.name} was closed", team)
        member_exit(db, membership, team, "closed")
    db.commit()
    return {"ok": True}


@app.put("/api/teams/{team_id}/schedule")
def update_team_schedule(team_id: int, data: Schedule, user: User = Depends(current_user), db: Session = Depends(get_db)):
    team = team_or_404(db, team_id)
    if team.owner_id != user.id:
        raise HTTPException(403, "Only the owner can update the schedule")
    team.schedule = normalized_schedule(data)
    recipients = {item.user_id for item in db.scalars(select(Membership).where(Membership.team_id == team_id)).all()}
    recipients.update(item.user_id for item in db.scalars(select(JoinRequest).where(
        JoinRequest.team_id == team_id, JoinRequest.status == "pending",
    )).all())
    for recipient in recipients:
        notify(db, recipient, f"{team.name} changed its schedule; please review dates", team)
    db.commit()
    return team_view(db, team, user)


@app.get("/api/me/notifications")
def notifications(user: User = Depends(current_user), db: Session = Depends(get_db)):
    items = db.scalars(select(Notification).where(Notification.user_id == user.id).order_by(Notification.id.desc())).all()
    return {"unread_count": sum(not item.read for item in items), "items": [
        {"id": item.id, "text": item.text, "read": item.read, "created_at": item.created_at,
         "team_id": item.team_id, "opportunity_id": item.opportunity_id,
         "activity_title": db.get(Opportunity, item.opportunity_id).title if item.opportunity_id else None,
         "category": db.get(Opportunity, item.opportunity_id).category if item.opportunity_id else None,
         "schedule": db.get(Team, item.team_id).schedule if item.team_id else db.get(Opportunity, item.opportunity_id).schedule if item.opportunity_id else {}}
        for item in items
    ]}


@app.post("/api/me/notifications/{notification_id}/read")
def read_notification(notification_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = db.get(Notification, notification_id)
    if not item or item.user_id != user.id:
        raise HTTPException(404, "Notification not found")
    item.read = True
    db.commit()
    return {"ok": True}


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
            "activity_title": db.get(Opportunity, db.get(Team, item.team_id).opportunity_id).title,
            "category": db.get(Opportunity, db.get(Team, item.team_id).opportunity_id).category,
            "schedule": db.get(Team, item.team_id).schedule,
        }
        for item in requests
    ]


@app.get("/api/me/participation")
def my_participation(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {
        "teams": my_teams(user, db),
        "requests": my_requests(user, db),
        "looking": [
            {"opportunity_id": item.opportunity_id, "activity_title": opportunity.title,
             "category": opportunity.category, "schedule": opportunity.schedule,
             "date_answers": item.date_answers}
            for item, opportunity in db.execute(
                select(Interest, Opportunity).join(Opportunity, Opportunity.id == Interest.opportunity_id)
                .where(Interest.user_id == user.id, Interest.looking.is_(True), Opportunity.hidden.is_(False))
            ).all()
        ],
        "invitations": [
            {"id": invite.id, "status": invite.status, "team_id": team.id, "team_name": team.name,
             "opportunity_id": opportunity.id, "activity_title": opportunity.title,
             "category": opportunity.category, "schedule": team.schedule or opportunity.schedule}
            for invite, team, opportunity in db.execute(
                select(Invitation, Team, Opportunity)
                .join(Team, Team.id == Invitation.team_id)
                .join(Opportunity, Opportunity.id == Team.opportunity_id)
                .where(Invitation.user_id == user.id)
            ).all()
        ],
    }


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
