"""Tests für die Home-Assistant-Integration (Kalender + To-do-Listen).

Deckt die Backend-Tasks T1-T9 sowie statische Frontend-/Config-Prüfungen
(T10-T12) ab. HA wird vollständig über ``httpx.MockTransport`` gemockt - es
darf nie ein echter Netzwerkzugriff stattfinden (Handler-Default: ``pytest.fail``).

Fester Testtag: 2026-11-09 (ein Montag).
"""
import asyncio
import json
import os

import httpx
import pytest
import yaml
from fastapi.testclient import TestClient

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDONS = ["alltags_manager_dev", "alltags_manager"]

TODAY = "2026-11-09"
TOMORROW = "2026-11-10"
YESTERDAY = "2026-11-08"
SUMMER = "2026-07-01"


# --- Mock-Infrastruktur ----------------------------------------------------

class HAMock:
    """Konfigurierbarer HA-Mock; protokolliert Requests und Bodies."""

    def __init__(self):
        self.counter = 0
        self.requests = []
        self.calendars = {}     # entity -> list | ("status", code) | Exception
        self.states = {}        # entity -> friendly_name
        self.todo_items = {}    # entity -> list | Exception
        self.update_calls = []
        self.update_status = 200
        self.update_error = None

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.counter += 1
        self.requests.append(request)
        path = request.url.path

        if "/calendars/" in path:
            entity = path.split("/calendars/", 1)[1]
            value = self.calendars.get(entity, [])
            if isinstance(value, Exception):
                raise value
            if isinstance(value, tuple) and value[0] == "status":
                return httpx.Response(value[1], json=[])
            return httpx.Response(200, json=value)

        if path.endswith("/services/todo/get_items"):
            body = json.loads(request.content or b"{}")
            assert "return_response" in request.url.params
            entity = body.get("entity_id")
            value = self.todo_items.get(entity, [])
            if isinstance(value, Exception):
                raise value
            payload = {"changed_states": [],
                       "service_response": {entity: {"items": value}}}
            return httpx.Response(200, json=payload)

        if path.endswith("/services/todo/add_item"):
            body = json.loads(request.content or b"{}")
            self.update_calls.append(body)
            if self.update_error is not None:
                raise self.update_error
            if self.update_status >= 400:
                return httpx.Response(self.update_status, json={"message": "rejected"})
            return httpx.Response(200, json=[])

        if path.endswith("/services/todo/remove_item"):
            body = json.loads(request.content or b"{}")
            self.update_calls.append(body)
            if self.update_error is not None:
                raise self.update_error
            if self.update_status >= 400:
                return httpx.Response(self.update_status, json={"message": "rejected"})
            return httpx.Response(200, json=[])

        if path.endswith("/services/todo/update_item"):
            body = json.loads(request.content or b"{}")
            self.update_calls.append(body)
            if self.update_error is not None:
                raise self.update_error
            if self.update_status >= 400:
                return httpx.Response(self.update_status, json={"message": "rejected"})
            return httpx.Response(200, json=[])

        if "/states/" in path:
            entity = path.split("/states/", 1)[1]
            name = self.states.get(entity) or entity.split(".")[-1].title()
            return httpx.Response(200, json={
                "entity_id": entity,
                "state": "1",
                "attributes": {"friendly_name": name},
            })

        pytest.fail(f"Unerwarteter HA-Request: {path}")


@pytest.fixture
def ha_mock(client, monkeypatch):
    """Ersetzt ``crud.ha.make_client`` durch einen MockTransport-Client."""
    import crud.ha as ha

    mock = HAMock()

    def factory():
        return httpx.AsyncClient(
            transport=httpx.MockTransport(mock.handler),
            base_url=ha.get_ha_base_url(),
            headers={"Authorization": "Bearer test-token"},
        )

    monkeypatch.setattr(ha, "make_client", factory)
    return mock


