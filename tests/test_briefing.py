import pytest
from starlette.testclient import TestClient

def test_briefing_unauthorized(app_factory, addon_name):
    """Unauthentifizierter Abruf liefert 401."""
    app = app_factory(addon_name, password="geheim")
    with TestClient(app) as client:
        res = client.get("/api/briefing")
        assert res.status_code == 401

def test_briefing_success(client: TestClient, monkeypatch):
    """Briefing liefert Begrüßung und Zusammenfassung (auch wenn HA offline ist)."""
    res = client.get("/api/briefing")
    assert res.status_code == 200
    data = res.json()
    assert data["available"] is True
    assert "greeting" in data
    assert "summary" in data
    assert "time_of_day" in data
    assert isinstance(data["highlights"], list)
