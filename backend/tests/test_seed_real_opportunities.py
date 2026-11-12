from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from backend import seed_real_opportunities as seed
from backend.database import Base
from backend.models import Interest, Membership, Opportunity, Team, User


def test_seed_is_idempotent_and_preserves_existing_data(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(seed, "DATABASE_URL", "sqlite:///./test.db")
    engine = create_engine("sqlite:///./test.db")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(
        seed, "SessionLocal", sessionmaker(bind=engine, expire_on_commit=False)
    )
    with Session(engine) as db:
        db.add(
            User(
                email="existing@example.com",
                display_name="Existing user",
                password_hash="unchanged",
            )
        )
        db.commit()

    seed.seed()
    seed.seed()

    with Session(engine) as db:
        existing = db.scalar(select(User).where(User.email == "existing@example.com"))
        assert existing.display_name == "Existing user"
        assert existing.password_hash == "unchanged"
        assert len(db.scalars(select(User)).all()) == 9
        assert len(db.scalars(select(Opportunity)).all()) == 5
        assert len(db.scalars(select(Team)).all()) == 5
        assert len(db.scalars(select(Membership)).all()) == 5
        assert len(db.scalars(select(Interest)).all()) == 3
        assert all(team.name.startswith("[DEMO]") for team in db.scalars(select(Team)))
    assert len(list(tmp_path.glob("test-backup-*.db"))) == 2
    engine.dispose()