@pytest.fixture
def ha_env(monkeypatch):
    """Setzt Token/Konfiguration/TZ für HA-Tests."""

    def apply(token="test-token", calendars="calendar.familie",
              todos="todo.einkaufsliste", tz="Europe/Berlin"):
        if token is None:
            monkeypatch.delenv("SUPERVISOR_TOKEN", raising=False)
        else:
            monkeypatch.setenv("SUPERVISOR_TOKEN", token)
        monkeypatch.setenv("ALLTAGS_CALENDAR_ENTITIES", calendars)
        monkeypatch.setenv("ALLTAGS_TODO_ENTITIES", todos)
        if tz is None:
            monkeypatch.delenv("TZ", raising=False)
        else:
            monkeypatch.setenv("TZ", tz)
        monkeypatch.delenv("ALLTAGS_HA_BASE_URL", raising=False)

    return apply


def _agenda(client, today=TODAY):
    response = client.get(f"/api/ha/agenda?today={today}")
    assert response.status_code == 200, response.text
    return response.json()


# --- Testfälle (1-19) ------------------------------------------------------

def test_ha_fallback_without_token(client, ha_env):
    """1. Ohne SUPERVISOR_TOKEN -> available:false, leere Listen."""
    ha_env(token=None)
    assert _agenda(client) == {"available": False, "date": TODAY, "events": []}
    assert client.get("/api/ha/todos").json() == {"available": False, "lists": []}


def test_empty_config_makes_no_ha_request(client, ha_env, ha_mock):
    """2. Leere Konfiguration -> available:false und kein HA-Request."""
    ha_env(token="test-token", calendars="", todos="")
    assert _agenda(client)["available"] is False
    assert client.get("/api/ha/todos").json()["available"] is False
    assert ha_mock.counter == 0


def test_agenda_mapping_and_sorting(client, ha_env, ha_mock):
    """3. Mapping + Sortierung (All-Day zuerst, dann Zeit)."""
    ha_env()
    ha_mock.states["calendar.familie"] = "Familie"
    ha_mock.calendars["calendar.familie"] = [
        {"start": {"dateTime": "2026-11-09T14:30:00+01:00"},
         "end": {"dateTime": "2026-11-09T15:30:00+01:00"},
         "summary": "Zahnarzt", "location": "Praxis"},
        {"start": {"date": "2026-11-09"}, "end": {"date": "2026-11-10"},
         "summary": "Familientag"},
    ]
    data = _agenda(client)
    assert data["available"] is True
    events = data["events"]
    assert [e["title"] for e in events] == ["Familientag", "Zahnarzt"]
    assert events[0]["all_day"] is True
    assert events[0]["start"] == "2026-11-09"
    assert "T" not in events[0]["start"]
    assert events[0]["calendar_name"] == "Familie"
    assert events[1]["all_day"] is False
    assert events[1]["start"] == "2026-11-09T14:30:00+01:00"
    assert events[1]["location"] == "Praxis"


def test_agenda_request_bounds_and_headers(client, ha_env, ha_mock):
    """4. Tagesgrenzen (Winter/Sommer) + Auth-Header, kein X-Hass-User-ID."""
    ha_env(tz="Europe/Berlin")
    ha_mock.calendars["calendar.familie"] = []

    _agenda(client, TODAY)
    cal_reqs = [r for r in ha_mock.requests if "/calendars/" in r.url.path]
    assert len(cal_reqs) == 1
    params = cal_reqs[0].url.params
    assert params.get("start") == "2026-11-09T00:00:00+01:00"
    assert params.get("end") == "2026-11-10T00:00:00+01:00"
    header_names = {k.lower() for k in cal_reqs[0].headers.keys()}
    assert cal_reqs[0].headers["authorization"].lower().startswith("bearer ")
    assert "x-hass-user-id" not in header_names

    _agenda(client, SUMMER)
    summer_req = [r for r in ha_mock.requests if "/calendars/" in r.url.path][-1]
    assert summer_req.url.params.get("start") == "2026-07-01T00:00:00+02:00"


