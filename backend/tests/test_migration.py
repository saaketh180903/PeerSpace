"""The startup upgrade keeps old accounts, teams, requests and event dates."""

import json
import sqlite3

from sqlalchemy import create_engine

from backend.migrate import migrate


def test_old_sqlite_data_is_upgraded_without_loss(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE users (id INTEGER PRIMARY KEY, skills JSON NOT NULL);
            CREATE TABLE opportunities (id INTEGER PRIMARY KEY, event_date TEXT);
            CREATE TABLE teams (id INTEGER PRIMARY KEY, opportunity_id INTEGER, skills JSON NOT NULL);
            CREATE TABLE interests (id INTEGER PRIMARY KEY);
            CREATE TABLE join_requests (id INTEGER PRIMARY KEY, status TEXT);
            INSERT INTO users VALUES (1, '{"Python": 4, "Design": 2}');
            INSERT INTO opportunities VALUES (1, '2026-11-21');
            INSERT INTO opportunities VALUES (2, NULL);
            INSERT INTO teams VALUES (1, 1, '{"Python": 3}');
            INSERT INTO teams VALUES (2, 2, '{}');
            INSERT INTO interests VALUES (1);
            INSERT INTO join_requests VALUES (1, 'pending');
        """)
    engine = create_engine(f"sqlite:///{path}")
    migrate(engine)
    migrate(engine)  # Running it again must be safe.
    engine.dispose()
    with sqlite3.connect(path) as db:
        assert json.loads(db.execute("SELECT skills FROM users").fetchone()[0]) == ["Python", "Design"]
        assert json.loads(db.execute("SELECT skills FROM teams").fetchone()[0]) == ["Python"]
        assert json.loads(db.execute("SELECT schedule FROM opportunities").fetchone()[0])["required_dates"] == ["2026-11-21"]
        assert json.loads(db.execute("SELECT schedule FROM opportunities WHERE id=2").fetchone()[0])["kind"] == "undecided"
        assert json.loads(db.execute("SELECT schedule FROM teams WHERE id=2").fetchone()[0])["kind"] == "undecided"
        assert db.execute("SELECT status FROM join_requests").fetchone()[0] == "pending"
        assert db.execute("SELECT count(*) FROM interests").fetchone()[0] == 1
