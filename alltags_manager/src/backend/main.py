import os
import re
import json
import httpx
from datetime import date
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from db.database import SessionLocal, engine, Base, get_db, ensure_schema
from crud import task as crud
from crud import overview as crud_overview
from crud import ha as crud_ha
from crud import news as crud_news
from crud import weather as crud_weather
from schemas import task as schemas
from schemas import overview as overview_schemas
from schemas import ha as ha_schemas
from schemas import news as news_schemas
from schemas import weather as weather_schemas
from auth import (
    require_auth,
    get_configured_password,
    get_user_name,
    create_session_token,
    verify_password,
    revoke_session,
    purge_expired,
    is_open_mode,
    client_ip,
    is_login_rate_limited,
    register_login_failure,
    reset_login_failures,
)

# Tabellen erstellen (inkl. sessions), danach Mini-Migration für Alt-DBs.
Base.metadata.create_all(bind=engine)
ensure_schema(engine)

app = FastAPI(title="Alltags-Manager API")

# --- Auth Endpunkte ---
class LoginRequest(BaseModel):
    password: str

@app.get("/api/auth/status")
def auth_status(auth_info: dict = Depends(require_auth)):
    return {"authenticated": True, "type": auth_info["auth"], "user": auth_info["user"]}

@app.post("/api/auth/login")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    # Offener Modus (kein Passwort konfiguriert): Token trotzdem ausstellen.
    if is_open_mode():
        purge_expired(db)
        token = create_session_token(db)
        return {"success": True, "token": token, "message": "Kein Passwort konfiguriert (offener Modus)"}

    # Einfaches In-Memory-Rate-Limit gegen Brute-Force (pro Client-IP).
    ip = client_ip(request)
    if is_login_rate_limited(ip):
        raise HTTPException(
            status_code=429,
            detail="Zu viele Fehlversuche. Bitte in 15 Minuten erneut versuchen.",
        )

    if not verify_password(payload.password):
        register_login_failure(ip)
        raise HTTPException(status_code=401, detail="Falsches Passwort.")

    reset_login_failures(ip)
    purge_expired(db)
    token = create_session_token(db)
    return {"success": True, "token": token}

