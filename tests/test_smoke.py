"""Smoke-Tests: prüfen Basis-Endpunkte beider Add-ons mit temporärer DB.

Es werden nur Endpunkte geprüft, die in beiden Add-ons vorhanden sind
(``/``, ``/tasks/``, ``/api/auth/status``).
"""
import os


def test_data_dir_uses_tmp_path(addon, tmp_path):
    """Die Test-DB liegt im tmp_path, nicht unter /data."""
    from db import database

    assert database.DATA_DIR == str(tmp_path)
    assert str(database.DB_PATH).startswith(str(tmp_path))
    assert os.path.isdir(tmp_path)


def test_index_serves_html(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    # Ingress-Injection-Script ist im HTML enthalten.
    assert "APP_CONFIG" in response.text


def test_tasks_list_available(client):
    response = client.get("/tasks/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_open_mode_auth_status(client):
    response = client.get("/api/auth/status")
    assert response.status_code == 200
    body = response.json()
    assert body["authenticated"] is True
