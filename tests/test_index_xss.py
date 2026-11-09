"""T2.7: XSS-Fix in serve_index — Ingress-Pfad-Validierung."""
from fastapi.testclient import TestClient


def test_invalid_ingress_path_is_not_embedded(app_factory, addon_name):
    app = app_factory(addon_name)
    payloads = ['"; alert(1); //', "</script>", "javascript:alert(1)", "<img src=x onerror=alert(1)>"]
    with TestClient(app) as client:
        for payload in payloads:
            response = client.get("/", headers={"X-Ingress-Path": payload})
            assert response.status_code == 200
            assert "alert(1)" not in response.text
            # Ungültiger Pfad -> leerer Fallback.
            assert '"INGRESS_PATH": ""' in response.text


def test_valid_ingress_path_is_embedded(app_factory, addon_name):
    app = app_factory(addon_name)
    with TestClient(app) as client:
        response = client.get("/", headers={"X-Ingress-Path": "/api/hassio_ingress/abc123"})
        assert response.status_code == 200
        assert '"/api/hassio_ingress/abc123"' in response.text
