"""Add real, sourced opportunities and explicitly fictional demo participants.

Run from the project root with `python -m backend.seed_real_opportunities`.
Existing records are never overwritten. Re-running is safe for records this
script previously created. These are snapshots, not an automatically updated feed.
"""

from datetime import datetime
from pathlib import Path
import sqlite3

from sqlalchemy import select

from .database import DATABASE_URL, SessionLocal, engine
from .migrate import migrate
from .models import ActivityEvent, Interest, Membership, Opportunity, Team, User
from .security import hash_password


DEMO_PASSWORD = "DemoPeer2026!"

# These listings were checked against the linked organizer pages on 12 Nov 2026.
# The database stores a single date, but each opportunity has several stages;
# therefore dates are included in the description instead of forcing one date.
OPPORTUNITIES = [
    {
        "title": "TrueFoundry Forge-a-thon",
        "description": "Build a VS Code coding agent with TrueForge. Open to participants aged 18 and over; teams of up to 5. Registration closes 15 Nov 2026; remote round deadline 20 Nov; Techfest IIT Bombay finals 16–18 Dec. Demo-labeled teams on PeerSpace are fictional.",
        "organizer": "Techfest IIT Bombay and TrueFoundry",
        "official_url": "https://techfest.org/competitions/forge-a-thon",
    },
    {
        "title": "AyushTech Innovate: National Open Ayurveda AI Challenge",
        "description": "Build source-grounded AI tools for Ayurveda. Teams of 2–4 must include an eligible Ayurveda student; see the official rules. Registration closes 15 Nov 2026; final presentations 15–18 Dec at Techfest IIT Bombay. Demo-labeled teams on PeerSpace are fictional.",
        "organizer": "Techfest IIT Bombay",
        "official_url": "https://techfest.org/competitions/ayushtech",
    },
    {
        "title": "National Aeromodelling Challenge",
        "description": "Student teams design and fly a payload-carrying RC aircraft. Teams of 2–4; registration and abstract submission close 25 Nov 2026. Qualifiers are 15–16 Dec and the main round is 17 Dec at IIT Bombay. Demo-labeled teams on PeerSpace are fictional.",
        "organizer": "Techfest IIT Bombay",
        "official_url": "https://techfest.org/competitions/Aeromodelling-2026",
    },
    {
        "title": "Agentic AI in BFSI Hackathon 2026",
        "description": "Build AI solutions for banking workflows in a Perfios and Techfest IIT Bombay hackathon. Student teams of up to 4; registration closes 25 Nov 2026, with finals 15–18 Dec. Check the listing for current rules and eligibility. Demo-labeled teams on PeerSpace are fictional.",
        "organizer": "Perfios and Techfest IIT Bombay",
        "official_url": "https://unstop.com/hackathons/agentic-ai-in-bfsi-hackathon-iit-bombay-1800857/amp",
    },
    {
        "title": "Global Sustainability Challenge 2026–27",
        "description": "University student teams develop sustainability solutions in energy or climate resilience. Teams of 1–6; at least one member must meet the organizer's age rule. Registration, team formation and Phase 1 submissions close 22 Nov 2026. Demo-labeled teams on PeerSpace are fictional.",
        "organizer": "Global Sustainability Challenge, with IIT Bombay as South Asia partner",
        "official_url": "https://gesh.iitb.ac.in/event-details/global-sustainability-challenge-2026-2027",
    },
]

DEMO_USERS = [
    (
        "maya",
        "[DEMO] Maya",
        {"Python": 4, "React": 3},
        ["evening", "weekends"],
        ["AI", "hackathon"],
    ),
    ("arjun", "[DEMO] Arjun", {"Python": 4, "AI": 4}, ["evening"], ["AI", "health"]),
    ("noor", "[DEMO] Noor", {"CAD": 4, "Electronics": 3}, ["weekends"], ["aerospace"]),
    (
        "dev",
        "[DEMO] Dev",
        {"Python": 4, "Data": 3},
        ["evening", "weekends"],
        ["finance", "AI"],
    ),
    (
        "riya",
        "[DEMO] Riya",
        {"Research": 4, "Design": 3},
        ["weekends"],
        ["sustainability"],
    ),
    (
        "tara",
        "[DEMO] Tara",
        {"React": 4, "Design": 4},
        ["evening"],
        ["AI", "hackathon"],
    ),
    (
        "kabir",
        "[DEMO] Kabir",
        {"Python": 3, "SQL": 4},
        ["evening", "weekends"],
        ["finance"],
    ),
    (
        "isha",
        "[DEMO] Isha",
        {"Research": 4, "Design": 4},
        ["weekends"],
        ["sustainability"],
    ),
]

