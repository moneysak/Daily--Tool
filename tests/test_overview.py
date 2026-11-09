"""Tests für die "Heute"-Übersichtsseite (GET /api/overview).

Deckt die Backend-Tasks B1-B7 sowie die statische Frontend-Smoke-Prüfung (T9)
ab. Die Fixtures ``client`` und ``addon_name`` sind über Dev- und Prod-Add-on
parametrisiert (siehe tests/conftest.py).

Fester Testtag: 2026-11-09 (ein Montag).
"""
import os
import re
import sqlite3
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDONS = ["alltags_manager_dev", "alltags_manager"]

TODAY = "2026-11-09"      # Montag
TOMORROW = "2026-11-10"   # Dienstag
YESTERDAY = "2026-11-08"  # Sonntag
LAST_WEEK = "2026-11-02"  # Montag


# --- Hilfsfunktionen -------------------------------------------------------

def _overview(client, today=TODAY):
    response = client.get(f"/api/overview?today={today}")
    assert response.status_code == 200, response.text
    return response.json()


def _titles(items):
    return [item["title"] for item in items]


def _db_session():
    import db.database as database

    return database.SessionLocal()


def _set_task_completed_at(task_id, moment):
    from models.task import Task

    db = _db_session()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        task.completed = True
        task.completed_at = moment
        db.commit()
    finally:
        db.close()


def _set_routine_last_completed(routine_id, day):
    from models.task import Routine

    db = _db_session()
    try:
        routine = db.query(Routine).filter(Routine.id == routine_id).first()
        routine.last_completed_on = day
        db.commit()
    finally:
        db.close()


# --- T1: Modelle / Schemas -------------------------------------------------

def test_task_due_date_roundtrip(client):
    with_due = client.post("/tasks/", json={"title": "A", "due_date": TOMORROW})
    assert with_due.status_code == 200
    assert with_due.json()["due_date"] == TOMORROW

    without_due = client.post("/tasks/", json={"title": "B"})
    assert without_due.status_code == 200
    assert without_due.json()["due_date"] is None


def test_task_completed_at_lifecycle(client):
    task_id = client.post("/tasks/", json={"title": "C"}).json()["id"]

    completed = client.put(f"/tasks/{task_id}", json={"completed": True})
    assert completed.status_code == 200
    assert completed.json()["completed_at"] is not None

    reopened = client.put(f"/tasks/{task_id}", json={"completed": False})
    assert reopened.status_code == 200
    assert reopened.json()["completed_at"] is None


def test_routine_weekdays_roundtrip(client):
    response = client.post(
        "/api/routines/",
        json={"title": "R", "frequency": "weekly", "weekdays": [2, 0, 2]},
    )
    assert response.status_code == 200
    assert response.json()["weekdays"] == [0, 2]


def test_routine_invalid_weekday_returns_422(client):
    response = client.post(
        "/api/routines/",
        json={"title": "R", "frequency": "weekly", "weekdays": [7]},
    )
    assert response.status_code == 422


def test_routine_invalid_frequency_returns_422(client):
    response = client.post("/api/routines/", json={"title": "R", "frequency": "monthly"})
    assert response.status_code == 422


def test_routine_completed_today_is_effective(client):
    routine_id = client.post(
        "/api/routines/", json={"title": "R", "frequency": "daily"}
    ).json()["id"]

    client.put(f"/api/routines/{routine_id}", json={"completed_today": True})
    items = client.get("/api/routines/").json()
    assert next(r for r in items if r["id"] == routine_id)["completed_today"] is True

    # Quelle der Wahrheit ist last_completed_on: ohne Datum -> wieder offen.
    _set_routine_last_completed(routine_id, None)
    items = client.get("/api/routines/").json()
    assert next(r for r in items if r["id"] == routine_id)["completed_today"] is False


# --- T2: Aggregation -------------------------------------------------------

def test_aggregation_task_classification(client):
    client.post("/tasks/", json={"title": "due", "due_date": TODAY})
    client.post("/tasks/", json={"title": "over", "due_date": YESTERDAY})
    client.post("/tasks/", json={"title": "someday"})
    client.post("/tasks/", json={"title": "future", "due_date": TOMORROW})

    overview = _overview(client)
    assert _titles(overview["tasks"]["due_today"]) == ["due"]
    assert _titles(overview["tasks"]["overdue"]) == ["over"]
    assert _titles(overview["tasks"]["someday"]) == ["someday"]
    assert overview["tasks"]["overdue"][0]["is_overdue"] is True

    seen = (
        _titles(overview["tasks"]["due_today"])
        + _titles(overview["tasks"]["overdue"])
        + _titles(overview["tasks"]["someday"])
        + _titles(overview["tasks"]["done_today"])
    )
    assert "future" not in seen


