"""Small local management commands for the course demo.

Run `python -m backend.manage --help` from the repository root.
"""

import argparse
from datetime import date
from html.parser import HTMLParser
import json
import sqlite3
from pathlib import Path
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from fastapi import HTTPException
from sqlalchemy import select

from .database import Base, SessionLocal, engine
from .main import normalize_url
from .migrate import migrate
from .models import Opportunity, User


def import_records(db, records, source, creator):
    added = skipped = 0
    for record in records:
        title = str(record.get("title", "")).strip()
        description = str(record.get("description", "")).strip()
        category = record.get("category")
        if (
            not title
            or not description
            or category
            not in {"hackathon", "course_project", "study_group", "trek_sport"}
        ):
            skipped += 1
            continue
        try:
            url = normalize_url(record.get("official_url"))
            event_date = (
                date.fromisoformat(record["event_date"]).isoformat()
                if record.get("event_date")
                else None
            )
        except (ValueError, TypeError, HTTPException):
            skipped += 1
            continue
        if url and db.scalar(
            select(Opportunity.id).where(Opportunity.official_url == url)
        ):
            skipped += 1
            continue
        db.add(
            Opportunity(
                title=title[:200],
                description=description[:5000],
                category=category,
                source=source,
                official_url=url,
                organizer=record.get("organizer"),
                event_date=event_date,
                schedule=(
                    {"kind": "single", "start_date": event_date, "required_dates": [event_date]}
                    if event_date else {"kind": "undecided"}
                ),
                created_by=creator.id,
            )
        )
        db.flush()
        added += 1
    db.commit()
    return added, skipped


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def rss_records(url, category):
    """Read a public RSS feed chosen and verified by the operator."""
    url = normalize_url(url)
    request = Request(url, headers={"User-Agent": "PeerSpace/1.0 (student project)"})
    with urlopen(request, timeout=15) as response:
        data = response.read(2_000_001)
    if len(data) > 2_000_000:
        raise ValueError("Feed is larger than 2 MB")
    root = ElementTree.fromstring(data)
    records = []
    for item in root.findall("./channel/item"):
        plain = PlainText()
        plain.feed(item.findtext("description") or "")
        records.append(
            {
                "title": item.findtext("title"),
                "description": " ".join(plain.parts).strip()
                or "See the official link for details.",
                "official_url": item.findtext("link"),
                "category": category,
            }
        )
    return records


def main():
    parser = argparse.ArgumentParser(description="PeerSpace local administration")
    commands = parser.add_subparsers(dest="command", required=True)
    backup = commands.add_parser("backup", help="Create a consistent SQLite backup")
    backup.add_argument("path", help="Destination .db file")
    make_admin = commands.add_parser(
        "make-admin", help="Grant admin to an existing account"
    )
    make_admin.add_argument("email")
    curated = commands.add_parser(
        "import-curated", help="Import a JSON array from a local file"
    )
    curated.add_argument("email", help="Existing administrator email")
    curated.add_argument("path", help="Path to JSON file")
    rss = commands.add_parser(
        "import-rss",
        help="Import a public RSS feed after checking permission and relevance",
    )
    rss.add_argument("email", help="Existing administrator email")
    rss.add_argument("url")
    rss.add_argument(
        "category", choices=["hackathon", "course_project", "study_group", "trek_sport"]
    )
    args = parser.parse_args()
    if args.command == "backup":
        source = engine.url.database
        if engine.dialect.name != "sqlite" or not source:
            parser.error("Backup command supports file-based SQLite only")
        destination = Path(args.path)
        if destination.exists():
            parser.error("Backup destination already exists")
        with sqlite3.connect(source) as original, sqlite3.connect(destination) as copy:
            original.backup(copy)
        print(f"Backup saved to {destination}")
        return
    migrate(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == args.email.strip().lower()))
        if not user:
            parser.error("Account not found. Sign up first.")
        if args.command == "make-admin":
            user.is_admin = True
            db.commit()
            print("Administrator access granted.")
            return
        if not user.is_admin:
            parser.error("This command requires an administrator account.")
        if args.command == "import-curated":
            with open(args.path, encoding="utf-8") as file:
                records = json.load(file)
            if not isinstance(records, list):
                parser.error("The JSON file must contain an array.")
            added, skipped = import_records(db, records, "curated", user)
        else:
            added, skipped = import_records(
                db, rss_records(args.url, args.category), "scraped", user
            )
        print(f"Added {added}; skipped {skipped} invalid or duplicate records.")


if __name__ == "__main__":
    main()