def test_agenda_multiday_overlap_and_exclusive_allday(client, ha_env, ha_mock):
    """5. Mehrtägige Events inkl., All-Day von gestern (end exklusiv) exkl."""
    ha_env()
    ha_mock.calendars["calendar.familie"] = [
        {"start": {"dateTime": "2026-11-08T10:00:00+01:00"},
         "end": {"dateTime": "2026-11-10T12:00:00+01:00"}, "summary": "Mehrtägig"},
        {"start": {"date": "2026-11-08"}, "end": {"date": "2026-11-09"},
         "summary": "GesternGanztags"},
        {"start": {"date": "2026-11-09"}, "end": {"date": "2026-11-11"},
         "summary": "GanztagsMehrtag"},
    ]
    titles = [e["title"] for e in _agenda(client)["events"]]
    assert "Mehrtägig" in titles
    assert "GanztagsMehrtag" in titles
    assert "GesternGanztags" not in titles


def test_agenda_single_calendar_error_others_ok(client, ha_env, ha_mock):
    """6. Ein Kalender 500 -> anderer liefert trotzdem, available:true."""
    ha_env(calendars="calendar.familie,calendar.arbeit")
    ha_mock.calendars["calendar.familie"] = ("status", 500)
    ha_mock.calendars["calendar.arbeit"] = [
        {"start": {"dateTime": "2026-11-09T09:00:00+01:00"},
         "end": {"dateTime": "2026-11-09T10:00:00+01:00"}, "summary": "Meeting"},
    ]
    data = _agenda(client)
    assert data["available"] is True
    assert [e["title"] for e in data["events"]] == ["Meeting"]


def test_agenda_all_calendars_connect_error(client, ha_env, ha_mock):
    """7. Alle Kalender mit ConnectError -> available:false, HTTP 200."""
    ha_env(calendars="calendar.familie,calendar.arbeit")
    ha_mock.calendars["calendar.familie"] = httpx.ConnectError("boom")
    ha_mock.calendars["calendar.arbeit"] = httpx.ConnectError("boom")
    data = _agenda(client)
    assert data["available"] is False
    assert data["events"] == []


def test_agenda_invalid_today_returns_422(client, ha_env):
    """8. Ungültiges today -> 422."""
    ha_env()
    assert client.get("/api/ha/agenda?today=abc").status_code == 422


def test_todos_mapping_order_and_names(client, ha_env, ha_mock):
    """9. Mapping, Reihenfolge, Namen (friendly_name), nur needs_action."""
    ha_env(todos="todo.einkaufsliste,todo.haushalt")
    ha_mock.states["todo.einkaufsliste"] = "Einkaufsliste"
    ha_mock.states["todo.haushalt"] = "Haushalt"
    ha_mock.todo_items["todo.einkaufsliste"] = [
        {"uid": "u1", "summary": "Milch", "status": "needs_action", "due": None},
        {"uid": "u2", "summary": "Brot", "status": "completed", "due": None},
    ]
    ha_mock.todo_items["todo.haushalt"] = [
        {"uid": "h1", "summary": "Staubsaugen", "status": "needs_action", "due": None},
    ]
    data = client.get("/api/ha/todos").json()
    assert data["available"] is True
    assert [lst["entity_id"] for lst in data["lists"]] == ["todo.einkaufsliste", "todo.haushalt"]
    assert [lst["name"] for lst in data["lists"]] == ["Einkaufsliste", "Haushalt"]
    assert [i["summary"] for i in data["lists"][0]["items"]] == ["Milch"]


def test_todos_single_list_error_others_remain(client, ha_env, ha_mock):
    """10. Fehler einer Liste -> andere bleibt erhalten."""
    ha_env(todos="todo.einkaufsliste,todo.haushalt")
    ha_mock.todo_items["todo.einkaufsliste"] = httpx.ConnectError("boom")
    ha_mock.todo_items["todo.haushalt"] = [
        {"uid": "h1", "summary": "Wischen", "status": "needs_action"},
    ]
    data = client.get("/api/ha/todos").json()
    assert data["available"] is True
    assert [lst["entity_id"] for lst in data["lists"]] == ["todo.haushalt"]


