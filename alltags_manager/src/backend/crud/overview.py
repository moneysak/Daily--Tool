"""Aggregationslogik für die "Heute"-Übersichtsseite (GET /api/overview).

Bewusst unter dem Paket ``crud`` abgelegt, damit der Modul-Reset in
``tests/conftest.py`` ohne Änderung greift. Alle Funktionen sind rein bzw.
arbeiten direkt auf der übergebenen DB-Session — kein HTTP-Wissen.
"""
import os
from datetime import datetime, date
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from models.task import Task, ShoppingItem, Routine


def _local_timezone():
    """Zeitzone aus der Umgebungsvariable ``TZ`` (setzt HA im Add-on-Container).

    Liefert bei fehlender oder ungültiger ``TZ`` ``None`` zurück (=> UTC).
    """
    tz_name = os.environ.get("TZ")
    if not tz_name:
        return None
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return None


def local_now() -> datetime:
    """Aktuelle lokale Zeit (naiv) in der ``TZ``-Zeitzone, Fallback UTC.

    Zentraler Helper, damit ``completed_at`` (Tasks) und ``last_completed_on``
    (Routinen) denselben lokalen Tagesbezug haben wie die Anzeige des Clients.
    """
    tz = _local_timezone()
    if tz is not None:
        return datetime.now(tz).replace(tzinfo=None)
    return datetime.utcnow()


def local_today() -> date:
    """Liefert das lokale Datum (``local_now().date()``)."""
    return local_now().date()


def _csv_to_weekdays(value: Optional[str]):
    """CSV-String ("0,2,4") -> sortierte Liste von ints. Defensiv bei Müll."""
    if not value:
        return []
    days = []
    for part in str(value).split(","):
        part = part.strip()
        if part == "":
            continue
        try:
            day = int(part)
        except ValueError:
            continue
        if 0 <= day <= 6 and day not in days:
            days.append(day)
    return sorted(days)


def is_routine_due(routine: Routine, today: date) -> bool:
    """Fälligkeitsregel einer Routine (siehe Plan D2).

    - inaktive Routinen sind nie fällig
    - daily (oder unbekannte Alt-Werte) sind immer fällig
    - weekly mit weekdays ist am gewählten Wochentag fällig
    - weekly ohne weekdays (Alt-Daten) ist am Wochentag von created_at fällig
    """
    if not routine.active:
        return False

    frequency = (routine.frequency or "daily").strip().lower()
    if frequency == "weekly":
        weekdays = _csv_to_weekdays(routine.weekdays)
        if weekdays:
            return today.weekday() in weekdays
        created_at = routine.created_at
        if created_at is None:
            return False
        return today.weekday() == created_at.weekday()

    # daily und unbekannte Alt-Werte werden wie "daily" behandelt.
    return True


def build_overview(db: Session, today: date, user_name: Optional[str]) -> dict:
    """Baut die komplette Übersicht mit genau drei Queries.

    Fortschrittsregel (Plan-Entscheidung): ``total`` = heute fällige +
    überfällige + heute erledigte Tasks + heute fällige Routinen. ``done`` =
    heute erledigte Tasks + heute erledigte fällige Routinen. Ein heute
    erledigter "Irgendwann"-Task zählt dadurch in ``done`` UND ``total``.
    """
    tasks = db.query(Task).all()
    routines = db.query(Routine).all()
    open_count = (
        db.query(ShoppingItem).filter(ShoppingItem.checked == False).count()  # noqa: E712
    )

    due_today = []
    overdue = []
    someday = []
    done_today = []

    for task in tasks:
        if task.completed:
            if task.completed_at is not None and task.completed_at.date() == today:
                done_today.append(task)
            # Alt-Daten: completed=True ohne completed_at zählen nicht.
            continue
        if task.due_date is None:
            someday.append(task)
        elif task.due_date == today:
            due_today.append(task)
        elif task.due_date < today:
            task.is_overdue = True
            overdue.append(task)
        # Zukunft: taucht in keiner Liste auf.

    overdue.sort(key=lambda t: t.due_date)

    routines_due = []
    for routine in routines:
        if is_routine_due(routine, today):
            routine.completed_today = routine.last_completed_on == today
            routines_due.append(routine)

    done = len(done_today) + sum(1 for r in routines_due if r.completed_today)
    total = len(due_today) + len(overdue) + len(done_today) + len(routines_due)
    percent = int(round(done * 100 / total)) if total > 0 else 0

    return {
        "today": today,
        "user_name": user_name,
        "tasks": {
            "due_today": due_today,
            "overdue": overdue,
            "someday": someday,
            "done_today": done_today,
        },
        "routines": routines_due,
        "shopping": {"open_count": open_count},
        "progress": {"done": done, "total": total, "percent": percent},
    }
