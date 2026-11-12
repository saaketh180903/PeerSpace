"""Small, transparent ranking rules for the four activity categories."""

WEIGHTS = {
    "hackathon": {
        "skills": 0.5,
        "availability": 0.25,
        "interests": 0.15,
        "course": 0.05,
        "experience": 0.05,
    },
    "course_project": {
        "skills": 0.35,
        "availability": 0.2,
        "interests": 0.1,
        "course": 0.3,
        "experience": 0.05,
    },
    "study_group": {
        "skills": 0.05,
        "availability": 0.35,
        "interests": 0.15,
        "course": 0.4,
        "experience": 0.05,
    },
    "trek_sport": {
        "skills": 0.05,
        "availability": 0.3,
        "interests": 0.15,
        "course": 0.0,
        "experience": 0.5,
    },
}


def overlap(required, offered):
    required = {item.strip().lower() for item in required if item.strip()}
    offered = {item.strip().lower() for item in offered if item.strip()}
    return len(required & offered) / len(required) if required else 0.0


def eligibility_reasons(user, team, opportunity):
    """Explain mandatory requirements that the current profile does not meet."""
    reasons = []
    if opportunity.event_date and opportunity.event_date not in user.available_dates:
        reasons.append("event_date")
    if team.availability_required and not overlap(team.availability, user.availability):
        reasons.append("availability")
    return reasons


def score_match(user, team, opportunity):
    """Return None when a stated mandatory constraint cannot be met."""
    if eligibility_reasons(user, team, opportunity):
        return None
    time_fit = overlap(team.availability, user.availability)
    skills = {name.lower(): level for name, level in user.skills.items()}
    skill_fit = (
        sum(
            min(skills.get(name.lower(), 0) / level, 1)
            for name, level in team.skills.items()
        )
        / len(team.skills)
        if team.skills
        else 0
    )
    factors = {
        "skills": skill_fit,
        "availability": time_fit,
        "interests": overlap([opportunity.category], user.interests),
        "course": overlap([team.course] if team.course else [], user.courses),
        "experience": overlap(team.experience, user.experience),
    }
    breakdown = {
        key: round(value * WEIGHTS[opportunity.category][key], 4)
        for key, value in factors.items()
    }
    return {
        "score": round(sum(breakdown.values()), 4),
        "breakdown": breakdown,
        "explanation": [
            f"{key.title()}: {value:.0%} fit"
            for key, value in factors.items()
            if WEIGHTS[opportunity.category][key]
        ],
    }
