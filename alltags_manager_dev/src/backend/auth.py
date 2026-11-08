import os
import secrets
import hashlib
from fastapi import Request, HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer(auto_error=False)

# In-Memory Session Tokens for Standalone Auth
VALID_SESSIONS = set()

def get_configured_password() -> str:
    # Read from Add-on options (mapped to APP_PASSWORD by HA Supervisor) or fallback env
    return os.environ.get("APP_PASSWORD", "").strip()

def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()

def create_session_token() -> str:
    token = secrets.token_hex(32)
    VALID_SESSIONS.add(token)
    return token

def verify_session_token(token: str) -> bool:
    return token in VALID_SESSIONS

async def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    """
    Hybrid-Auth:
    1. If request comes via Home Assistant Ingress (X-Ingress-Path is present), pass automatically.
    2. If no password is configured (standalone dev mode), pass automatically.
    3. Otherwise, check Authorization: Bearer <token> against active sessions or static token.
    """
    configured_pw = get_configured_password()
    
    # 1. HA Ingress Check
    if request.headers.get("X-Ingress-Path") or request.headers.get("x-ingress-path"):
        return {"auth": "ingress", "user": request.headers.get("X-Hass-User-ID", "ha_user")}
        
    # 2. Open Access if no password configured
    if not configured_pw:
        return {"auth": "open", "user": "default"}
        
    # 3. Bearer Token Check
    if credentials and credentials.credentials:
        token = credentials.credentials
        if verify_session_token(token) or token == configured_pw:
            return {"auth": "token", "user": "authenticated"}
            
    # Check session header if passed as X-Auth-Token
    x_auth = request.headers.get("X-Auth-Token")
    if x_auth and (verify_session_token(x_auth) or x_auth == configured_pw):
        return {"auth": "token", "user": "authenticated"}

    raise HTTPException(
        status_code=401,
        detail="Authentifizierung erforderlich. Bitte einloggen.",
        headers={"WWW-Authenticate": "Bearer"}
    )
