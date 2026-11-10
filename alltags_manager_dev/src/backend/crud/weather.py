r"""CRUD-Logik für Wetterdaten über den Home Assistant Core Proxy.

- Liest ALLTAGS_WEATHER_ENTITY aus env oder weather_entity aus options.json
- Validiert Entity Regex: ^weather\.[a-zA-Z0-9_\-\.]+$
- Wenn keine Entity konfiguriert oder kein SUPERVISOR_TOKEN vorhanden: return {"available": False}
- Liest aktuellen Zustand über HA Core Proxy /states/{entity_id} (temp, condition, humidity, wind)
- Liest heutige Vorhersage (min/max) via /services/weather/get_forecasts mit return_response=1 oder attributes fallback
- Liefert WeatherResponse
"""
import json
import logging
import os
import re
from typing import Optional

import httpx

import crud.ha as ha
from schemas.weather import WeatherForecast, WeatherResponse

logger = logging.getLogger(__name__)

_WEATHER_RE = re.compile(r"^weather\.[a-zA-Z0-9_\-\.]+$")


def get_configured_weather_entity() -> Optional[str]:
    """Liest die konfigurierte Wetter-Entity aus Env oder options.json und validiert sie."""
    raw = os.environ.get("ALLTAGS_WEATHER_ENTITY")
    if raw is None:
        raw = ha._read_options().get("weather_entity")

    if not raw or not isinstance(raw, str):
        return None

    entity_id = raw.strip()
    if not _WEATHER_RE.match(entity_id):
        return None
    return entity_id


async def fetch_weather_today() -> WeatherResponse:
    """Holt die aktuellen Wetterdaten und Vorhersage von Home Assistant."""
    entity_id = get_configured_weather_entity()
    token = ha.get_ha_token()

    if not entity_id or not token:
        return WeatherResponse(available=False)

    try:
        async with ha.make_client() as client:
            # 1. Aktuellen Zustand abfragen
            state_resp = await client.get(f"/states/{entity_id}")
            if state_resp.status_code != 200:
                logger.warning("HA state call for %s failed: %s", entity_id, state_resp.status_code)
                return WeatherResponse(available=False)

            state_data = state_resp.json()
            condition = state_data.get("state")
            attrs = state_data.get("attributes", {})

            temperature = attrs.get("temperature")
            humidity = attrs.get("humidity")
            wind_speed = attrs.get("wind_speed")

            # Typkonvertierungen
            try:
                temperature = float(temperature) if temperature is not None else None
            except (ValueError, TypeError):
                temperature = None

            try:
                humidity = float(humidity) if humidity is not None else None
            except (ValueError, TypeError):
                humidity = None

            try:
                wind_speed = float(wind_speed) if wind_speed is not None else None
            except (ValueError, TypeError):
                wind_speed = None

            # 2. Vorhersage (Forecast) ermitteln
            # Erst modern via /services/weather/get_forecasts probieren, Fallback auf attributes.forecast
            forecast_today = None
            forecast_list = None

            try:
                service_resp = await client.post(
                    "/services/weather/get_forecasts?return_response=1",
                    json={"entity_id": entity_id, "type": "daily"},
                )
                if service_resp.status_code == 200:
                    svc_data = service_resp.json()
                    # Struktur: {"service_response": {entity_id: {"forecast": [...]}}}
                    svc_resp = svc_data.get("service_response", {})
                    ent_data = svc_resp.get(entity_id, {})
                    if "forecast" in ent_data:
                        forecast_list = ent_data.get("forecast")
            except Exception as e:
                logger.debug("weather.get_forecasts service call failed: %s", e)

            if forecast_list is None:
                # Fallback auf veraltetes attributes.forecast
                if "forecast" in attrs and isinstance(attrs["forecast"], list):
                    forecast_list = attrs["forecast"]

            if forecast_list and len(forecast_list) > 0:
                today_fc = forecast_list[0]
                fc_condition = today_fc.get("condition")
                fc_templow = today_fc.get("templow")
                fc_temp = today_fc.get("temperature")

                try:
                    fc_templow = float(fc_templow) if fc_templow is not None else None
                except (ValueError, TypeError):
                    fc_templow = None

                try:
                    fc_temp = float(fc_temp) if fc_temp is not None else None
                except (ValueError, TypeError):
                    fc_temp = None

                forecast_today = WeatherForecast(
                    condition=fc_condition,
                    templow=fc_templow,
                    temperature=fc_temp,
                )

            return WeatherResponse(
                available=True,
                condition=condition,
                temperature=temperature,
                humidity=humidity,
                wind_speed=wind_speed,
                forecast_today=forecast_today,
            )
    except ha.HAUnavailable:
        return WeatherResponse(available=False)
    except Exception as exc:
        logger.warning("Error fetching weather from HA: %s", exc)
        return WeatherResponse(available=False)
