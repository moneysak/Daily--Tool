"""T2.3: DB-gestützte Sessions (Persistenz, TTL, kein Klartext)."""
import secrets
from datetime import datetime, timedelta


def _new_db():
    from db.database import SessionLocal

    return SessionLocal()


def test_create_and_verify(app_factory, addon_name):
    app_factory(addon_name)
    from auth import create_session_token, verify_session_token

    db = _new_db()
    try:
        token = create_session_token(db)
        assert isinstance(token, str)
        assert len(token) == 64  # token_hex(32)
        assert verify_session_token(db, token) is True
        assert verify_session_token(db, "deadbeef") is False
        assert verify_session_token(db, "") is False
    finally:
        db.close()


def test_revoke_session(app_factory, addon_name):
    app_factory(addon_name)
    from auth import create_session_token, revoke_session, verify_session_token

    db = _new_db()
    try:
        token = create_session_token(db)
        assert verify_session_token(db, token) is True
        assert revoke_session(db, token) is True
        assert verify_session_token(db, token) is False
        assert revoke_session(db, token) is False
    finally:
        db.close()


def test_expired_token_rejected_and_purged(app_factory, addon_name):
    app_factory(addon_name)
    from auth import hash_token, purge_expired, verify_session_token
    from models.session import AuthSession

    db = _new_db()
    try:
        past = datetime.utcnow() - timedelta(seconds=5)

        expired = secrets.token_hex(32)
        db.add(
            AuthSession(
                token_hash=hash_token(expired),
                created_at=past - timedelta(days=1),
                expires_at=past,
                last_seen=past,
            )
        )
        db.commit()
        # Abgelaufenes Token wird abgelehnt und beim Prüfen entfernt.
        assert verify_session_token(db, expired) is False
        assert db.query(AuthSession).filter_by(token_hash=hash_token(expired)).first() is None

        # Zweite abgelaufene Session -> purge_expired entfernt sie.
        expired2 = secrets.token_hex(32)
        db.add(
            AuthSession(
                token_hash=hash_token(expired2),
                created_at=past - timedelta(days=1),
                expires_at=past,
                last_seen=past,
            )
        )
        db.commit()
        assert purge_expired(db) == 1
        assert db.query(AuthSession).filter_by(token_hash=hash_token(expired2)).first() is None
    finally:
        db.close()


def test_token_not_stored_in_plaintext(app_factory, addon_name):
    app_factory(addon_name)
    from auth import create_session_token, hash_token
    from db.database import DB_PATH

    db = _new_db()
    token = create_session_token(db)
    db.close()

    with open(DB_PATH, "rb") as fh:
        raw = fh.read()
    assert token.encode("utf-8") not in raw
    assert hash_token(token).encode("utf-8") in raw


def test_session_persists_across_app_rebuild(app_factory, addon_name, tmp_path):
    data_dir = tmp_path / "persist"

    app_factory(addon_name, data_dir=data_dir)
    from auth import create_session_token

    db = _new_db()
    token = create_session_token(db)
    db.close()

    # App neu aufbauen (Module werden zurückgesetzt), gleiche DB-Datei.
    app_factory(addon_name, data_dir=data_dir)
    from auth import verify_session_token

    db2 = _new_db()
    try:
        assert verify_session_token(db2, token) is True
    finally:
        db2.close()
