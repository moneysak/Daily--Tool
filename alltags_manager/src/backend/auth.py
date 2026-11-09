import hashlib
import json
import os
import secrets
import time
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from db.database import get_db
from models.session import AuthSession

security = HTTPBearer(auto_error=False)

# Lebensdauer einer Login-Session.
SESSION_TTL_DAYS = 30

# Add-on-Optionen (HA Supervisor schreibt sie hierhin). Überschreibbar via
# ALLTAGS_OPTIONS_PATH, z.B. für Tests.
DEFAULT_OPTIONS_PATH = "/data/options.json"

# Nur von dieser Client-IP wird der Ingress-Header X-Ingress-Path vertraut.
# HA-Ingress spricht den Add-on-Container standardmäßig von 172.30.32.2 an.
DEFAULT_TRUSTED_INGRESS_IPS = "172.30.32.2"

# --- Einfaches In-Memory-Rate-Limit für Login-Versuche ---
# Maximal LOGIN_MAX_FAILURES Fehlversuche pro Client-IP innerhalb von
# LOGIN_WINDOW_SECONDS. Bewusst in-memory und ohne externes Dependency; der
# Zustand geht bei einem Add-on-Neustart verloren, was für einen persönlichen
# Brute-Force-Schutz ausreicht. Erfolgreiche Logins setzen den Zähler zurück.
LOGIN_MAX_FAILURES = 5
LOGIN_WINDOW_SECONDS = 15 * 60

# IP -> (Fehlversuchs-Zähler, Fensterstart als monotone Zeit).
_login_failures: dict = {}


def client_ip(request: Request) -> str:
    """Liefert die Client-IP des Requests (Fallback: "unknown")."""
    return request.client.host if request.client else "unknown"


def _failure_bucket(ip: str, now: float):
    """Aktueller (Zähler, Fensterstart) einer IP, abgelaufenes Fenster zurückgesetzt."""
    entry = _login_failures.get(ip)
    if entry is None or now - entry[1] >= LOGIN_WINDOW_SECONDS:
        return 0, now
    return entry


def is_login_rate_limited(ip: str) -> bool:
    """True, wenn die IP im aktuellen Fenster das Fehlversuchs-Limit erreicht hat."""
    count, _ = _failure_bucket(ip, time.monotonic())
    return count >= LOGIN_MAX_FAILURES


def register_login_failure(ip: str) -> None:
    """Zählt einen Fehlversuch für die IP (im aktuellen 15-Minuten-Fenster)."""
    now = time.monotonic()
    count, start = _failure_bucket(ip, now)
    _login_failures[ip] = (count + 1, start)


def reset_login_failures(ip: str) -> None:
    """Löscht die Fehlversuche einer IP (nach erfolgreichem Login)."""
    _login_failures.pop(ip, None)


def _options_path() -> str:
    return os.environ.get("ALLTAGS_OPTIONS_PATH", DEFAULT_OPTIONS_PATH)


def get_configured_password() -> str:
    """Liest das konfigurierte Passwort.

    Reihenfolge: Umgebungsvariable ``APP_PASSWORD`` (von HA Supervisor
    gemappt) hat Vorrang, danach ``app_password`` aus der Add-on-Optionen-Datei
    (Standard ``/data/options.json``, überschreibbar via
    ``ALLTAGS_OPTIONS_PATH``). Ein leerer Rückgabewert bedeutet offener Modus.
    """
    env_pw = os.environ.get("APP_PASSWORD", "")
    if env_pw.strip():
        return env_pw.strip()

    path = _options_path()
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as handle:
                options = json.load(handle)
            value = options.get("app_password")
            if value is not None:
                return str(value).strip()
    except Exception:
        pass
    return ""


def hash_secret(secret: str) -> str:
    """SHA-256-Hex-Hash eines Secrets.

    Bewusste Design-Entscheidung: **kein Salt**. Das Ergebnis dient
    ausschließlich dem konstantzeitlichen Vergleich gegen genau ein
    konfiguriertes Passwort (``secrets.compare_digest``) und wird nicht in
    einer Benutzer-Datenbank persistiert. Ein Salt müsste zusammen mit dem
    Hash offenliegen und brächte hier daher keinen Sicherheitsgewinn.
    """
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def is_open_mode() -> bool:
    """Offener Modus: es ist kein Passwort konfiguriert."""
    return not get_configured_password()