def test_overdue_is_sorted_oldest_first(client):
    client.post("/tasks/", json={"title": "newer", "due_date": YESTERDAY})
    client.post("/tasks/", json={"title": "older", "due_date": LAST_WEEK})

    overview = _overview(client)
    assert _titles(overview["tasks"]["overdue"]) == ["older", "newer"]


def test_aggregation_done_today_and_yesterday(client):
    done_today = client.post("/tasks/", json={"title": "done_today"}).json()["id"]
    done_yesterday = client.post("/tasks/", json={"title": "done_yesterday"}).json()["id"]
    _set_task_completed_at(done_today, datetime(2026, 11, 9, 10, 0, 0))
    _set_task_completed_at(done_yesterday, datetime(2026, 11, 8, 10, 0, 0))

    overview = _overview(client)
    assert _titles(overview["tasks"]["done_today"]) == ["done_today"]


def test_aggregation_routines(client):
    client.post("/api/routines/", json={"title": "daily", "frequency": "daily"})
    client.post(
        "/api/routines/", json={"title": "mon", "frequency": "weekly", "weekdays": [0]}
    )
    client.post(
        "/api/routines/", json={"title": "tue", "frequency": "weekly", "weekdays": [1]}
    )
    client.post(
        "/api/routines/",
        json={"title": "inactive", "frequency": "daily", "active": False},
    )

    overview = _overview(client)
    titles = _titles(overview["routines"])
    assert "daily" in titles
    assert "mon" in titles
    assert "tue" not in titles
    assert "inactive" not in titles


def test_weekly_without_weekdays_uses_created_at(client):
    routine_id = client.post(
        "/api/routines/", json={"title": "legacy", "frequency": "weekly"}
    ).json()["id"]

    import db.database as database
    from models.task import Routine

    db = database.SessionLocal()
    try:
        routine = db.query(Routine).filter(Routine.id == routine_id).first()
        routine.created_at = datetime(2026, 11, 9, 8, 0, 0)  # Montag
        db.commit()
    finally:
        db.close()

    assert "legacy" in _titles(_overview(client, TODAY)["routines"])
    assert "legacy" not in _titles(_overview(client, TOMORROW)["routines"])


def test_routine_completed_today_resets_next_day(client):
    routine_id = client.post(
        "/api/routines/", json={"title": "daily", "frequency": "daily"}
    ).json()["id"]
    _set_routine_last_completed(routine_id, date(2026, 11, 9))

    assert _overview(client, TODAY)["routines"][0]["completed_today"] is True
    assert _overview(client, TOMORROW)["routines"][0]["completed_today"] is False


# --- T3: Fortschritt -------------------------------------------------------

def test_progress_calculation(client):
    client.post("/tasks/", json={"title": "due", "due_date": TODAY})
    client.post("/tasks/", json={"title": "over", "due_date": YESTERDAY})
    done = client.post("/tasks/", json={"title": "done", "due_date": TODAY}).json()["id"]
    _set_task_completed_at(done, datetime(2026, 11, 9, 9, 0, 0))
    routine_id = client.post(
        "/api/routines/", json={"title": "r", "frequency": "daily"}
    ).json()["id"]
    _set_routine_last_completed(routine_id, date(2026, 11, 9))

    progress = _overview(client)["progress"]
    # total = 1 due + 1 overdue + 1 done_today + 1 routine_due = 4
    # done  = 1 done_today + 1 routine_done = 2
    assert progress == {"done": 2, "total": 4, "percent": 50}


def test_progress_empty_db(client):
    overview = _overview(client)
    assert overview["progress"] == {"done": 0, "total": 0, "percent": 0}
    assert overview["tasks"] == {
        "due_today": [],
        "overdue": [],
        "someday": [],
        "done_today": [],
    }
    assert overview["routines"] == []


def test_someday_completed_today_counts_in_done_and_total(client):
    task_id = client.post("/tasks/", json={"title": "someday_done"}).json()["id"]
    _set_task_completed_at(task_id, datetime(2026, 11, 9, 9, 0, 0))

    overview = _overview(client)
    assert _titles(overview["tasks"]["done_today"]) == ["someday_done"]
    assert overview["progress"] == {"done": 1, "total": 1, "percent": 100}


# --- T4: Einkauf -----------------------------------------------------------

