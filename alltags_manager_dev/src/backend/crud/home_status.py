r"""CRUD-Logik für Home-Status über den Home Assistant Core Proxy.

- Liest Optionen / Env:
  - enable_home_status (default True)
  - lock_entity (default "lock.nuki")
  - door_sensor_entity (default "binary_sensor.nuki_door_sensor")
  - washing_machine_entity (default "binary_sensor.washing_machine_running")
- Holt alle States per GET /states in einem einzigen Roundtrip.
- Falls kein Token, HA unerreichbar oder enable_home_status False -> HomeStatusResponse(available=False).
- Ermittelt:
  - door: lock_entity -> locked/unlocked, door_sensor_entity -> on(open=True)/off(open=False)
  - windows: ^binary_sensor\..*_open_window_detected$ mit state == "on" -> open_count und Friendly Name / entity_id
  - lights: light.* mit state == "on", ignoriert Status-/Indikator-LEDs (z.B. "status_led" in entity_id oder "floodlight")
  - climate: climate.* mit state != "unavailable", Durchschnitt von current_temperature und target_temperature
  - appliances: washing_machine_entity mit state == "on"
"""
import logging
import os
import re
from typing import Dict, List, Optional

import crud.ha as ha
from crud.overview import local_now
from schemas.home_status import (
    ApplianceStatus,
    ClimateStatus,
    DoorStatus,
    HomeStatusResponse,
    LightStatus,
    WindowStatus,
)

logger = logging.getLogger(__name__)

_WINDOW_RE = re.compile(r"^binary_sensor\..*_open_window_detected$")


def is_home_status_enabled() -> bool:
    """Prüft, ob Home Status in Env oder options.json aktiviert ist."""
    raw = os.environ.get("ALLTAGS_ENABLE_HOME_STATUS")
    if raw is not None:
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    opt = ha._read_options().get("enable_home_status")
    if opt is not None:
        return bool(opt)
    return True


def get_configured_entities() -> Dict[str, Optional[str]]:
    """Liest Entity-IDs für Lock, Door Sensor und Washing Machine."""
    options = ha._read_options()
    lock_ent = os.environ.get("ALLTAGS_LOCK_ENTITY") or options.get("lock_entity") or "lock.nuki"
    door_ent = os.environ.get("ALLTAGS_DOOR_SENSOR_ENTITY") or options.get("door_sensor_entity") or "binary_sensor.nuki_door_sensor"
    wm_ent = os.environ.get("ALLTAGS_WASHING_MACHINE_ENTITY") or options.get("washing_machine_entity") or "binary_sensor.washing_machine_running"
    return {
        "lock": str(lock_ent).strip() if lock_ent else None,
        "door_sensor": str(door_ent).strip() if door_ent else None,
        "washing_machine": str(wm_ent).strip() if wm_ent else None,
    }


def get_time_of_day() -> str:
    """Bestimmt Tageszeit: morning (06-11), day (11-17), evening (17-06) basierend auf local_now()."""
    hour = local_now().hour
    if 6 <= hour < 11:
        return "morning"
    elif 11 <= hour < 17:
        return "day"
    else:
        return "evening"


async def fetch_home_status() -> HomeStatusResponse:
    """Liest alle Zustände via HA Core Proxy /states und erzeugt HomeStatusResponse."""
    if not is_home_status_enabled():
        return HomeStatusResponse(available=False)

    token = ha.get_ha_token()
    if not token:
        return HomeStatusResponse(available=False)

    try:
        async with ha.make_client() as client:
            resp = await client.get("/states")
            if resp.status_code != 200:
                logger.warning("HA GET /states failed: %s", resp.status_code)
                return HomeStatusResponse(available=False)
            states: List[dict] = resp.json()
    except Exception as e:
        logger.warning("Error fetching HA states: %s", e)
        return HomeStatusResponse(available=False)

    states_by_id: Dict[str, dict] = {
        s.get("entity_id", ""): s for s in states if isinstance(s, dict) and "entity_id" in s
    }

    configured = get_configured_entities()

    # 1. Door / Lock
    door_status = DoorStatus()
    lock_id = configured.get("lock")
    if lock_id and lock_id in states_by_id:
        lock_state = states_by_id[lock_id].get("state")
        if lock_state == "locked":
            door_status.locked = True
        elif lock_state == "unlocked":
            door_status.locked = False

    door_sensor_id = configured.get("door_sensor")
    if door_sensor_id and door_sensor_id in states_by_id:
        door_sensor_state = states_by_id[door_sensor_id].get("state")
        if door_sensor_state == "on":
            door_status.open = True
        elif door_sensor_state == "off":
            door_status.open = False

    # 2. Windows
    open_windows: List[str] = []
    for ent_id, ent_data in states_by_id.items():
        if _WINDOW_RE.match(ent_id) and ent_data.get("state") == "on":
            attrs = ent_data.get("attributes", {})
            friendly_name = attrs.get("friendly_name")
            if not friendly_name:
                # Fallback: Extrahiere Name aus Entity-ID
                friendly_name = ent_id.replace("binary_sensor.", "").replace("_open_window_detected", "").replace("_", " ").title()
            open_windows.append(friendly_name)

    window_status = WindowStatus(
        open_count=len(open_windows),
        open_windows=sorted(open_windows),
    )

    # 3. Lights
    lights_on = 0
    for ent_id, ent_data in states_by_id.items():
        if ent_id.startswith("light."):
            # Ignoriere Status-/Indikator-LEDs oder Flutlichter von Kameras
            ent_lower = ent_id.lower()
            if "status_led" in ent_lower or "indicator" in ent_lower or "floodlight" in ent_lower:
                continue
            if ent_data.get("state") == "on":
                lights_on += 1

    light_status = LightStatus(on_count=lights_on)

    # 4. Climate
    current_temps: List[float] = []
    target_temps: List[float] = []
    for ent_id, ent_data in states_by_id.items():
        if ent_id.startswith("climate."):
            state_val = ent_data.get("state")
            if state_val in {"unavailable", "unknown"}:
                continue
            attrs = ent_data.get("attributes", {})
            curr_t = attrs.get("current_temperature")
            targ_t = attrs.get("temperature")  # HA Standard für Climate-Target
            if targ_t is None:
                targ_t = attrs.get("target_temperature")

            if curr_t is not None:
                try:
                    current_temps.append(float(curr_t))
                except (ValueError, TypeError):
                    pass
            if targ_t is not None:
                try:
                    target_temps.append(float(targ_t))
                except (ValueError, TypeError):
                    pass

    climate_status = ClimateStatus(
        current_temperature=round(sum(current_temps) / len(current_temps), 1) if current_temps else None,
        target_temperature=round(sum(target_temps) / len(target_temps), 1) if target_temps else None,
    )

    # 5. Appliances (Washing Machine)
    appliance_status = ApplianceStatus()
    wm_id = configured.get("washing_machine")
    if wm_id and wm_id in states_by_id:
        wm_state = states_by_id[wm_id].get("state")
        if wm_state in {"on", "running", "true"}:
            appliance_status.washing_machine_running = True
        elif wm_state in {"off", "false"}:
            appliance_status.washing_machine_running = False

    return HomeStatusResponse(
        available=True,
        door=door_status,
        windows=window_status,
        lights=light_status,
        climate=climate_status,
        appliances=appliance_status,
    )
