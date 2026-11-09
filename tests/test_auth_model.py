"""T2.1: Session-Modell — Tabelle ``sessions`` wird angelegt und ist nutzbar."""
from datetime import datetime, timedelta


def test_sessions_table_is_created(app_factory, addon_name):
    app_factory(addon_name)
    from sqlalchemy import inspect

    from db.database import engine

    assert "sessions" in inspect(engine).get_table_names()


def test_session_row_insert_and_query(app_factory, addon_name):
    app_factory(addon_name)
    from db.database import SessionLocal
    from models.session import AuthSession

    db = SessionLocal()
    try:
        now = datetime.utcnow()
        db.add(
            AuthSession(
                token_hash="abc123",
                created_at=now,
                expires_at=now + timedelta(days=1),
                last_seen=now,
            )
        )
        db.commit()

        row = db.query(AuthSession).filter_by(token_hash="abc123").first()
        assert row is not None
        assert row.expires_at > now
    finally:
        db.close()
