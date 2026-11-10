"""Home-Assistant-Client (Supervisor-Proxy) für Kalender- und To-do-Daten.

Kapselt den httpx-Zugriff auf ``http://supervisor/core/api``. Enthält bewusst
kein FastAPI-Wissen; die Routen liegen in ``main.py``.

Design:
- Nur die in den Add-on-Optionen konfigurierten Entity-IDs sind zulässig
  (Allowlist). Der Supervisor-Token hätte sonst Zugriff auf alle Entities.
- Fehlt ``SUPERVISOR_TOKEN`` (Standalone), schlägt jeder Aufruf mit
  ``HAUnavailable`` fehl; die Routen liefern dann ``available: false``.
- Ein einzelner fehlschlagender Kalender/To-do-Liste wird übersprungen.
"""
import asyncio
import json
import logging
import os
import re
from datetime import date, datetime, time, timedelta, timezone
from typing import List, Optional, Tuple

import httpx

from crud.overview import _local_timezone

logger = logging.getLogger(__name__)

DEFAULT_HA_BASE_URL = "http://supervisor/core/api"
DEFAULT_OPTIONS_PATH = "/data/options.json"

# 5 s Timeout pro Request (parallel über alle Entities).
HA_TIMEOUT = 5.0

_CALENDAR_RE = re.compile(r"^calendar\.[a-zA-Z0-9_\-\.]+$")
_TODO_RE = re.compile(r"^todo\.[a-zA-Z0-9_\-\.]+$")

_KIND_CONFIG = {
    "calendar": {
        "env": "ALLTAGS_CALENDAR_ENTITIES",
        "option": "calendar_entities",
        "regex": _CALENDAR_RE,
    },
    "todo": {
        "env": "ALLTAGS_TODO_ENTITIES",
        "option": "todo_entities",
        "regex": _TODO_RE,
    },
    "today_todo": {
        "env": "ALLTAGS_TODAY_TODO_ENTITIES",
        "option": "today_todo_entities",
        "regex": _TODO_RE,
    },
    "shopping_todo": {
        "env": "ALLTAGS_SHOPPING_TODO_ENTITIES",
        "option": "shopping_todo_entities",
        "regex": _TODO_RE,
    },
}


class HAUnavailable(Exception):
    """Kein Token / Netzfehler / 401 / Timeout -> HA gilt als nicht verfügbar."""


class HARejected(Exception):
    """HA hat den (Schreib-)Service-Call abgelehnt (4xx/5xx)."""


# --- Konfiguration ---------------------------------------------------------

def _options_path() -> str:
    return os.environ.get("ALLTAGS_OPTIONS_PATH", DEFAULT_OPTIONS_PATH)


def _read_options() -> dict:
    path = _options_path()
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def get_ha_token() -> Optional[str]:
    """Liefert den Supervisor-Token aus der Env, oder ``None`` (Standalone)."""
    token = os.environ.get("SUPERVISOR_TOKEN", "")
    token = token.strip()
    return token or None


def get_ha_base_url() -> str:
    """Basis-URL des Supervisor-Proxy (Override ``ALLTAGS_HA_BASE_URL`` für Tests)."""
    url = os.environ.get("ALLTAGS_HA_BASE_URL") or DEFAULT_HA_BASE_URL
    return url.rstrip("/")


def _get_direct_configured_entities(kind: str) -> List[str]:
    """Liest und validiert die Entity-Liste für einen einzelnen Key ohne Fallback."""
    cfg = _KIND_CONFIG.get(kind)
    if cfg is None:
        return []

    raw_env = os.environ.get(cfg["env"])
    if raw_env is not None:
        values = raw_env.split(",")
    else:
        value = _read_options().get(cfg["option"])
        if isinstance(value, list):
            values = value
        elif isinstance(value, str):
            values = value.split(",")
        else:
            values = []

    regex = cfg["regex"]
    result: List[str] = []
    for item in values:
        if not isinstance(item, str):
            continue
        entity_id = item.strip()
        if not entity_id or not regex.match(entity_id):
            continue
        if entity_id not in result:
            result.append(entity_id)
    return result