def test_toggle_sends_correct_body(client, ha_env, ha_mock):
    """11. completed true/false -> korrekter Service-Body."""
    ha_env(todos="todo.einkaufsliste")
    ok = client.post("/api/ha/todos/item",
                     json={"entity_id": "todo.einkaufsliste", "uid": "u1", "completed": True})
    assert ok.status_code == 200 and ok.json() == {"status": "success"}
    again = client.post("/api/ha/todos/item",
                        json={"entity_id": "todo.einkaufsliste", "uid": "u1", "completed": False})
    assert again.status_code == 200
    assert ha_mock.update_calls[0] == {
        "entity_id": "todo.einkaufsliste", "item": "u1", "status": "completed"}
    assert ha_mock.update_calls[1] == {
        "entity_id": "todo.einkaufsliste", "item": "u1", "status": "needs_action"}


def test_toggle_forbidden_and_validation(client, ha_env, ha_mock):
    """12. Nicht in Allowlist -> 403 (kein HA-Call); ungültig/fehlend -> 422."""
    ha_env(todos="todo.einkaufsliste")
    forbidden = client.post("/api/ha/todos/item",
                            json={"entity_id": "todo.other", "uid": "u1", "completed": True})
    assert forbidden.status_code == 403
    assert ha_mock.update_calls == []

    assert client.post("/api/ha/todos/item",
                       json={"entity_id": "foo", "uid": "u1", "completed": True}).status_code == 422
    assert client.post("/api/ha/todos/item",
                       json={"entity_id": "todo.einkaufsliste", "completed": True}).status_code == 422


def test_toggle_ha_unavailable_and_rejected(client, ha_env, ha_mock):
    """13. HA nicht verfügbar -> 503 (kein Token / Netzfehler); HA lehnt ab (400) -> 502."""
    ha_env(token=None, todos="todo.einkaufsliste")
    unavailable = client.post("/api/ha/todos/item",
                              json={"entity_id": "todo.einkaufsliste", "uid": "u1", "completed": True})
    assert unavailable.status_code == 503

    ha_env(token="test-token", todos="todo.einkaufsliste")
    ha_mock.update_status = 400
    rejected = client.post("/api/ha/todos/item",
                           json={"entity_id": "todo.einkaufsliste", "uid": "u1", "completed": True})
    assert rejected.status_code == 502

    # Netzfehler (ConnectError) -> HAUnavailable -> 503, kein unbehandelter 500.
    ha_env(token="test-token", todos="todo.einkaufsliste")
    ha_mock.update_status = 200
    ha_mock.update_error = httpx.ConnectError("Netzwerk weg")
    network_error = client.post("/api/ha/todos/item",
                                json={"entity_id": "todo.einkaufsliste", "uid": "u1", "completed": True})
    assert network_error.status_code == 503


def test_ha_endpoints_require_auth(app_factory, addon_name):
    """14. Alle drei Endpunkte ohne Token (Passwort-Modus) -> 401."""
    app = app_factory(addon_name, password="geheim")
    with TestClient(app) as client:
        assert client.get("/api/ha/agenda").status_code == 401
        assert client.get("/api/ha/todos").status_code == 401
        assert client.post("/api/ha/todos/item",
                           json={"entity_id": "todo.x", "uid": "u", "completed": True}).status_code == 401


def test_get_configured_entities_priority_and_validation(client, tmp_path, monkeypatch):
    """15. Env > options.json > leer; ungültige/duplizierte verworfen."""
    import crud.ha as ha

    monkeypatch.setenv("ALLTAGS_CALENDAR_ENTITIES",
                       "calendar.b,todo.x,calendar.a,calendar.b,INVALID,calendar.c!")
    assert ha.get_configured_entities("calendar") == ["calendar.b", "calendar.a"]

    options_file = tmp_path / "options.json"
    options_file.write_text(
        json.dumps({"calendar_entities": ["calendar.x", "bad", "todo.y"]}),
        encoding="utf-8",
    )
    monkeypatch.delenv("ALLTAGS_CALENDAR_ENTITIES", raising=False)
    monkeypatch.setenv("ALLTAGS_OPTIONS_PATH", str(options_file))
    assert ha.get_configured_entities("calendar") == ["calendar.x"]

    # Env hat Vorrang vor options.json
    monkeypatch.setenv("ALLTAGS_CALENDAR_ENTITIES", "calendar.env")
    assert ha.get_configured_entities("calendar") == ["calendar.env"]

    monkeypatch.delenv("ALLTAGS_CALENDAR_ENTITIES", raising=False)
    monkeypatch.setenv("ALLTAGS_OPTIONS_PATH", str(tmp_path / "nope.json"))
    assert ha.get_configured_entities("calendar") == []


