"""Small, repeatable SQLite upgrade for the profile and team redesign."""

import json

from sqlalchemy import inspect, text


COLUMNS = {
    "users": {
        "bio": "TEXT NOT NULL DEFAULT ''",
        "topics": "JSON NOT NULL DEFAULT '[]'",
    },
    "opportunities": {
        "topics": "JSON NOT NULL DEFAULT '[]'",
        "skills": "JSON NOT NULL DEFAULT '[]'",
        "course": "VARCHAR(120)",
        "experience": "JSON NOT NULL DEFAULT '[]'",
        "eligibility": "TEXT NOT NULL DEFAULT ''",
        "schedule": "JSON NOT NULL DEFAULT '{}'",
    },
    "interests": {"date_answers": "JSON NOT NULL DEFAULT '{}'"},
    "teams": {
        "goal": "TEXT NOT NULL DEFAULT ''",
        "schedule": "JSON NOT NULL DEFAULT '{}'",
        "question": "TEXT NOT NULL DEFAULT ''",
        "closed": "BOOLEAN NOT NULL DEFAULT 0",
    },
    "join_requests": {
        "date_answers": "JSON NOT NULL DEFAULT '{}'",
        "motivation": "TEXT NOT NULL DEFAULT ''",
        "question_answer": "TEXT NOT NULL DEFAULT ''",
    },
}


def migrate(engine):
    if engine.dialect.name != "sqlite":
        return
    existing_tables = set(inspect(engine).get_table_names())
    with engine.begin() as connection:
        for table, columns in COLUMNS.items():
            if table not in existing_tables:
                continue
            existing_columns = {
                column["name"] for column in inspect(connection).get_columns(table)
            }
            for name, definition in columns.items():
                if name not in existing_columns:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))
        if "users" in existing_tables:
            for user_id, skills in connection.execute(text("SELECT id, skills FROM users")):
                value = json.loads(skills) if isinstance(skills, str) else skills
                if isinstance(value, dict):
                    connection.execute(
                        text("UPDATE users SET skills=:skills WHERE id=:id"),
                        {"skills": json.dumps(list(value)), "id": user_id},
                    )
        if "teams" in existing_tables:
            for team_id, skills in connection.execute(text("SELECT id, skills FROM teams")):
                value = json.loads(skills) if isinstance(skills, str) else skills
                if isinstance(value, dict):
                    connection.execute(
                        text("UPDATE teams SET skills=:skills WHERE id=:id"),
                        {"skills": json.dumps(list(value)), "id": team_id},
                    )
        if "opportunities" in existing_tables:
            connection.execute(
                text("""
                    UPDATE opportunities
                    SET schedule = json_object('kind', 'single', 'start_date', event_date,
                                               'required_dates', json_array(event_date))
                    WHERE event_date IS NOT NULL AND schedule = '{}'
                """)
            )
