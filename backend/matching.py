"""Simple, explainable profile and team matching."""

from datetime import date, timedelta

WEIGHTS = {
    "hackathon": {"category": 20, "topics": 25, "skills": 40, "course": 0, "experience": 15},
    "course_project": {"category": 20, "topics": 15, "skills": 25, "course": 35, "experience": 5},
    "study_group": {"category": 20, "topics": 20, "skills": 10, "course": 45, "experience": 5},
    "trek_sport": {"category": 20, "topics": 40, "skills": 10, "course": 0, "experience": 30},
}


def overlap(wanted, offered):
    wanted = {str(item).strip().lower() for item in wanted if str(item).strip()}
    offered = {str(item).strip().lower() for item in offered if str(item).strip()}
    return len(wanted & offered) / len(wanted) if wanted else None


def band(score):
    return "High" if score >= 70 else "Medium" if score >= 40 else "Low"


def report(factors, weights):
    active = {key: value for key, value in factors.items() if value is not None and weights.get(key)}
    possible = sum(weights[key] for key in active)
    score = round(sum(weights[key] * value for key, value in active.items()) / possible * 100) if possible else 0
    details = [
        {"factor": key.replace("_", " ").title(), "matched": round(value * 100), "weight": weights[key]}
        for key, value in active.items()
    ]
    return {
        "score": score, "band": band(score), "breakdown": details,
        "explanation": [f"{item['factor']}: {item['matched']}% match" for item in details] or ["Add profile details to improve this estimate"],
        "guidance": True,
    }


def activity_match(user, opportunity):
    factors = {
        "category": overlap([opportunity.category], user.interests),
        "topics": overlap(opportunity.topics or [], user.topics),
        "skills": overlap(opportunity.skills or [], user.skills),
        "course": overlap([opportunity.course] if opportunity.course else [], user.courses),
        "experience": overlap(opportunity.experience or [], user.experience),
    }
    return report(factors, WEIGHTS[opportunity.category])


def listed_dates(schedule):
    if not schedule or schedule.get("kind") == "undecided" or not schedule.get("start_date"):
        return []
    start = date.fromisoformat(schedule["start_date"])
    if schedule.get("kind") == "single":
        return [start.isoformat()]
    end = date.fromisoformat(schedule.get("end_date") or schedule["start_date"])
    days = (end - start).days
    if days < 0 or days > 365:
        return []
    dates = [start + timedelta(days=i) for i in range(days + 1)]
    if schedule.get("kind") == "recurring":
        dates = [day for day in dates if day.weekday() in schedule.get("weekdays", [])]
    return [day.isoformat() for day in dates]


def date_fit(schedule, answers):
    schedule = schedule or {}
    if schedule.get("kind", "undecided") == "undecided":
        return {"status": "no_restriction", "overlap": None, "missing": []}
    if not answers:
        return {"status": "not_confirmed", "overlap": None, "missing": []}
    listed = listed_dates(schedule)
    chosen = set(answers.get("dates") or [])
    if schedule.get("kind") == "recurring":
        chosen.update(day for day in listed if date.fromisoformat(day).weekday() in (answers.get("weekdays") or []))
    required = set(schedule.get("required_dates") or [])
    if schedule.get("kind") == "recurring":
        required.update(day for day in listed if date.fromisoformat(day).weekday() in (schedule.get("required_weekdays") or []))
    missing = sorted(required - chosen)
    return {
        "status": "ineligible" if missing else "confirmed",
        "overlap": len(chosen.intersection(listed)) / len(listed) if listed else None,
        "missing": missing,
    }


def eligibility_reasons(user, team, opportunity, answers=None):
    fit = date_fit(team.schedule or opportunity.schedule, answers)
    return ["required_dates"] if fit["status"] == "ineligible" else []


def score_match(user, team, opportunity, answers=None):
    activity = activity_match(user, opportunity)
    factors = {
        "activity": activity["score"] / 100,
        "skills": overlap(team.skills or [], user.skills),
        "course": overlap([team.course] if team.course else [], user.courses),
        "experience": overlap(team.experience or [], user.experience),
    }
    weights = {"activity": 40, "skills": 45, "course": 10, "experience": 5}
    fit = date_fit(team.schedule or opportunity.schedule, answers)
    if fit["overlap"] is not None:
        factors["optional_dates"] = fit["overlap"]
        weights["optional_dates"] = 10
    result = report(factors, weights)
    result["date_status"] = fit["status"]
    result["missing_required_dates"] = fit["missing"]
    return result
