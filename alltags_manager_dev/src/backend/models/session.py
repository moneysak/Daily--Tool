from datetime import datetime

from sqlalchemy import Column, DateTime, String

from db.database import Base


class AuthSession(Base):
    """Persistente Login-Session.

    Es wird ausschließlich der SHA-256-Hash des Tokens gespeichert
    (``token_hash`` als Primärschlüssel), nie der Klartext-Token. Das Token
    selbst liegt nur beim Client und wird dort bei jeder Anfrage mitgeschickt.
    """

    __tablename__ = "sessions"

    token_hash = Column(String, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    last_seen = Column(DateTime, default=datetime.utcnow, nullable=False)
