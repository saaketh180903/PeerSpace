"""Inputs accepted by the API."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Category = Literal["hackathon", "course_project", "study_group", "trek_sport"]


class Signup(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("display_name")
    @classmethod
    def name_not_blank(cls, value):
        if not value.strip():
            raise ValueError("Enter a name")
        return value.strip()

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        value = value.strip().lower()
        if (
            value.count("@") != 1
            or any(not part for part in value.split("@"))
            or " " in value
        ):
            raise ValueError("Enter a valid email address")
        return value


class Login(BaseModel):
    email: str
    password: str


class Profile(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    skills: dict[str, int] = Field(default_factory=dict)
    interests: list[str] = Field(default_factory=list)
    availability: list[str] = Field(default_factory=list)
    available_dates: list[date] = Field(default_factory=list)
    courses: list[str] = Field(default_factory=list)
    experience: list[str] = Field(default_factory=list)
    contact: str | None = Field(default=None, max_length=320)

    @field_validator("display_name")
    @classmethod
    def name_not_blank(cls, value):
        if not value.strip():
            raise ValueError("Enter a name")
        return value.strip()

    @field_validator("skills")
    @classmethod
    def valid_skills(cls, value):
        if any(
            not name.strip() or level < 1 or level > 5 for name, level in value.items()
        ):
            raise ValueError("Skills must have a name and a level from 1 to 5")
        return value


class OpportunityInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    category: Category
    organizer: str | None = Field(default=None, max_length=200)
    official_url: str | None = Field(default=None, max_length=2048)
    event_date: date | None = None
    confirm_similar: bool = False

    @field_validator("title", "description")
    @classmethod
    def required_text(cls, value):
        if not value.strip():
            raise ValueError("This field cannot be blank")
        return value.strip()


class TeamInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    capacity: int = Field(ge=1, le=100)
    skills: dict[str, int] = Field(default_factory=dict)
    availability: list[str] = Field(default_factory=list)
    availability_required: bool = False
    course: str | None = None
    experience: list[str] = Field(default_factory=list)
    group_link: str | None = Field(default=None, max_length=2048)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value):
        if not value.strip():
            raise ValueError("Enter a team name")
        return value.strip()

    @field_validator("skills")
    @classmethod
    def valid_skills(cls, value):
        if any(
            not name.strip() or level < 1 or level > 5 for name, level in value.items()
        ):
            raise ValueError("Skills must have a name and a level from 1 to 5")
        return value


class MessageInput(BaseModel):
    text: str = Field(min_length=1, max_length=4000)

    @field_validator("text")
    @classmethod
    def message_not_blank(cls, value):
        if not value.strip():
            raise ValueError("Enter a message")
        return value.strip()


class ReportInput(BaseModel):
    target_type: Literal["profile", "opportunity"]
    target_id: int
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def reason_not_blank(cls, value):
        if not value.strip():
            raise ValueError("Enter a reason")
        return value.strip()
