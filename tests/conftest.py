"""Gemeinsame pytest-Fixtures für beide Alltags-Manager-Add-ons.

Die Fixture ``addon`` ist über die beiden Add-on-Verzeichnisse parametrisiert
(Dev und Prod). Pro Testlauf werden sys.path und die geladenen App-Module
zurückgesetzt, damit beide Add-ons unabhängig voneinander importiert werden
können (sie nutzen identische Modulnamen wie ``main``, ``db``, ``crud`` ...).

``ALLTAGS_DATA_DIR`` zeigt auf ``tmp_path`` — kein Test schreibt nach /data.
"""
import importlib
import json
import os
import sys

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Beide Add-ons teilen sich dieselbe Backend-Modulstruktur (Top-Level-Pakete
# unter src/backend), daher müssen die Module zwischen Läufen zurückgesetzt
# werden.
ADDONS = ["alltags_manager_dev", "alltags_manager"]

# Wurzelmodule und Untermodule der App (Details werden beim Import nachgeladen).
APP_MODULES = [
    "main",
    "auth",
    "db",
    "db.database",
    "crud",
    "crud.task",
    "crud.overview",
    "crud.ha",
    "crud.news",
    "crud.weather",
    "crud.home_status",
    "crud.briefing",
    "models",
    "models.task",
    "models.session",
    "schemas",
    "schemas.task",
    "schemas.overview",
    "schemas.ha",
    "schemas.news",
    "schemas.weather",
    "schemas.home_status",
    "schemas.briefing",
]


def _clear_app_modules():
    for mod in APP_MODULES:
        sys.modules.pop(mod, None)
    # Verbleibende Untermodule (z.B. db.xyz) entfernen.
    for name in list(sys.modules):
        if name.split(".")[0] in {"main", "auth", "db", "crud", "models", "schemas"}:
            sys.modules.pop(name, None)


@pytest.fixture(params=ADDONS)
def addon(request, tmp_path, monkeypatch):
    """Importiert ``main`` des parametrisierten Add-ons und liefert die ASGI-App."""
    addon_name = request.param
    backend_dir = os.path.join(REPO_ROOT, addon_name, "src", "backend")

    assert os.path.isdir(backend_dir), f"Backend nicht gefunden: {backend_dir}"

    monkeypatch.syspath_prepend(backend_dir)
    monkeypatch.setenv("ALLTAGS_DATA_DIR", str(tmp_path))

    # Deterministischer offener Modus: kein Passwort aus Umgebung/options.json.
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    monkeypatch.setenv(
        "ALLTAGS_OPTIONS_PATH", str(tmp_path / "nonexistent-options.json")
    )

    _clear_app_modules()
    try:
        main = importlib.import_module("main")
        yield main.app
    finally:
        _clear_app_modules()


@pytest.fixture
def client(addon):
    """TestClient gegen die App des jeweiligen Add-ons."""
    with TestClient(addon) as test_client:
        yield test_client


@pytest.fixture(params=ADDONS)
def addon_name(request):
    """Parametrisiert Auth-Tests über beide Add-ons (Dev und Prod)."""
    return request.param


@pytest.fixture
def app_factory(monkeypatch, tmp_path):
    """Lädt ein Add-on mit frei wählbaren Auth-Umgebungsvariablen.

    Rückgabe: ``load(addon_name=..., password=None, options=None,
    trusted_ips=None, data_dir=None)`` liefert die importierte ASGI-App.

    ``password`` setzt ``APP_PASSWORD``; ``options`` schreibt eine
    ``options.json`` (``app_password``) in das Datenverzeichnis. Ohne beides
    läuft das Add-on im offenen Modus. ``data_dir`` erlaubt dieselbe DB über
    mehrere ``load``-Aufrufe hinweg (Persistenz-Test).
    """
    counter = {"n": 0}

    def load(
        addon_name=ADDONS[0],
        password=None,
        options=None,
        trusted_ips=None,
        data_dir=None,
    ):
        backend_dir = os.path.join(REPO_ROOT, addon_name, "src", "backend")
        assert os.path.isdir(backend_dir), f"Backend nicht gefunden: {backend_dir}"

        if data_dir is None:
            data_dir = tmp_path / f"data-{counter['n']}"
            counter["n"] += 1
        data_dir = str(data_dir)
        os.makedirs(data_dir, exist_ok=True)

        monkeypatch.syspath_prepend(backend_dir)
        monkeypatch.setenv("ALLTAGS_DATA_DIR", data_dir)
        monkeypatch.setenv("ALLTAGS_OPTIONS_PATH", os.path.join(data_dir, "options.json"))
        monkeypatch.delenv("ALLTAGS_INGRESS_TRUSTED_IPS", raising=False)
        monkeypatch.delenv("APP_PASSWORD", raising=False)

        if trusted_ips is not None:
            monkeypatch.setenv("ALLTAGS_INGRESS_TRUSTED_IPS", trusted_ips)
        if password is not None:
            monkeypatch.setenv("APP_PASSWORD", password)
        if options is not None:
            with open(os.path.join(data_dir, "options.json"), "w", encoding="utf-8") as fh:
                json.dump(options, fh)

        _clear_app_modules()
        main = importlib.import_module("main")
        return main.app

    yield load
    _clear_app_modules()
