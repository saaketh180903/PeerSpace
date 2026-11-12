"""Compare matching strategies using reproducible synthetic data.

Run with `python -m backend.evaluation`. These results are illustrative; they
do not establish compatibility or real-world adoption.
"""

import random
from statistics import mean, stdev
from types import SimpleNamespace

from .matching import score_match

SKILLS = ["python", "design", "writing", "research"]
CATEGORIES = ["hackathon", "course_project", "study_group", "trek_sport"]


def make_data(seed):
    randomizer = random.Random(seed)
    users = []
    for _ in range(16):
        skill = randomizer.choice(SKILLS)
        users.append(
            SimpleNamespace(
                skills=[skill],
                interests=[randomizer.choice(CATEGORIES)],
                topics=[randomizer.choice(["AI", "climate", "outdoors"])],
                courses=[randomizer.choice(["CS101", "EE101"])],
                experience=[randomizer.choice(["hiking", "beginner"])],
            )
        )
    groups = []
    for index, category in enumerate(CATEGORIES):
        team = SimpleNamespace(
            skills=[SKILLS[index]],
            schedule={"kind": "undecided"},
            course="CS101",
            experience=["hiking"],
        )
        groups.append((team, SimpleNamespace(
            category=category, topics=["AI"], skills=[SKILLS[index]],
            course="CS101", experience=["hiking"], schedule={"kind": "undecided"}
        )))
    return users, groups


def run_strategy(users, groups, strategy, seed):
    remaining = list(users)
    randomizer = random.Random(seed)
    scores = []
    for team, opportunity in groups:
        for _ in range(3):
            if not remaining:
                break
            if strategy == "random":
                person = randomizer.choice(remaining)
            elif strategy == "first_come":
                person = remaining[0]
            else:
                person = max(
                    remaining,
                    key=lambda user: score_match(user, team, opportunity)["score"],
                )
            scores.append(score_match(person, team, opportunity)["score"])
            remaining.remove(person)
    return mean(scores) if scores else 0


def summarize(values):
    # Student's t critical value for 29 degrees of freedom, two-sided 95% CI.
    margin = 2.045 * stdev(values) / len(values) ** 0.5
    return {
        "mean_score": round(mean(values), 4),
        "ci_95_low": round(mean(values) - margin, 4),
        "ci_95_high": round(mean(values) + margin, 4),
        "runs": len(values),
    }


def evaluate():
    results = {"random": [], "first_come": [], "peerspace": []}
    for seed in range(30):
        users, groups = make_data(seed)
        for strategy in results:
            results[strategy].append(run_strategy(users, groups, strategy, seed))
    return {strategy: summarize(values) for strategy, values in results.items()}


if __name__ == "__main__":
    print("Synthetic demonstration only; score is the same rule used for ranking.")
    for strategy, result in evaluate().items():
        print(strategy, result)
