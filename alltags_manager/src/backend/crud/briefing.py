r"""CRUD-Logik für das Daily Briefing.

Synthetisiert ein tägliches Briefing aus:
- Benutzername (via auth.get_user_name)
- Tageszeit (morning, day, evening) und passende Begrüßung
- Wetter (via crud.weather.fetch_weather_today)
- Home-Status Highlights (Türen, Fenster, Lichter, Waschmaschine via crud.home_status.fetch_home_status)
- Heutige offene Aufgaben/Routinen (via crud.overview.build_overview)
- Kalendertermine (via crud.ha.fetch_agenda)

Regelbasierter, prägnanter, motivierender deutscher Text (max. 2-3 Sätze)
mit robuster Fehlerbehandlung (Graceful Fallback).
"""
import logging
import os
from typing import List, Optional
from sqlalchemy.orm import Session

from auth import get_user_name
import crud.ha as ha
from crud.home_status import fetch_home_status, get_time_of_day
from crud.overview import build_overview, local_today
from crud.weather import fetch_weather_today
from schemas.briefing import BriefingResponse

logger = logging.getLogger(__name__)


def is_daily_briefing_enabled() -> bool:
    """Prüft, ob Daily Briefing aktiviert ist (default True)."""
    raw = os.environ.get("ALLTAGS_ENABLE_DAILY_BRIEFING")
    if raw is not None:
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    opt = ha._read_options().get("enable_daily_briefing")
    if opt is not None:
        return bool(opt)
    return True


async def generate_briefing(db: Session) -> BriefingResponse:
    """Generiert das Briefing für den heutigen Tag."""
    if not is_daily_briefing_enabled():
        return BriefingResponse(
            available=False,
            greeting="",
            summary="",
            time_of_day="day",
            highlights=[],
        )

    time_of_day = get_time_of_day()
    user_name = get_user_name()

    # 1. Begrüßung
    if time_of_day == "morning":
        base_greeting = f"Guten Morgen, {user_name}!" if user_name else "Guten Morgen!"
    elif time_of_day == "day":
        base_greeting = f"Hallo, {user_name}!" if user_name else "Hallo!"
    else:
        base_greeting = f"Guten Abend, {user_name}!" if user_name else "Guten Abend!"

    today = local_today()
    highlights: List[str] = []

    # 2. Daten sammeln (defensiv gegen Fehler)
    # Wetter
    weather_data = None
    try:
        weather_data = await fetch_weather_today()
    except Exception as e:
        logger.debug("Briefing: Failed to fetch weather: %s", e)

    # Home Status
    home_data = None
    try:
        home_data = await fetch_home_status()
    except Exception as e:
        logger.debug("Briefing: Failed to fetch home status: %s", e)

    # Kalendertermine
    agenda_data = None
    try:
        agenda_data = await ha.fetch_agenda(today)
    except Exception as e:
        logger.debug("Briefing: Failed to fetch agenda: %s", e)

    # Aufgaben & Routinen
    overview_data = None
    try:
        overview_data = build_overview(db, today, user_name)
    except Exception as e:
        logger.debug("Briefing: Failed to build overview: %s", e)

    # 3. Highlights & Sätze ableiten
    summary_parts: List[str] = []

    # A) Wetter-Highlights & Satz
    if weather_data and weather_data.available:
        temp_str = f"{weather_data.temperature:.1f}°C" if weather_data.temperature is not None else None
        if weather_data.forecast_today and weather_data.forecast_today.temperature is not None:
            max_temp = f"bis zu {weather_data.forecast_today.temperature:.0f}°C"
        else:
            max_temp = None

        if temp_str and max_temp:
            highlights.append(f"Wetter: {temp_str} (heute {max_temp})")
            if time_of_day == "morning":
                summary_parts.append(f"Draußen sind es gerade {temp_str} bei Aussichten auf {max_temp}.")
            else:
                summary_parts.append(f"Aktuell sind es {temp_str}.")
        elif temp_str:
            highlights.append(f"Wetter: {temp_str}")
            summary_parts.append(f"Aktuell hat es {temp_str}.")

    # B) Termine & Aufgaben
    event_count = len(agenda_data.get("events", [])) if agenda_data and agenda_data.get("available") else 0
    open_tasks = 0
    if overview_data:
        tasks_due = len(overview_data.get("tasks", {}).get("due_today", []))
        tasks_overdue = len(overview_data.get("tasks", {}).get("overdue", []))
        routines_due = sum(1 for r in overview_data.get("routines", []) if not getattr(r, "completed_today", False))
        open_tasks = tasks_due + tasks_overdue + routines_due

    task_event_text = []
    if event_count > 0:
        event_label = "1 Termin" if event_count == 1 else f"{event_count} Termine"
        highlights.append(f"Kalender: {event_label} heute")
        task_event_text.append(event_label)

    if open_tasks > 0:
        task_label = "1 offene Aufgabe" if open_tasks == 1 else f"{open_tasks} offene Aufgaben/Routinen"
        highlights.append(f"To-dos: {task_label}")
        task_event_text.append(task_label)

    if task_event_text:
        summary_parts.append(f"Für heute stehen {' sowie '.join(task_event_text)} an.")
    elif time_of_day == "evening":
        summary_parts.append("Für heute stehen keine offenen Aufgaben mehr an.")
    else:
        summary_parts.append("Für heute stehen keine dringenden Aufgaben oder Termine an.")

    # C) Home Status Highlights
    if home_data and home_data.available:
        if home_data.door and home_data.door.locked is False:
            highlights.append("Haustür ist unverschlossen")
        if home_data.windows and home_data.windows.open_count > 0:
            count = home_data.windows.open_count
            w_text = f"{count} Fenster offen" if count > 1 else "1 Fenster offen"
            highlights.append(w_text)
            if time_of_day == "evening":
                summary_parts.append(f"Hinweis: Es ist noch {w_text}.")
        if home_data.appliances and home_data.appliances.washing_machine_running:
            highlights.append("Waschmaschine läuft")
        if home_data.lights and home_data.lights.on_count > 0:
            count = home_data.lights.on_count
            l_text = f"{count} Lichter an" if count > 1 else "1 Licht an"
            highlights.append(l_text)

    # 4. Zusammenfassung bilden (max 2-3 Sätze)
    if not summary_parts:
        summary = "Alles ruhig und startklar für den Tag."
    else:
        summary = " ".join(summary_parts[:3])

    return BriefingResponse(
        available=True,
        greeting=base_greeting,
        summary=summary,
        time_of_day=time_of_day,
        highlights=highlights,
    )