@pytest.mark.parametrize("addon", ADDONS)
def test_frontend_ha_hooks_present(addon):
    """16. Statische Frontend-Prüfung: Slots, Funktionen, Endpunkte, Escaping."""
    path = os.path.join(REPO_ROOT, addon, "src", "frontend", "app.js")
    with open(path, encoding="utf-8") as handle:
        js = handle.read()
    for token in ("loadAgenda", "loadTodos", "/api/ha/agenda", "/api/ha/todos",
                  "escapeHtml", "agenda-slot", "todos-slot", "ha-todo-checkbox"):
        assert token in js, f"{token} fehlt in app.js"


@pytest.mark.parametrize("addon", ADDONS)
def test_config_yaml_ha_options(addon):
    """17. Beide config.yaml: Optionen + Schema + homeassistant_api."""
    path = os.path.join(REPO_ROOT, addon, "config.yaml")
    with open(path, encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    assert config["homeassistant_api"] is True
    assert "calendar_entities" in config["options"]
    assert "todo_entities" in config["options"]
    assert "calendar_entities" in config["schema"]
    assert "todo_entities" in config["schema"]


def test_overview_has_no_ha_fields(client):
    """18. Regression: /api/overview bleibt DB-only (keine HA-Felder)."""
    data = client.get("/api/overview?today=2026-11-09").json()
    assert set(data.keys()) == {"today", "user_name", "tasks", "routines", "shopping", "progress"}


def test_make_client_headers_and_base_url(client, monkeypatch):
    """19. make_client: Bearer-Header, korrekte Basis-URL, kein X-Hass-User-ID."""
    import crud.ha as ha

    monkeypatch.setenv("SUPERVISOR_TOKEN", "tok-123")
    monkeypatch.delenv("ALLTAGS_HA_BASE_URL", raising=False)
    client_obj = ha.make_client()
    try:
        assert client_obj.headers["authorization"] == "Bearer tok-123"
        assert "x-hass-user-id" not in {k.lower() for k in client_obj.headers.keys()}
        assert str(client_obj.base_url).rstrip("/") == "http://supervisor/core/api"
    finally:
        asyncio.run(client_obj.aclose())


# --- Multi-List Integration Tests ---

def test_ha_multi_list_endpoints(client, ha_env, ha_mock):
    """Testet die neuen Endpunkte für To-Do-Listen-Switching und CRUD."""
    ha_env(todos="todo.einkaufsliste,todo.dm")
    ha_mock.states["todo.einkaufsliste"] = "Supermarkt"
    ha_mock.states["todo.dm"] = "Drogerie"
    ha_mock.todo_items["todo.einkaufsliste"] = [
        {"uid": "item-1", "summary": "Milch", "status": "needs_action", "description": "2x"},
        {"uid": "item-2", "summary": "Brot", "status": "completed"}
    ]

    # 1. GET /api/ha/todos/lists
    res = client.get("/api/ha/todos/lists")
    assert res.status_code == 200
    lists = res.json()
    assert len(lists) == 2
    assert lists[0] == {"entity_id": "todo.einkaufsliste", "name": "Supermarkt"}
    assert lists[1] == {"entity_id": "todo.dm", "name": "Drogerie"}

    # 2. GET /api/ha/todos/lists/{entity_id}
    res = client.get("/api/ha/todos/lists/todo.einkaufsliste")
    assert res.status_code == 200
    data = res.json()
    assert data["entity_id"] == "todo.einkaufsliste"
    assert data["name"] == "Supermarkt"
    assert len(data["items"]) == 2
    assert data["items"][0] == {
        "uid": "item-1",
        "summary": "Milch",
        "status": "needs_action",
        "due": None,
        "description": "2x"
    }

    # Unberechtigte entity_id -> 403
    assert client.get("/api/ha/todos/lists/todo.forbidden").status_code == 403

    # 3. POST /api/ha/todos/items
    add_res = client.post("/api/ha/todos/items", json={
        "entity_id": "todo.einkaufsliste",
        "summary": "Haferflocken",
        "description": "1 Paket"
    })
    assert add_res.status_code == 200
    assert ha_mock.update_calls[-1] == {
        "entity_id": "todo.einkaufsliste",
        "item": "Haferflocken",
        "description": "1 Paket"
    }

    # 4. PUT /api/ha/todos/items/{uid}
    update_res = client.put("/api/ha/todos/items/item-1", json={
        "entity_id": "todo.einkaufsliste",
        "completed": True,
        "summary": "Vollmilch"
    })
    assert update_res.status_code == 200
    assert ha_mock.update_calls[-1] == {
        "entity_id": "todo.einkaufsliste",
        "item": "item-1",
        "status": "completed",
        "rename": "Vollmilch"
    }

    # 5. POST /api/ha/todos/items/delete
    del_res = client.post("/api/ha/todos/items/delete", json={
        "entity_id": "todo.einkaufsliste",
        "uids": ["item-1", "item-2"]
    })
    assert del_res.status_code == 200
    assert ha_mock.update_calls[-1] == {
        "entity_id": "todo.einkaufsliste",
        "item": ["item-1", "item-2"]
    }


def test_ha_multi_list_auth_and_error_handling(client, ha_env, ha_mock, app_factory, addon_name):
    """Testet Allowlist, Fehlerstatus (503/502) und Auth-Schutz der neuen Endpunkte."""
    ha_env(todos="todo.einkaufsliste")

    # Forbidden entities
    assert client.post("/api/ha/todos/items", json={"entity_id": "todo.bad", "summary": "X"}).status_code == 403
    assert client.put("/api/ha/todos/items/u1", json={"entity_id": "todo.bad", "completed": True}).status_code == 403
    assert client.post("/api/ha/todos/items/delete", json={"entity_id": "todo.bad", "uids": ["u1"]}).status_code == 403

    # HA nicht verfügbar -> 503
    ha_env(token=None, todos="todo.einkaufsliste")
    assert client.get("/api/ha/todos/lists").status_code == 503
    assert client.get("/api/ha/todos/lists/todo.einkaufsliste").status_code == 503
    assert client.post("/api/ha/todos/items", json={"entity_id": "todo.einkaufsliste", "summary": "X"}).status_code == 503
    assert client.put("/api/ha/todos/items/u1", json={"entity_id": "todo.einkaufsliste", "completed": True}).status_code == 503
    assert client.post("/api/ha/todos/items/delete", json={"entity_id": "todo.einkaufsliste", "uids": ["u1"]}).status_code == 503

    # HA abgelehnt -> 502
    ha_env(token="test-token", todos="todo.einkaufsliste")
    ha_mock.update_status = 500
    assert client.post("/api/ha/todos/items", json={"entity_id": "todo.einkaufsliste", "summary": "X"}).status_code == 502

    # Auth erforderlich
    app = app_factory(addon_name, password="geheim")
    with TestClient(app) as auth_client:
        assert auth_client.get("/api/ha/todos/lists").status_code == 401
        assert auth_client.get("/api/ha/todos/lists/todo.einkaufsliste").status_code == 401
        assert auth_client.post("/api/ha/todos/items", json={"entity_id": "todo.einkaufsliste", "summary": "X"}).status_code == 401
        assert auth_client.put("/api/ha/todos/items/u1", json={"entity_id": "todo.einkaufsliste", "completed": True}).status_code == 401
        assert auth_client.post("/api/ha/todos/items/delete", json={"entity_id": "todo.einkaufsliste", "uids": ["u1"]}).status_code == 401


@pytest.mark.parametrize("addon", ADDONS)
def test_frontend_shopping_multi_list_hooks_present(addon):
    """Statische Frontend-Prüfung für Shopping-Multi-List Dropdown und Keys."""
    path = os.path.join(REPO_ROOT, addon, "src", "frontend", "app.js")
    with open(path, encoding="utf-8") as handle:
        js = handle.read()
    for token in ("shopping-list-select", "alltags_selected_shopping_list",
                  "/api/ha/todos/lists", "updateShoppingListsDropdown"):
        assert token in js, f"{token} fehlt in app.js"

