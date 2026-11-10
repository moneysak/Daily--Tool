"""Tests für den Home-Status Endpunkt /api/ha/status."""
import httpx
import pytest
from starlette.testclient import TestClient


def test_home_status_unauthorized(app_factory, addon_name):
    """Unauthentifizierter Abruf liefert 401 wenn Passwort gesetzt."""
    app = app_factory(addon_name, password="test-password")
    with TestClient(app) as client:
        res = client.get("/api/ha/status")
        assert res.status_code == 401


def test_home_status_no_supervisor_token(client: TestClient, monkeypatch):
    """Ohne SUPERVISOR_TOKEN -> available: False."""
    monkeypatch.delenv("SUPERVISOR_TOKEN", raising=False)
    res = client.get("/api/ha/status")
    assert res.status_code == 200
    data = res.json()
    assert data["available"] is False


def test_home_status_disabled_via_env(client: TestClient, monkeypatch):
    """Wenn enable_home_status False ist -> available: False."""
    monkeypatch.setenv("ALLTAGS_ENABLE_HOME_STATUS", "false")
    monkeypatch.setenv("SUPERVISOR_TOKEN", "mock-token")
    res = client.get("/api/ha/status")
    assert res.status_code == 200
    assert res.json()["available"] is False


def test_home_status_success(client: TestClient, monkeypatch):
    """Erfolgreicher Abruf mit Mocks für alle Entities."""
    import crud.ha as ha_crud

    monkeypatch.setenv("SUPERVISOR_TOKEN", "mock-token")
    monkeypatch.setenv("ALLTAGS_LOCK_ENTITY", "lock.nuki")
    monkeypatch.setenv("ALLTAGS_DOOR_SENSOR_ENTITY", "binary_sensor.nuki_door_sensor")
    monkeypatch.setenv("ALLTAGS_WASHING_MACHINE_ENTITY", "binary_sensor.washing_machine_running")

    mock_states = [
        # Lock
        {"entity_id": "lock.nuki", "state": "locked"},
        # Door sensor
        {"entity_id": "binary_sensor.nuki_door_sensor", "state": "off"},
        # Windows
        {
            "entity_id": "binary_sensor.kitchen_open_window_detected",
            "state": "on",
            "attributes": {"friendly_name": "Küche Fenster"},
        },
        {
            "entity_id": "binary_sensor.living_room_open_window_detected",
            "state": "off",
            "attributes": {"friendly_name": "Wohnzimmer Fenster"},
        },
        # Lights
        {"entity_id": "light.living_room", "state": "on"},
        {"entity_id": "light.bedroom", "state": "off"},
        {"entity_id": "light.camera_status_led", "state": "on"},  # sollte ignoriert werden
        {"entity_id": "light.driveway_floodlight", "state": "on"},  # sollte ignoriert werden
        # Climate
        {
            "entity_id": "climate.living_room",
            "state": "heat",
            "attributes": {"current_temperature": 21.0, "temperature": 22.0},
        },
        {
            "entity_id": "climate.kitchen",
            "state": "heat",
            "attributes": {"current_temperature": 19.0, "temperature": 20.0},
        },
        {
            "entity_id": "climate.offline",
            "state": "unavailable",
            "attributes": {"current_temperature": 10.0, "temperature": 10.0},
        },
        # Appliance
        {"entity_id": "binary_sensor.washing_machine_running", "state": "on"},
    ]

    def mock_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/states"):
            return httpx.Response(200, json=mock_states)
        return httpx.Response(404)

    def mock_client_factory():
        return httpx.AsyncClient(
            transport=httpx.MockTransport(mock_handler),
            base_url="http://supervisor/core/api",
        )

    monkeypatch.setattr(ha_crud, "make_client", mock_client_factory)

    res = client.get("/api/ha/status")
    assert res.status_code == 200
    data = res.json()
    assert data["available"] is True

    # Door
    assert data["door"]["locked"] is True
    assert data["door"]["open"] is False

    # Windows
    assert data["windows"]["open_count"] == 1
    assert data["windows"]["open_windows"] == ["Küche Fenster"]

    # Lights
    assert data["lights"]["on_count"] == 1

    # Climate (avg of 21.0 & 19.0 = 20.0, avg target of 22.0 & 20.0 = 21.0)
    assert data["climate"]["current_temperature"] == 20.0
    assert data["climate"]["target_temperature"] == 21.0

    # Appliance
    assert data["appliances"]["washing_machine_running"] is True
