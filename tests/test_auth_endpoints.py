"""T2.5: Login/Logout-Endpunkte und Schutz aller Endpunkte."""
from fastapi.testclient import TestClient


def test_login_wrong_password_returns_401(app_factory, addon_name):
    app = app_factory(addon_name, password="geheim")
    with TestClient(app) as client:
        r = client.post("/api/auth/login", json={"password": "falsch"})
        assert r.status_code == 401


def test_login_success_returns_working_token(app_factory, addon_name):
    app = app_factory(addon_name, password="geheim")
    with TestClient(app) as client:
        r = client.post("/api/auth/login", json={"password": "geheim"})
        assert r.status_code == 200
        token = r.json()["token"]
        assert token

        headers = {"Authorization": f"Bearer {token}"}
        assert client.get("/tasks/", headers=headers).status_code == 200
        assert client.get("/api/auth/status", headers=headers).status_code == 200


def test_protected_endpoint_without_token_401(app_factory, addon_name):
    app = app_factory(addon_name, password="geheim")
    with TestClient(app) as client:
        assert client.get("/tasks/").status_code == 401
        # Klartext-Passwort als Token ist nicht mehr gültig.
        assert client.get("/tasks/", headers={"Authorization": "Bearer geheim"}).status_code == 401
        assert client.get("/tasks/", headers={"X-Auth-Token": "geheim"}).status_code == 401


def test_logout_revokes_token(app_factory, addon_name):
    app = app_factory(addon_name, password="geheim")
    with TestClient(app) as client:
        token = client.post("/api/auth/login", json={"password": "geheim"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        assert client.get("/tasks/", headers=headers).status_code == 200
        assert client.post("/api/auth/logout", headers=headers).status_code == 200
        assert client.get("/tasks/", headers=headers).status_code == 401


def test_all_endpoints_are_protected(app_factory, addon_name):
    app = app_factory(addon_name, password="geheim")
    cases = [
        ("GET", "/tasks/", None),
        ("POST", "/tasks/", {"title": "x", "completed": False}),
        ("PUT", "/tasks/1", {"completed": True}),
        ("DELETE", "/tasks/1", None),
        ("GET", "/api/shopping/", None),
        ("POST", "/api/shopping/", {"name": "x", "quantity": "1", "checked": False}),
        ("GET", "/api/routines/", None),
        ("POST", "/api/routines/", {"title": "x", "frequency": "daily", "active": True, "completed_today": False}),
        ("GET", "/api/auth/status", None),
        ("POST", "/api/hermes/chat", {"message": "hi"}),
    ]
    with TestClient(app) as client:
        for method, url, body in cases:
            response = client.request(method, url, json=body)
            assert response.status_code == 401, f"{method} {url} -> {response.status_code}"


def test_login_rate_limited_after_five_failures(app_factory, addon_name):
    """Nach 5 Fehlversuchen wird die IP gesperrt (429), auch für korrektes Passwort."""
    app = app_factory(addon_name, password="geheim")
    with TestClient(app) as client:
        for _ in range(5):
            r = client.post("/api/auth/login", json={"password": "falsch"})
            assert r.status_code == 401
        # 6. Versuch: gesperrt.
        assert client.post("/api/auth/login", json={"password": "falsch"}).status_code == 429
        # Auch das richtige Passwort wird während der Sperre abgewiesen.
        assert client.post("/api/auth/login", json={"password": "geheim"}).status_code == 429


def test_login_success_resets_failure_counter(app_factory, addon_name):
    """Ein erfolgreicher Login setzt den Fehlversuchs-Zähler der IP zurück."""
    app = app_factory(addon_name, password="geheim")
    with TestClient(app) as client:
        for _ in range(4):
            assert client.post("/api/auth/login", json={"password": "falsch"}).status_code == 401
        assert client.post("/api/auth/login", json={"password": "geheim"}).status_code == 200
        # Zähler zurückgesetzt: erneut 4 Fehlversuche bleiben erlaubt (401, nicht 429).
        for _ in range(4):
            assert client.post("/api/auth/login", json={"password": "falsch"}).status_code == 401