@app.post("/api/auth/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    """Widerruft das mitgeschickte Session-Token (idempotent)."""
    token = ""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[len("bearer "):].strip()
    if not token:
        token = request.headers.get("X-Auth-Token", "")
    if token:
        revoke_session(db, token)
    return {"success": True}


# --- Tasks API ---
@app.post("/tasks/", response_model=schemas.Task)
def create_task(task: schemas.TaskCreate, db: Session = Depends(get_db), auth: dict = Depends(require_auth)):
    return crud.create_task(db=db, task=task)

@app.get("/tasks/", response_model=list[schemas.Task])
def read_tasks(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), auth: dict = Depends(require_auth)):
    return crud.get_tasks(db, skip=skip, limit=limit)

@app.put("/tasks/{task_id}", response_model=schemas.Task)
def update_task(task_id: int, task: schemas.TaskUpdate, db: Session = Depends(get_db), auth: dict = Depends(require_auth)):
    updated = crud.update_task(db=db, task_id=task_id, task=task)
    if not updated:
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden.")
    return updated

@app.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db), auth: dict = Depends(require_auth)):
    deleted = crud.delete_task(db=db, task_id=task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden.")
    return {"status": "success", "deleted_id": task_id}

# --- Shopping List API ---
@app.get("/api/shopping/", response_model=list[schemas.ShoppingItem])
def read_shopping_items(skip: int = 0, limit: int = 200, db: Session = Depends(get_db), auth: dict = Depends(require_auth)):
    return crud.get_shopping_items(db, skip=skip, limit=limit)

@app.post("/api/shopping/", response_model=schemas.ShoppingItem)
def create_shopping_item(item: schemas.ShoppingItemCreate, db: Session = Depends(get_db), auth: dict = Depends(require_auth)):
    return crud.create_shopping_item(db=db, item=item)

@app.put("/api/shopping/{item_id}", response_model=schemas.ShoppingItem)
def update_shopping_item(item_id: int, item: schemas.ShoppingItemUpdate, db: Session = Depends(get_db), auth: dict = Depends(require_auth)):
    updated = crud.update_shopping_item(db=db, item_id=item_id, item=item)
    if not updated:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden.")
    return updated

@app.delete("/api/shopping/{item_id}")
def delete_shopping_item(item_id: int, db: Session = Depends(get_db), auth: dict = Depends(require_auth)):
    deleted = crud.delete_shopping_item(db=db, item_id=item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden.")
    return {"status": "success", "deleted_id": item_id}

@app.post("/api/shopping/clear-checked")
def clear_checked_shopping(db: Session = Depends(get_db), auth: dict = Depends(require_auth)):
    deleted = crud.clear_checked_shopping_items(db=db)
    return {"status": "success", "deleted_count": deleted}

# --- Routines API ---
@app.get("/api/routines/", response_model=list[schemas.Routine])
def read_routines(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), auth: dict = Depends(require_auth)):
    return crud.get_routines(db, skip=skip, limit=limit)

@app.post("/api/routines/", response_model=schemas.Routine)
def create_routine(routine: schemas.RoutineCreate, db: Session = Depends(get_db), auth: dict = Depends(require_auth)):
    return crud.create_routine(db=db, routine=routine)

@app.put("/api/routines/{routine_id}", response_model=schemas.Routine)
def update_routine(routine_id: int, routine: schemas.RoutineUpdate, db: Session = Depends(get_db), auth: dict = Depends(require_auth)):
    updated = crud.update_routine(db=db, routine_id=routine_id, routine=routine)
    if not updated:
        raise HTTPException(status_code=404, detail="Routine nicht gefunden.")
    return updated

@app.delete("/api/routines/{routine_id}")
def delete_routine(routine_id: int, db: Session = Depends(get_db), auth: dict = Depends(require_auth)):
    deleted = crud.delete_routine(db=db, routine_id=routine_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Routine nicht gefunden.")
    return {"status": "success", "deleted_id": routine_id}

# --- Heute-Übersicht API ---
@app.get("/api/overview", response_model=overview_schemas.Overview)
def read_overview(
    today: Optional[str] = None,
    db: Session = Depends(get_db),
    auth: dict = Depends(require_auth),
):
    """Liefert die aggregierte "Heute"-Übersicht.

    ``today`` (YYYY-MM-DD) ist optional und macht Tests/den Frontend-Aufruf
    deterministisch; ohne Param wird das lokale Serverdatum verwendet.
    """
    if today is None:
        day = crud_overview.local_today()
    else:
        try:
            day = date.fromisoformat(today)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail="Ungültiges Datum. Erwartet wird YYYY-MM-DD.",
            )
    return crud_overview.build_overview(db, day, get_user_name())

# --- Home-Assistant-Integration ---
@app.get("/api/ha/agenda", response_model=ha_schemas.AgendaResponse)
async def read_ha_agenda(
    today: Optional[str] = None,
    auth: dict = Depends(require_auth),
):
    """Termine aller konfigurierten HA-Kalender für einen Tag.

    Liefert immer HTTP 200; ``available=False`` bei fehlendem Token, leerer
    Konfiguration oder HA-Ausfall.
    """
    if today is None:
        day = crud_overview.local_today()
    else:
        try:
            day = date.fromisoformat(today)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail="Ungültiges Datum. Erwartet wird YYYY-MM-DD.",
            )
    try:
        data = await crud_ha.fetch_agenda(day)
    except crud_ha.HAUnavailable:
        return ha_schemas.AgendaResponse(available=False, date=day, events=[])
    return ha_schemas.AgendaResponse(**data)


@app.get("/api/ha/todos", response_model=ha_schemas.TodosResponse)
async def read_ha_todos(auth: dict = Depends(require_auth)):
    """Offene Items aller konfigurierten HA-To-do-Listen."""
    try:
        data = await crud_ha.fetch_todos(kind="today_todo")
    except crud_ha.HAUnavailable:
        return ha_schemas.TodosResponse(available=False, lists=[])
    return ha_schemas.TodosResponse(**data)


@app.post("/api/ha/todos/item")
async def toggle_ha_todo(
    payload: ha_schemas.TodoToggle,
    auth: dict = Depends(require_auth),
):
    """Hakt ein HA-To-do-Item ab bzw. setzt es zurück (Rückschreiben nach HA)."""
    if payload.entity_id not in crud_ha.get_configured_entities("today_todo"):
        raise HTTPException(status_code=403, detail="Entity ist nicht freigegeben.")
    try:
        await crud_ha.set_todo_status(payload.entity_id, payload.uid, payload.completed)
    except crud_ha.HAUnavailable:
        raise HTTPException(status_code=503, detail="Home Assistant ist nicht verfügbar.")
    except crud_ha.HARejected as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Home Assistant hat die Anfrage abgelehnt: {exc}",
        )
    return {"status": "success"}


@app.get("/api/ha/todos/lists", response_model=List[ha_schemas.TodoListSummary])
async def list_ha_todo_lists(auth: dict = Depends(require_auth)):
    """Liefert Übersicht aller konfigurierten To-do-Listen (entity_id und Name)."""
    try:
        return await crud_ha.fetch_todo_lists_summary(kind="shopping_todo")
    except crud_ha.HAUnavailable:
        raise HTTPException(status_code=503, detail="Home Assistant ist nicht verfügbar.")
    except crud_ha.HARejected as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Home Assistant hat die Anfrage abgelehnt: {exc}",
        )


@app.get("/api/ha/todos/lists/{entity_id}", response_model=ha_schemas.TodoListResponse)
async def get_ha_todo_list(entity_id: str, auth: dict = Depends(require_auth)):
    """Liefert alle Items einer bestimmten freigegebenen To-do-Liste."""
    if entity_id not in crud_ha.get_configured_entities("shopping_todo"):
        raise HTTPException(status_code=403, detail="Entity ist nicht freigegeben.")
    try:
        return await crud_ha.fetch_single_todo_list(entity_id)
    except crud_ha.HAUnavailable:
        raise HTTPException(status_code=503, detail="Home Assistant ist nicht verfügbar.")
    except crud_ha.HARejected as exc:
        raise HTTPException(status_code=502, detail=f"Home Assistant hat die Anfrage abgelehnt: {exc}")


@app.post("/api/ha/todos/items")
async def create_ha_todo_item(
    payload: ha_schemas.TodoItemCreate,
    auth: dict = Depends(require_auth),
):
    """Erstellt ein neues Item auf der angegebenen HA To-do-Liste."""
    if payload.entity_id not in crud_ha.get_configured_entities("shopping_todo"):
        raise HTTPException(status_code=403, detail="Entity ist nicht freigegeben.")
    try:
        await crud_ha.add_todo_item(payload.entity_id, payload.summary, payload.description)
    except crud_ha.HAUnavailable:
        raise HTTPException(status_code=503, detail="Home Assistant ist nicht verfügbar.")
    except crud_ha.HARejected as exc:
        raise HTTPException(status_code=502, detail=f"Home Assistant hat die Anfrage abgelehnt: {exc}")
    return {"status": "success"}


@app.put("/api/ha/todos/items/{uid}")
async def update_ha_todo_item(
    uid: str,
    payload: ha_schemas.TodoItemUpdate,
    auth: dict = Depends(require_auth),
):
    """Aktualisiert Status oder Titel eines Items auf der angegebenen HA To-do-Liste."""
    if payload.entity_id not in crud_ha.get_configured_entities("shopping_todo"):
        raise HTTPException(status_code=403, detail="Entity ist nicht freigegeben.")
    try:
        await crud_ha.update_todo_item(payload.entity_id, uid, payload.completed, payload.summary)
    except crud_ha.HAUnavailable:
        raise HTTPException(status_code=503, detail="Home Assistant ist nicht verfügbar.")
    except crud_ha.HARejected as exc:
        raise HTTPException(status_code=502, detail=f"Home Assistant hat die Anfrage abgelehnt: {exc}")
    return {"status": "success"}


@app.post("/api/ha/todos/items/delete")
async def delete_ha_todo_items(
    payload: ha_schemas.TodoItemDelete,
    auth: dict = Depends(require_auth),
):
    """Löscht ein oder mehrere Items von der angegebenen HA To-do-Liste."""
    if payload.entity_id not in crud_ha.get_configured_entities("shopping_todo"):
        raise HTTPException(status_code=403, detail="Entity ist nicht freigegeben.")
    try:
        await crud_ha.remove_todo_items(payload.entity_id, payload.uids)
    except crud_ha.HAUnavailable:
        raise HTTPException(status_code=503, detail="Home Assistant ist nicht verfügbar.")
    except crud_ha.HARejected as exc:
        raise HTTPException(status_code=502, detail=f"Home Assistant hat die Anfrage abgelehnt: {exc}")
    return {"status": "success"}


# --- News & Weather Endpunkte ---

@app.get("/api/news/positive", response_model=news_schemas.NewsResponse)
async def get_positive_news(auth: dict = Depends(require_auth)):
    """Liefert die neuesten positiven Nachrichten (GoodNews RSS Feed)."""
    return await crud_news.fetch_positive_news()


@app.get("/api/weather/today", response_model=weather_schemas.WeatherResponse)
async def get_weather_today(auth: dict = Depends(require_auth)):
    """Liefert das heutige Wetter und die Vorhersage aus Home Assistant."""
    return await crud_weather.fetch_weather_today()



# --- Hermes Chat API Proxy ---
class ChatMessage(BaseModel):
    message: str

def get_hermes_api_key() -> str:
    # 1. Aus Umgebungsvariable
    key = os.environ.get("HERMES_API_KEY") or os.environ.get("API_SERVER_KEY")
    if key:
        return key.strip()
    # 2. Aus Add-on /data/options.json
    try:
        if os.path.exists("/data/options.json"):
            with open("/data/options.json", "r", encoding="utf-8") as f:
                opts = json.load(f)
                if opts.get("hermes_api_key"):
                    return str(opts["hermes_api_key"]).strip()
    except Exception:
        pass
    # 3. Aus interner Key-Datei (Host-Mount falls vorhanden)
    key_file = "/data/.ha_api_server_key"
    if os.path.exists(key_file):
        try:
            with open(key_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return ""

def get_hermes_api_url() -> str:
    url = os.environ.get("HERMES_API_URL")
    if url:
        return url.rstrip("/")
    try:
        if os.path.exists("/data/options.json"):
            with open("/data/options.json", "r", encoding="utf-8") as f:
                opts = json.load(f)
                if opts.get("hermes_api_url"):
                    return str(opts["hermes_api_url"]).rstrip("/")
    except Exception:
        pass
    # Standard: Hermes OpenAI API Server auf Port 8642
    # In Docker/HA-Netzwerk kann host.docker.internal, 172.17.0.1 oder 127.0.0.1 zutreffen
    return "http://127.0.0.1:8642/v1"

@app.post("/api/hermes/chat")
async def chat_with_hermes(payload: ChatMessage, auth: dict = Depends(require_auth)):
    api_url = get_hermes_api_url()
    api_key = get_hermes_api_key()

    target_endpoint = f"{api_url}/chat/completions"
    headers = {
        "Content-Type": "application/json"
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    chat_payload = {
        "model": "hermes-agent",
        "messages": [
            {"role": "user", "content": payload.message}
        ]
    }

    # Liste an potentiellen Host-Adressen falls 127.0.0.1 im separaten Container nicht erreichbar ist
    candidate_endpoints = [target_endpoint]
    if "127.0.0.1" in target_endpoint:
        candidate_endpoints.append(target_endpoint.replace("127.0.0.1", "172.17.0.1"))
        candidate_endpoints.append(target_endpoint.replace("127.0.0.1", "host.docker.internal"))

    last_error = None
    async with httpx.AsyncClient(timeout=45.0) as client:
        for endpoint in candidate_endpoints:
            try:
                response = await client.post(endpoint, json=chat_payload, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    # Extrahiere Text aus OpenAI-Format
                    msg_text = ""
                    if "choices" in data and len(data["choices"]) > 0:
                        choice = data["choices"][0]
                        if "message" in choice and "content" in choice["message"]:
                            msg_text = choice["message"]["content"]
                    if not msg_text and "response" in data:
                        msg_text = data["response"]
                    if not msg_text:
                        msg_text = str(data)
                    return {"message": msg_text, "endpoint": endpoint}
                else:
                    last_error = f"HTTP {response.status_code}: {response.text}"
            except Exception as e:
                last_error = str(e)

    raise HTTPException(status_code=502, detail=f"Hermes Agent nicht erreichbar: {last_error}")

# --- Frontend Root Ingress Handler & Static Files ---
FRONTEND_DIR = "/app/src/frontend"
if not os.path.exists(FRONTEND_DIR):
    FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")

# Erlaubtes Ingress-Pfad-Muster: beginnt mit "/", danach nur unkritische Zeichen.
# Verhindert u.a. Ausbruch aus dem JS-String-Literal ("</script>", ";...).
_INGRESS_PATH_RE = re.compile(r"^/[A-Za-z0-9/_\-.]*$")


@app.get("/", response_class=HTMLResponse)
async def serve_index(request: Request):
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if not os.path.exists(index_path):
        raise HTTPException(status_code=404, detail="index.html nicht gefunden.")

    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()

    # HA Ingress Support: X-Ingress-Path nur verwenden, wenn er dem strikten
    # Muster entspricht, sonst leerer Fallback. Einbettung via json.dumps,
    # damit der Wert sicher als JS-String-Literal serialisiert wird.
    raw_ingress_path = request.headers.get("X-Ingress-Path", "").rstrip("/")
    ingress_path = raw_ingress_path if _INGRESS_PATH_RE.match(raw_ingress_path) else ""

    app_config = json.dumps(
        {"INGRESS_PATH": ingress_path, "API_BASE_URL": ingress_path}
    )
    config_script = f"\n    <script>\n      window.APP_CONFIG = {app_config};\n    </script>\n"

    if "</head>" in content:
        content = content.replace("</head>", f"{config_script}\n</head>")
    else:
        content = f"{config_script}\n{content}"

    return HTMLResponse(content=content)

app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=False), name="frontend")
