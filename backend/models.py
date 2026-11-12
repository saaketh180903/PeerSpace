"""Persistent records backing the initial PeerSpace user journey."""

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    skills: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    bio: Mapped[str] = mapped_column(Text, default="", nullable=False)
    interests: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    topics: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    availability: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    available_dates: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    courses: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    experience: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    contact: Mapped[str | None] = mapped_column(String(320))
    suspended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class LoginSession(Base):
    __tablename__ = "login_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class Opportunity(Base):
    __tablename__ = "opportunities"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="student")
    organizer: Mapped[str | None] = mapped_column(String(200))
    official_url: Mapped[str | None] = mapped_column(String(2048), unique=True)
    event_date: Mapped[str | None] = mapped_column(String(10))
    topics: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    skills: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    course: Mapped[str | None] = mapped_column(String(120))
    experience: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    eligibility: Mapped[str] = mapped_column(Text, default="", nullable=False)
    schedule: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    __table_args__ = (
        CheckConstraint(
            "category IN ('hackathon','course_project','study_group','trek_sport')",
            name="opportunity_category",
        ),
        CheckConstraint(
            "source IN ('student','curated','scraped')", name="opportunity_source"
        ),
    )


class Interest(Base):
    __tablename__ = "interests"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("opportunities.id"), nullable=False
    )
    looking: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    date_answers: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    __table_args__ = (UniqueConstraint("user_id", "opportunity_id"),)


class Team(Base):
    __tablename__ = "teams"
    id: Mapped[int] = mapped_column(primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("opportunities.id"), nullable=False
    )
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    capacity: Mapped[int] = mapped_column(nullable=False)
    skills: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    goal: Mapped[str] = mapped_column(Text, default="", nullable=False)
    schedule: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    question: Mapped[str] = mapped_column(Text, default="", nullable=False)
    closed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    availability: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    availability_required: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    course: Mapped[str | None] = mapped_column(String(120))
    experience: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    group_link: Mapped[str | None] = mapped_column(String(2048))
    __table_args__ = (
        CheckConstraint("capacity >= 1 AND capacity <= 100", name="team_capacity"),
        UniqueConstraint("id", "opportunity_id"),
    )


class Membership(Base):
    __tablename__ = "memberships"
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(nullable=False)
    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("opportunities.id"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    __table_args__ = (
        ForeignKeyConstraint(
            ["team_id", "opportunity_id"], ["teams.id", "teams.opportunity_id"]
        ),
        UniqueConstraint("opportunity_id", "user_id"),
    )


class JoinRequest(Base):
    __tablename__ = "join_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    date_answers: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    motivation: Mapped[str] = mapped_column(Text, default="", nullable=False)
    question_answer: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    __table_args__ = (
        UniqueConstraint("team_id", "user_id"),
        CheckConstraint("status IN ('pending','approved','declined','closed')"),
    )


class TeamMessage(Base):
    __tablename__ = "team_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[int] = mapped_column(nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )


class ActivityEvent(Base):
    __tablename__ = "activity_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    opportunity_id: Mapped[int | None] = mapped_column(ForeignKey("opportunities.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )


class ModerationAction(Base):
    __tablename__ = "moderation_actions"
    id: Mapped[int] = mapped_column(primary_key=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    target_id: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )


class Invitation(Base):
    __tablename__ = "invitations"
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("team_id", "user_id"),)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    opportunity_id: Mapped[int | None] = mapped_column(ForeignKey("opportunities.id"))
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    text: Mapped[str] = mapped_column(String(300), nullable=False)
    read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class MembershipExit(Base):
    __tablename__ = "membership_exits"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id"), nullable=False)
    reason: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
