"""T2.6: Ingress-Vertrauen auf bekannte Client-IP beschränken."""
from fastapi.testclient import TestClient

INGRESS_HEADER = {"X-Ingress-Path": "/api/hassio_ingress/tok"}


def test_ingress_header_from_untrusted_ip_is_rejected(app_factory, addon_name):
    # Vertraute IP ist 172.30.32.2, TestClient kommt von "testclient".
    app = app_factory(addon_name, password="geheim", trusted_ips="172.30.32.2")
    with TestClient(app) as client:
        assert client.get("/tasks/", headers=INGRESS_HEADER).status_code == 401


def test_ingress_header_from_trusted_ip_is_allowed(app_factory, addon_name):
    app = app_factory(addon_name, password="geheim", trusted_ips="testclient")
    with TestClient(app) as client:
        assert client.get("/tasks/", headers=INGRESS_HEADER).status_code == 200


def test_ingress_default_only_trusts_ha_ip(app_factory, addon_name):
    # Ohne explizite trusted_ips gilt der Default (172.30.32.2) -> testclient wird
    # trotz Ingress-Header abgewiesen.
    app = app_factory(addon_name, password="geheim")
    with TestClient(app) as client:
        assert client.get("/api/auth/status", headers=INGRESS_HEADER).status_code == 401