DEMO_TEAMS = [
    (0, "maya", "[DEMO] Code Garden", 4, {"React": 3, "Python": 3}, ["evening"]),
    (1, "arjun", "[DEMO] Health and AI", 4, {"AI": 3, "Research": 3}, ["evening"]),
    (2, "noor", "[DEMO] Flight Lab", 4, {"CAD": 3, "Electronics": 3}, ["weekends"]),
    (3, "dev", "[DEMO] Fintech Builders", 4, {"Python": 3, "SQL": 3}, ["evening"]),
    (4, "riya", "[DEMO] Green Ideas", 4, {"Research": 3, "Design": 3}, ["weekends"]),
]


def backup_database():
    if not DATABASE_URL.startswith("sqlite:///./"):
        raise RuntimeError(
            "This local seed script expects the default relative SQLite database URL."
        )
    path = Path(DATABASE_URL.removeprefix("sqlite:///./"))
    if not path.is_file():
        raise RuntimeError(
            "Database not found. Start PeerSpace from the project root first."
        )
    backup = path.with_name(f"{path.stem}-backup-{datetime.now():%Y%m%d-%H%M%S-%f}.db")
    with sqlite3.connect(path) as source, sqlite3.connect(backup) as destination:
        source.backup(destination)
    return backup


def seed():
    backup = backup_database()
    migrate(engine)
    with SessionLocal() as db:
        users = {}
        for key, name, skills, availability, interests in DEMO_USERS:
            email = f"{key}.demo@peerspace.invalid"
            user = db.scalar(select(User).where(User.email == email))
            if user and user.display_name != name:
                raise RuntimeError(
                    f"Refusing to overwrite the existing account {email}."
                )
            if user is None:
                user = User(
                    email=email,
                    display_name=name,
                    password_hash=hash_password(DEMO_PASSWORD),
                    skills=list(skills),
                    bio=f"{name} is a fictional demo student exploring campus activities.",
                    topics=interests,
                    interests=["hackathon"],
                    available_dates=[],
                    courses=[],
                    experience=[],
                    contact=None,
                )
                db.add(user)
                db.flush()
            users[key] = user

        items = []
        for data in OPPORTUNITIES:
            item = db.scalar(
                select(Opportunity).where(
                    Opportunity.official_url == data["official_url"]
                )
            )
            if item is None:
                item = Opportunity(
                    **data,
                    category="hackathon",
                    source="curated",
                    event_date=None,
                    schedule={"kind": "undecided"},
                    created_by=users["maya"].id,
                )
                db.add(item)
                db.flush()
            elif item.hidden:
                raise RuntimeError(
                    f"An existing opportunity is hidden: {data['title']}. No changes were saved."
                )
            items.append(item)

        for index, owner_key, name, capacity, skills, availability in DEMO_TEAMS:
            opportunity, owner = items[index], users[owner_key]
            team = db.scalar(
                select(Team).where(
                    Team.opportunity_id == opportunity.id,
                    Team.owner_id == owner.id,
                    Team.name == name,
                )
            )
            if team is None:
                existing = db.scalar(
                    select(Membership).where(
                        Membership.opportunity_id == opportunity.id,
                        Membership.user_id == owner.id,
                    )
                )
                if existing:
                    raise RuntimeError(
                        f"Demo owner {owner.display_name} already belongs to a different team for {opportunity.title}."
                    )
                team = Team(
                    opportunity_id=opportunity.id,
                    owner_id=owner.id,
                    name=name,
                    capacity=capacity,
                    skills=list(skills),
                    goal="Build a team for this activity",
                    schedule={"kind": "undecided"},
                    availability_required=False,
                    experience=[],
                )
                db.add(team)
                db.flush()
                db.add(
                    Membership(
                        team_id=team.id, opportunity_id=opportunity.id, user_id=owner.id
                    )
                )

        for index, key in [(0, "tara"), (3, "kabir"), (4, "isha")]:
            opportunity, user = items[index], users[key]
            membership = db.scalar(
                select(Membership).where(
                    Membership.opportunity_id == opportunity.id,
                    Membership.user_id == user.id,
                )
            )
            interest = db.scalar(
                select(Interest).where(
                    Interest.opportunity_id == opportunity.id,
                    Interest.user_id == user.id,
                )
            )
            if interest is None and membership is None:
                db.add(
                    Interest(
                        opportunity_id=opportunity.id, user_id=user.id, looking=True
                    )
                )
                db.add(
                    ActivityEvent(
                        name="interest", opportunity_id=opportunity.id, user_id=user.id
                    )
                )

        db.commit()
        print(f"Backup: {backup}")
        print(
            f"Available: {len(items)} sourced opportunities, {len(users)} labeled demo accounts, {len(DEMO_TEAMS)} labeled demo teams."
        )


if __name__ == "__main__":
    seed()