def get_configured_entities(kind: str) -> List[str]:
    """Liefert die validierte, deduplizierte Allowlist eines Typs mit Fallback-Logik.

    - calendar: ALLTAGS_CALENDAR_ENTITIES / calendar_entities
    - today_todo: ALLTAGS_TODAY_TODO_ENTITIES / today_todo_entities;
      falls nicht konfiguriert oder leer -> Fallback auf ALLTAGS_TODO_ENTITIES / todo_entities.
    - shopping_todo: ALLTAGS_SHOPPING_TODO_ENTITIES / shopping_todo_entities;
      falls nicht konfiguriert oder leer -> Fallback auf ALLTAGS_TODO_ENTITIES / todo_entities.
    - todo: ALLTAGS_TODO_ENTITIES / todo_entities;
      falls leer -> Vereinigung von today_todo und shopping_todo.
    """
    if kind == "today_todo":
        entities = _get_direct_configured_entities("today_todo")
        if not entities:
            entities = _get_direct_configured_entities("todo")
        return entities

    if kind == "shopping_todo":
        entities = _get_direct_configured_entities("shopping_todo")
        if not entities:
            entities = _get_direct_configured_entities("todo")
        return entities

    if kind == "todo":
        entities = _get_direct_configured_entities("todo")
        if not entities:
            union: List[str] = []
            for item in _get_direct_configured_entities("today_todo") + _get_direct_configured_entities("shopping_todo"):
                if item not in union:
                    union.append(item)
            return union
        return entities

    return _get_direct_configured_entities(kind)


# --- HTTP-Client -----------------------------------------------------------

def make_client() -> httpx.AsyncClient:
    """Erzeugt einen fertig konfigurierten AsyncClient.

    Tests ersetzen diese Factory per ``monkeypatch`` durch einen Client mit
    ``httpx.MockTransport``.
    """
    token = get_ha_token()
    if not token:
        raise HAUnavailable("SUPERVISOR_TOKEN nicht gesetzt")
    return httpx.AsyncClient(
        base_url=get_ha_base_url(),
        headers={"Authorization": f"Bearer {token}"},
        timeout=HA_TIMEOUT,
    )


def _day_bounds(day: date) -> Tuple[datetime, datetime]:
    """Lokale Tagesgrenzen [00:00, nächster Tag 00:00] mit Zeitzonen-Offset."""
    tz = _local_timezone()
    if tz is None:
        start = datetime.combine(day, time.min)
    else:
        start = datetime.combine(day, time.min, tzinfo=tz)
    return start, start + timedelta(days=1)


