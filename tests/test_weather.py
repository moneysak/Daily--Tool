import pytest
import httpx
from starlette.testclient import TestClient


def test_weather_unauthorized(app_factory, addon_name):
    """Unauthentifizierter Abruf liefert 401 (wenn Passwort gesetzt)."""
    app = app_factory(addon_name, password="geheim")
    with TestClient(app) as client:
        res = client.get("/api/weather/today")
        assert res.status_code == 401


def test_weather_not_configured(client: TestClient, monkeypatch):
    """Wenn keine weather_entity konfiguriert ist -> available: False."""
    import crud.weather as weather_crud
    import crud.ha as ha_crud

    monkeypatch.delenv("ALLTAGS_WEATHER_ENTITY", raising=False)
    monkeypatch.setattr(ha_crud, "_read_options", lambda: {})

    res = client.get("/api/weather/today")
    assert res.status_code == 200
    data = res.json()
    assert data["available"] is False


def test_weather_no_supervisor_token(client: TestClient, monkeypatch):
    """Wenn SUPERVISOR_TOKEN fehlt -> available: False."""
    monkeypatch.setenv("ALLTAGS_WEATHER_ENTITY", "weather.forecast_home")
    monkeypatch.delenv("SUPERVISOR_TOKEN", raising=False)

    res = client.get("/api/weather/today")
    assert res.status_code == 200
    assert res.json()["available"] is False


def test_weather_success(client: TestClient, monkeypatch):
    """Erfolgreicher Abruf mit Mocks für State und Forecast."""
    import crud.ha as ha_crud

    monkeypatch.setenv("ALLTAGS_WEATHER_ENTITY", "weather.weather_dwd")
    monkeypatch.setenv("SUPERVISOR_TOKEN", "mock-token")

    def mock_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "/states/weather.weather_dwd" in url_str:
            return httpx.Response(200, json={
                "entity_id": "weather.weather_dwd",
                "state": "partlycloudy",
                "attributes": {
                    "temperature": 18.5,
                    "temperature_unit": "°C",
                    "humidity": 65,
                    "wind_speed": 12.0,
                    "wind_speed_unit": "km/h"
                }
            })
        elif "/services/weather/get_forecasts" in url_str:
            return httpx.Response(200, json={
                "service_response": {
                    "weather.weather_dwd": {
                        "forecast": [
                            {
                                "condition": "partlycloudy",
                                "templow": 11.0,
                                "temperature": 21.0
                            }
                        ]
                    }
                }
            })
        return httpx.Response(404)

    def mock_client_factory():
        return httpx.AsyncClient(
            transport=httpx.MockTransport(mock_handler),
            base_url="http://supervisor/core/api"
        )

    monkeypatch.setattr(ha_crud, "make_client", mock_client_factory)

    res = client.get("/api/weather/today")
    assert res.status_code == 200
    data = res.json()
    assert data["available"] is True
    assert data["condition"] == "partlycloudy"
    assert data["temperature"] == 18.5
    assert data["humidity"] == 65
    assert data["wind_speed"] == 12.0
    assert data["forecast_today"] is not None
    assert data["forecast_today"]["templow"] == 11.0
    assert data["forecast_today"]["temperature"] == 21.0
