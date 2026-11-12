"""Inputs accepted by the API."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Category = Literal["hackathon", "course_project", "study_group", "trek_sport"]


class Signup(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    bio: str = Field(min_length=20, max_length=500)
    interests: list[Category] = Field(min_length=1)
    skills: list[str] = Field(min_length=1)
    topics: list[str] = Field(default_factory=list)
    courses: list[str] = Field(default_factory=list)
    experience: list[str] = Field(default_factory=list)

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

    @field_validator("skills")
    @classmethod
    def signup_skills(cls, value):
        names = list(dict.fromkeys(name.strip() for name in value if name.strip()))
        if not names or any(len(name) > 60 for name in names):
            raise ValueError("Enter at least one skill name, up to 60 characters")
        return names


class Login(BaseModel):
    email: str
    password: str


class Profile(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    bio: str = Field(min_length=20, max_length=500)
    skills: list[str] = Field(min_length=1)
    interests: list[Category] = Field(min_length=1)
    topics: list[str] = Field(default_factory=list)
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
        if any(not name.strip() or len(name) > 60 for name in value):
            raise ValueError("Enter skill names up to 60 characters")
        return list(dict.fromkeys(name.strip() for name in value))


class Schedule(BaseModel):
    kind: Literal["undecided", "single", "range", "recurring"] = "undecided"
    start_date: date | None = None
    end_date: date | None = None
    weekdays: list[int] = Field(default_factory=list)
    required_dates: list[date] = Field(default_factory=list)
    required_weekdays: list[int] = Field(default_factory=list)
    time_window: str = Field(default="", max_length=100)

    @field_validator("weekdays", "required_weekdays")
    @classmethod
    def valid_weekdays(cls, value):
        if any(day < 0 or day > 6 for day in value):
            raise ValueError("Weekdays must be 0 (Monday) through 6 (Sunday)")
        return sorted(set(value))

    def normalized(self):
        if self.kind != "undecided" and not self.start_date:
            raise ValueError("Choose a start date")
        if self.kind in ("range", "recurring"):
            if not self.end_date or self.end_date < self.start_date:
                raise ValueError("Choose an end date after the start date")
            if (self.end_date - self.start_date).days > 365:
                raise ValueError("A schedule may span up to one year")
        if self.kind == "recurring" and not self.weekdays:
            raise ValueError("Choose at least one recurring weekday")
        if self.kind == "single" and self.required_dates and self.required_dates != [self.start_date]:
            raise ValueError("Required date must match the activity date")
        if self.kind == "recurring" and not set(self.required_weekdays) <= set(self.weekdays):
            raise ValueError("Required weekdays must be listed weekdays")
        if self.kind == "range" and any(
            day < self.start_date or day > self.end_date for day in self.required_dates
        ):
            raise ValueError("Required dates must be within the date range")
        return self.model_dump(mode="json")


class DateAnswers(BaseModel):
    dates: list[date] = Field(default_factory=list)
    weekdays: list[int] = Field(default_factory=list)


class InterestInput(BaseModel):
    date_answers: DateAnswers = Field(default_factory=DateAnswers)


class JoinInput(InterestInput):
    motivation: str = Field(default="", max_length=1000)
    question_answer: str = Field(default="", max_length=1000)


class OpportunityInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    category: Category
    organizer: str | None = Field(default=None, max_length=200)
    official_url: str | None = Field(default=None, max_length=2048)
    event_date: date | None = None
    topics: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    course: str | None = None
    experience: list[str] = Field(default_factory=list)
    eligibility: str = Field(default="", max_length=2000)
    schedule: Schedule = Field(default_factory=Schedule)
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
    skills: list[str] = Field(default_factory=list)
    goal: str = Field(default="", max_length=1000)
    schedule: Schedule = Field(default_factory=Schedule)
    question: str = Field(default="", max_length=500)
    course: str | None = None
    experience: list[str] = Field(default_factory=list)
    group_link: str | None = Field(default=None, max_length=2048)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value):
        if not value.strip():
            raise ValueError("Enter a team name")
        return value.strip()



class MembershipExitInput(BaseModel):
    return_to_pool: bool = False


class OwnerTransferInput(BaseModel):
    user_id: int


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