def test_shopping_open_count(client):
    for name in ("a", "b", "c"):
        client.post("/api/shopping/", json={"name": name, "quantity": "1", "checked": False})
    first_id = client.get("/api/shopping/").json()[0]["id"]
    client.put(f"/api/shopping/{first_id}", json={"checked": True})

    overview = _overview(client)
    assert overview["shopping"]["open_count"] == 2


# --- T5: Auth --------------------------------------------------------------

def test_overview_requires_auth(app_factory, addon_name):
    app = app_factory(addon_name, password="geheim")
    with TestClient(app) as client:
        assert client.get("/api/overview").status_code == 401

        token = client.post("/api/auth/login", json={"password": "geheim"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/overview?today=2026-11-09", headers=headers)
        assert response.status_code == 200


def test_overview_invalid_today_returns_422(client):
    assert client.get("/api/overview?today=abc").status_code == 422


# --- T6: user_name ---------------------------------------------------------

def test_user_name_from_env(client, monkeypatch):
    monkeypatch.setenv("USER_NAME", "Daniel")
    assert _overview(client)["user_name"] == "Daniel"


def test_user_name_empty_is_null(client, monkeypatch):
    monkeypatch.delenv("USER_NAME", raising=False)
    assert _overview(client)["user_name"] is None


def test_user_name_from_options(app_factory, addon_name, monkeypatch):
    monkeypatch.delenv("USER_NAME", raising=False)
    app = app_factory(addon_name, options={"user_name": "Daniel"})
    with TestClient(app) as client:
        response = client.get("/api/overview?today=2026-11-09")
        assert response.status_code == 200
        assert response.json()["user_name"] == "Daniel"


# --- T7: Migration ---------------------------------------------------------

def _create_legacy_db(path):
    con = sqlite3.connect(str(path))
    con.execute(
        "CREATE TABLE tasks (id INTEGER PRIMARY KEY, title VARCHAR, description VARCHAR, "
        "completed BOOLEAN, created_at DATETIME)"
    )
    con.execute(
        "INSERT INTO tasks (id, title, completed, created_at) "
        "VALUES (1, 'Alt', 0, '2026-01-01 00:00:00')"
    )
    con.execute(
        "CREATE TABLE shopping_items (id INTEGER PRIMARY KEY, name VARCHAR, quantity VARCHAR, "
        "category VARCHAR, checked BOOLEAN, created_at DATETIME)"
    )
    con.execute(
        "CREATE TABLE routines (id INTEGER PRIMARY KEY, title VARCHAR, description VARCHAR, "
        "frequency VARCHAR, active BOOLEAN, completed_today BOOLEAN, created_at DATETIME)"
    )
    con.commit()
    con.close()


def test_old_db_is_migrated(app_factory, addon_name, tmp_path):
    data_dir = tmp_path / "olddata"
    data_dir.mkdir()
    _create_legacy_db(data_dir / "alltags_manager.db")

    app = app_factory(addon_name, data_dir=data_dir)
    with TestClient(app) as client:
        tasks = client.get("/tasks/")
        assert tasks.status_code == 200
        assert "Alt" in _titles(tasks.json())

        assert client.get("/api/overview?today=2026-11-09").status_code == 200
        # Neue Spalte nutzbar -> kein "no such column".
        created = client.post("/tasks/", json={"title": "Neu", "due_date": "2026-11-10"})
        assert created.status_code == 200
        assert created.json()["due_date"] == "2026-11-10"


def test_migration_is_idempotent(app_factory, addon_name, tmp_path):
    data_dir = tmp_path / "olddata2"
    data_dir.mkdir()
    _create_legacy_db(data_dir / "alltags_manager.db")

    app_factory(addon_name, data_dir=data_dir)  # erster Start migriert
    app2 = app_factory(addon_name, data_dir=data_dir)  # zweiter Start darf nicht werfen
    with TestClient(app2) as client:
        assert client.get("/tasks/").status_code == 200


# --- T8: Rückwärtskompatibilität -------------------------------------------

def test_put_routine_only_completed_today(client):
    routine_id = client.post(
        "/api/routines/", json={"title": "R", "frequency": "daily"}
    ).json()["id"]

    response = client.put(f"/api/routines/{routine_id}", json={"completed_today": True})
    assert response.status_code == 200
    assert response.json()["completed_today"] is True


# --- T9: Frontend-Smoke (statisch) -----------------------------------------

@pytest.mark.parametrize("addon", ADDONS)
def test_today_tab_is_first_and_active(addon):
    path = os.path.join(REPO_ROOT, addon, "src", "frontend", "index.html")
    with open(path, encoding="utf-8") as handle:
        html = handle.read()

    tab_bar = html.split("bottom-tab-bar", 1)[1]
    assert 'data-target="today"' in tab_bar
    assert tab_bar.index('data-target="today"') < tab_bar.index('data-target="tasks"')
    assert re.search(r'class="tab-item active"[^>]*data-target="today"', tab_bar)
    assert not re.search(r'class="tab-item active"[^>]*data-target="tasks"', tab_bar)


@pytest.mark.parametrize("addon", ADDONS)
def test_app_js_overview_and_escaping(addon):
    path = os.path.join(REPO_ROOT, addon, "src", "frontend", "app.js")
    with open(path, encoding="utf-8") as handle:
        js = handle.read()

    assert "/api/overview" in js
    assert "greetingFor" in js

    match = re.search(r"function renderTodaySections\([\s\S]*?\n    \}", js)
    assert match, "renderTodaySections nicht gefunden"
    assert "escapeHtml" in match.group(0)


# --- Zusätzliche Regressionstests (Review-Befunde) --------------------------

def test_completed_at_uses_local_timezone_at_midnight(client, monkeypatch):
    """Befund 1: Grenze lokale Mitternacht vs. UTC.

    00:30 Uhr Berlin entspricht 23:30 Uhr UTC am Vortag. Wird ``completed_at``
    in lokaler Zeit gespeichert, bleibt eine in dieser Zeit erledigte Aufgabe
    beim lokalen Datum ("heute erledigt") statt auf den UTC-Vortag zu rutschen.
    """
    import crud.task as task_crud
    from zoneinfo import ZoneInfo

    monkeypatch.setenv("TZ", "Europe/Berlin")

    local_moment = datetime(2026, 11, 9, 0, 30, 0)  # Montag, 00:30 lokal Berlin
    # Grenze belegen: derselbe Moment ist in UTC noch Sonntag (08.11.).
    aware = local_moment.replace(tzinfo=ZoneInfo("Europe/Berlin"))
    assert aware.astimezone(timezone.utc).date() == date(2026, 11, 8)

    monkeypatch.setattr(task_crud, "local_now", lambda: local_moment)

    task_id = client.post("/tasks/", json={"title": "mitternacht"}).json()["id"]
    response = client.put(f"/tasks/{task_id}", json={"completed": True})
    assert response.status_code == 200

    # completed_at wurde in lokaler Zeit gespeichert (nicht UTC).
    from models.task import Task

    db = _db_session()
    try:
        stored = db.query(Task).filter(Task.id == task_id).first()
        assert stored.completed_at == local_moment
    finally:
        db.close()

    # Lokaler Tag -> in "heute erledigt" enthalten.
    assert "mitternacht" in _titles(_overview(client, TODAY)["tasks"]["done_today"])
    # UTC-Vortag -> nicht enthalten (Gegenprobe der Grenze).
    assert "mitternacht" not in _titles(_overview(client, YESTERDAY)["tasks"]["done_today"])


def test_legacy_completed_without_completed_at_not_counted(client):
    """Befund 5: Alt-Daten completed=True ohne completed_at zählen nicht.

    Solche Datensätze dürfen weder in "heute erledigt" noch im Fortschritt
    auftauchen (weder in ``done`` noch in ``total``).
    """
    task_id = client.post("/tasks/", json={"title": "alt"}).json()["id"]
    # completed=True, aber ohne Zeitstempel (Alt-Bestand).
    _set_task_completed_at(task_id, None)

    overview = _overview(client)
    assert "alt" not in _titles(overview["tasks"]["done_today"])
    assert overview["progress"] == {"done": 0, "total": 0, "percent": 0}


def test_put_routine_invalid_weekday_returns_422(client):
    """Befund 5: PUT validiert weekdays genauso wie POST."""
    routine_id = client.post(
        "/api/routines/", json={"title": "R", "frequency": "daily"}
    ).json()["id"]

    response = client.put(f"/api/routines/{routine_id}", json={"weekdays": [7]})
    assert response.status_code == 422


def test_put_routine_invalid_frequency_returns_422(client):
    """Befund 5: PUT validiert frequency genauso wie POST."""
    routine_id = client.post(
        "/api/routines/", json={"title": "R", "frequency": "daily"}
    ).json()["id"]

    response = client.put(f"/api/routines/{routine_id}", json={"frequency": "monthly"})
    assert response.status_code == 422