def verify_password(candidate: str) -> bool:
    """Vergleicht den Kandidaten konstantzeitlich mit dem konfigurierten Passwort.

    Gibt immer ``False`` zurück, wenn kein Passwort konfiguriert ist (offener
    Modus wird an anderer Stelle behandelt, nicht hier).
    """
    configured = get_configured_password()
    if not configured:
        return False
    return secrets.compare_digest(hash_secret(candidate or ""), hash_secret(configured))


def hash_token(token: str) -> str:
    """SHA-256-Hex-Hash eines Session-Tokens (für den DB-Lookup)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session_token(db: Session) -> str:
    """Erzeugt ein neues Session-Token und speichert nur dessen Hash.

    Rückgabe: der Klartext-Token — er wird **nur hier** ausgegeben und niemals
    in der Datenbank abgelegt.
    """
    token = secrets.token_hex(32)
    now = datetime.utcnow()
    db.add(
        AuthSession(
            token_hash=hash_token(token),
            created_at=now,
            expires_at=now + timedelta(days=SESSION_TTL_DAYS),
            last_seen=now,
        )
    )
    db.commit()
    return token


def verify_session_token(db: Session, token: str) -> bool:
    """Prüft ein Token gegen die DB und aktualisiert ``last_seen``.

    Abgelaufene Sessions werden abgelehnt und entfernt.
    """
    if not token:
        return False

    session = (
        db.query(AuthSession)
        .filter(AuthSession.token_hash == hash_token(token))
        .first()
    )
    if not session:
        return False

    now = datetime.utcnow()
    if session.expires_at and session.expires_at < now:
        db.delete(session)
        db.commit()
        return False

    session.last_seen = now
    db.commit()
    return True


def revoke_session(db: Session, token: str) -> bool:
    """Widerruft ein Session-Token (Logout). True, wenn etwas gelöscht wurde."""
    if not token:
        return False
    deleted = (
        db.query(AuthSession)
        .filter(AuthSession.token_hash == hash_token(token))
        .delete()
    )
    db.commit()
    return bool(deleted)


def purge_expired(db: Session) -> int:
    """Entfernt alle abgelaufenen Sessions. Rückgabe: Anzahl gelöschter Zeilen."""
    deleted = (
        db.query(AuthSession)
        .filter(AuthSession.expires_at < datetime.utcnow())
        .delete()
    )
    db.commit()
    return deleted


def _trusted_ingress_ips() -> set:
    raw = os.environ.get("ALLTAGS_INGRESS_TRUSTED_IPS", DEFAULT_TRUSTED_INGRESS_IPS)
    return {ip.strip() for ip in raw.split(",") if ip.strip()}


def _is_trusted_ingress(request: Request) -> bool:
    """True, wenn X-Ingress-Path gesetzt ist UND die Client-IP vertrauenswürdig.

    Der Header allein genügt nicht: Auf den Standalone-Ports könnte ihn jeder
    setzen. Nur der HA-Ingress (bekannte IP) wird automatisch durchgelassen.
    """
    header = request.headers.get("X-Ingress-Path") or request.headers.get("x-ingress-path")
    if not header:
        return False
    client_ip = request.client.host if request.client else None
    return client_ip in _trusted_ingress_ips()


def _extract_token(
    request: Request, credentials: HTTPAuthorizationCredentials
) -> str:
    if credentials and credentials.credentials:
        return credentials.credentials
    return request.headers.get("X-Auth-Token", "")


async def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: Session = Depends(get_db),
):
    """Auth-Dependency für alle geschützten Endpunkte.

    Reihenfolge:
    1. Vertrauenswürdiger HA-Ingress (Header X-Ingress-Path + bekannte IP).
    2. Offener Modus (kein Passwort konfiguriert).
    3. Gültiges Session-Token (Bearer-Header oder X-Auth-Token) aus der DB.

    Ein Klartext-Passwort wird als Token **nicht** mehr akzeptiert.
    """
    if _is_trusted_ingress(request):
        return {
            "auth": "ingress",
            "user": request.headers.get("X-Hass-User-ID", "ha_user"),
        }

    if is_open_mode():
        return {"auth": "open", "user": "default"}

    token = _extract_token(request, credentials)
    if token and verify_session_token(db, token):
        return {"auth": "token", "user": "authenticated"}

    raise HTTPException(
        status_code=401,
        detail="Authentifizierung erforderlich. Bitte einloggen.",
        headers={"WWW-Authenticate": "Bearer"},
    )