def _as_aware(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        tz = _local_timezone()
        return moment.replace(tzinfo=tz or timezone.utc)
    return moment


# --- Kalender --------------------------------------------------------------

async def _entity_name(client: httpx.AsyncClient, entity_id: str) -> str:
    """Friendly-Name aus ``/states/{entity_id}``; Fallback = Entity-Suffix."""
    fallback = entity_id.split(".", 1)[-1]
    try:
        response = await client.get(f"/states/{entity_id}")
        if response.status_code == 200:
            attributes = response.json().get("attributes") or {}
            name = attributes.get("friendly_name")
            if name:
                return str(name)
    except Exception:
        pass
    return fallback


def _map_event(entity_id: str, calendar_name: str, raw: dict, day: date,
               day_start: datetime, day_end: datetime) -> Optional[dict]:
    """Mappt ein HA-Event-Dict; ``None``, wenn es den Tag nicht überlappt."""
    start_info = raw.get("start") or {}
    end_info = raw.get("end") or {}

    if "date" in start_info:
        all_day = True
        try:
            start_date = date.fromisoformat(start_info["date"])
            end_date = date.fromisoformat(end_info.get("date", start_info["date"]))
        except (ValueError, TypeError):
            return None
        # HA-All-Day-``end`` ist exklusiv: [start, end).
        if not (start_date <= day and end_date > day):
            return None
        start_str = start_date.isoformat()
        end_str = end_date.isoformat()
    else:
        all_day = False
        try:
            start_dt = _as_aware(datetime.fromisoformat(start_info["dateTime"]))
            end_dt = _as_aware(datetime.fromisoformat(end_info["dateTime"]))
        except (KeyError, ValueError, TypeError):
            return None
        if not (start_dt < day_end and end_dt > day_start):
            return None
        start_str = start_dt.isoformat()
        end_str = end_dt.isoformat()

    title = raw.get("summary") or "(ohne Titel)"
    location = raw.get("location") or None
    return {
        "calendar": entity_id,
        "calendar_name": calendar_name,
        "title": title,
        "all_day": all_day,
        "start": start_str,
        "end": end_str,
        "location": location,
    }


async def _fetch_calendar(client: httpx.AsyncClient, entity_id: str, day: date,
                          day_start: datetime, day_end: datetime) -> List[dict]:
    name = await _entity_name(client, entity_id)
    response = await client.get(
        f"/calendars/{entity_id}",
        params={"start": day_start.isoformat(), "end": day_end.isoformat()},
    )
    if response.status_code == 401:
        raise HAUnavailable(f"401 für {entity_id}")
    if response.status_code != 200:
        raise HARejected(f"HTTP {response.status_code} für {entity_id}")

    events: List[dict] = []
    for raw in response.json() or []:
        if not isinstance(raw, dict):
            continue
        mapped = _map_event(entity_id, name, raw, day, day_start, day_end)
        if mapped is not None:
            events.append(mapped)
    return events


def _sort_key(event: dict):
    if event["all_day"]:
        return (0, event["start"], event["title"])
    return (1, event["start"], event["title"])


async def fetch_agenda(day: date) -> dict:
    """Aggregiert die Termine aller konfigurierten Kalender für ``day``."""
    entities = get_configured_entities("calendar")
    if not get_ha_token() or not entities:
        return {"available": False, "date": day, "events": []}

    day_start, day_end = _day_bounds(day)
    try:
        client = make_client()
    except HAUnavailable:
        return {"available": False, "date": day, "events": []}

    async with client:
        results = await asyncio.gather(
            *[_fetch_calendar(client, ent, day, day_start, day_end) for ent in entities],
            return_exceptions=True,
        )

    events: List[dict] = []
    successes = 0
    for entity_id, result in zip(entities, results):
        if isinstance(result, Exception):
            logger.warning("Kalender %s konnte nicht geladen werden (%s)",
                           entity_id, type(result).__name__)
            continue
        successes += 1
        events.extend(result)

    if successes == 0:
        return {"available": False, "date": day, "events": []}

    events.sort(key=_sort_key)
    return {"available": True, "date": day, "events": events}


# --- To-do-Listen ----------------------------------------------------------

async def _fetch_todo_list(client: httpx.AsyncClient, entity_id: str) -> dict:
    name = await _entity_name(client, entity_id)
    response = await client.post(
        "/services/todo/get_items",
        params={"return_response": "1"},
        json={"entity_id": entity_id, "status": ["needs_action"]},
    )
    if response.status_code == 401:
        raise HAUnavailable(f"401 für {entity_id}")
    if response.status_code != 200:
        raise HARejected(f"HTTP {response.status_code} für {entity_id}")

    payload = response.json() or {}
    service_response = payload.get("service_response") or {}
    list_data = service_response.get(entity_id) or {}
    items: List[dict] = []
    for raw in list_data.get("items") or []:
        if not isinstance(raw, dict):
            continue
        if (raw.get("status") or "needs_action") != "needs_action":
            continue
        items.append({
            "uid": str(raw.get("uid") or ""),
            "summary": raw.get("summary") or "(ohne Titel)",
            "status": "needs_action",
            "due": raw.get("due"),
            "description": raw.get("description"),
        })
    return {"entity_id": entity_id, "name": name, "items": items}


async def fetch_todos(kind: str = "today_todo") -> dict:
    """Aggregiert die offenen Items aller konfigurierten To-do-Listen."""
    entities = get_configured_entities(kind)
    if not get_ha_token() or not entities:
        return {"available": False, "lists": []}

    try:
        client = make_client()
    except HAUnavailable:
        return {"available": False, "lists": []}

    async with client:
        results = await asyncio.gather(
            *[_fetch_todo_list(client, ent) for ent in entities],
            return_exceptions=True,
        )

    lists: List[dict] = []
    successes = 0
    for entity_id, result in zip(entities, results):
        if isinstance(result, Exception):
            logger.warning("To-do-Liste %s konnte nicht geladen werden (%s)",
                           entity_id, type(result).__name__)
            continue
        successes += 1
        lists.append(result)

    if successes == 0:
        return {"available": False, "lists": []}
    return {"available": True, "lists": lists}


async def set_todo_status(entity_id: str, uid: str, completed: bool) -> None:
    """Setzt den Status eines To-do-Items via Service-Call (Rückschreiben)."""
    if not get_ha_token():
        raise HAUnavailable("SUPERVISOR_TOKEN nicht gesetzt")
    await update_todo_item(entity_id, uid, completed=completed)


async def fetch_todo_lists_summary(kind: str = "shopping_todo") -> List[dict]:
    """Liefert Übersicht aller konfigurierten To-do-Listen (entity_id und Name)."""
    if not get_ha_token():
        raise HAUnavailable("SUPERVISOR_TOKEN nicht gesetzt")
    entities = get_configured_entities(kind)
    if not entities:
        return []

    client = make_client()
    async with client:
        results = await asyncio.gather(
            *[_entity_name(client, ent) for ent in entities],
            return_exceptions=True,
        )

    lists: List[dict] = []
    for entity_id, res in zip(entities, results):
        if isinstance(res, Exception):
            logger.warning("Konnte Name für %s nicht laden: %s", entity_id, res)
            continue
        lists.append({"entity_id": entity_id, "name": res})
    return lists


async def fetch_single_todo_list(entity_id: str) -> dict:
    """Lädt alle Items (needs_action und completed) einer einzelnen To-do-Liste."""
    if not get_ha_token():
        raise HAUnavailable("SUPERVISOR_TOKEN nicht gesetzt")
    client = make_client()
    async with client:
        name = await _entity_name(client, entity_id)
        try:
            response = await client.post(
                "/services/todo/get_items",
                params={"return_response": "1"},
                json={"entity_id": entity_id, "status": ["needs_action", "completed"]},
            )
        except httpx.HTTPError as exc:
            raise HAUnavailable(f"Netzfehler für {entity_id} ({type(exc).__name__})") from exc

    if response.status_code == 401:
        raise HAUnavailable(f"401 für {entity_id}")
    if response.status_code != 200:
        raise HARejected(f"HTTP {response.status_code} für {entity_id}")

    payload = response.json() or {}
    service_response = payload.get("service_response") or {}
    list_data = service_response.get(entity_id) or {}
    items: List[dict] = []
    for raw in list_data.get("items") or []:
        if not isinstance(raw, dict):
            continue
        status = raw.get("status") or "needs_action"
        items.append({
            "uid": str(raw.get("uid") or ""),
            "summary": raw.get("summary") or "(ohne Titel)",
            "status": status,
            "due": raw.get("due"),
            "description": raw.get("description"),
        })
    return {"entity_id": entity_id, "name": name, "items": items}


async def add_todo_item(entity_id: str, summary: str, description: Optional[str] = None) -> None:
    """Fügt ein Item zu einer HA To-do-Liste hinzu."""
    if not get_ha_token():
        raise HAUnavailable("SUPERVISOR_TOKEN nicht gesetzt")
    client = make_client()
    payload = {"entity_id": entity_id, "item": summary}
    if description:
        payload["description"] = description

    async with client:
        try:
            response = await client.post("/services/todo/add_item", json=payload)
        except httpx.HTTPError as exc:
            raise HAUnavailable(f"Netzfehler für {entity_id} ({type(exc).__name__})") from exc

    if response.status_code == 401:
        raise HAUnavailable(f"401 für {entity_id}")
    if response.status_code >= 400:
        raise HARejected(f"HTTP {response.status_code} für {entity_id}")


async def update_todo_item(
    entity_id: str,
    uid: str,
    completed: Optional[bool] = None,
    summary: Optional[str] = None,
) -> None:
    """Aktualisiert Status und/oder Titel eines To-do-Items."""
    if not get_ha_token():
        raise HAUnavailable("SUPERVISOR_TOKEN nicht gesetzt")
    client = make_client()
    payload: dict = {"entity_id": entity_id, "item": uid}
    if completed is not None:
        payload["status"] = "completed" if completed else "needs_action"
    if summary is not None:
        payload["rename"] = summary

    async with client:
        try:
            response = await client.post("/services/todo/update_item", json=payload)
        except httpx.HTTPError as exc:
            raise HAUnavailable(f"Netzfehler für {entity_id} ({type(exc).__name__})") from exc

    if response.status_code == 401:
        raise HAUnavailable(f"401 für {entity_id}")
    if response.status_code >= 400:
        raise HARejected(f"HTTP {response.status_code} für {entity_id}")


async def remove_todo_items(entity_id: str, uids: List[str]) -> None:
    """Entfernt ein oder mehrere Items aus einer HA To-do-Liste."""
    if not uids:
        return
    if not get_ha_token():
        raise HAUnavailable("SUPERVISOR_TOKEN nicht gesetzt")
    client = make_client()
    payload = {"entity_id": entity_id, "item": uids}

    async with client:
        try:
            response = await client.post("/services/todo/remove_item", json=payload)
        except httpx.HTTPError as exc:
            raise HAUnavailable(f"Netzfehler für {entity_id} ({type(exc).__name__})") from exc

    if response.status_code == 401:
        raise HAUnavailable(f"401 für {entity_id}")
    if response.status_code >= 400:
        raise HARejected(f"HTTP {response.status_code} für {entity_id}")

