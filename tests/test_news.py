import pytest
from starlette.testclient import TestClient

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
    <title>Good News</title>
    <link>https://goodnews.eu/</link>
    <description>Täglich gute Nachrichten</description>
    <item>
        <title>Sensationeller Erfolg im Naturschutz</title>
        <link>https://goodnews.eu/naturschutz-erfolg/</link>
        <pubDate>Tue, 10 Nov 2026 12:00:00 +0000</pubDate>
        <description><![CDATA[<p>Forscher berichten von &lt;b&gt;großartigen&lt;/b&gt; Fortschritten bei der Aufforstung.</p>]]></description>
    </item>
    <item>
        <title>Neue Solartechnologie halbiert Kosten</title>
        <link>https://goodnews.eu/solar-kosten/</link>
        <pubDate>Mon, 09 Nov 2026 15:00:00 +0000</pubDate>
        <description>Eine revolutionäre Zelle steigert den Wirkungsgrad signifikant.</description>
    </item>
</channel>
</rss>
"""


def test_positive_news_unauthorized(app_factory, addon_name):
    """Unauthentifizierter Abruf muss 401 liefern (wenn Passwort gesetzt)."""
    app = app_factory(addon_name, password="geheim")
    with TestClient(app) as client:
        res = client.get("/api/news/positive")
        assert res.status_code == 401


def test_positive_news_success(client: TestClient, monkeypatch):
    """Parst XML korrekt, strippt HTML und liefert NewsResponse."""
    import crud.news as news_crud
    news_crud.clear_news_cache()

    class MockResponse:
        status_code = 200
        text = SAMPLE_RSS

    async def mock_get(self, url):
        return MockResponse()

    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)

    res = client.get("/api/news/positive")
    assert res.status_code == 200
    data = res.json()
    assert data["available"] is True
    assert len(data["items"]) == 2
    assert data["items"][0]["title"] == "Sensationeller Erfolg im Naturschutz"
    assert data["items"][0]["link"] == "https://goodnews.eu/naturschutz-erfolg/"
    assert "<p>" not in data["items"][0]["summary"]
    assert "<b>" not in data["items"][0]["summary"]


def test_positive_news_caching(client: TestClient, monkeypatch):
    """In-Memory-Cache verhindert erneuten Request innerhalb TTL."""
    import crud.news as news_crud
    news_crud.clear_news_cache()

    call_count = 0

    class MockResponse:
        status_code = 200
        text = SAMPLE_RSS

    async def mock_get(self, url):
        nonlocal call_count
        call_count += 1
        return MockResponse()

    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)

    res1 = client.get("/api/news/positive")
    assert res1.status_code == 200
    assert call_count == 1

    res2 = client.get("/api/news/positive")
    assert res2.status_code == 200
    assert call_count == 1


def test_positive_news_graceful_degradation(client: TestClient, monkeypatch):
    """Bei Netzwerk- oder Parserfehler graceful available: False (kein 500)."""
    import crud.news as news_crud
    news_crud.clear_news_cache()

    async def mock_failing_get(self, url):
        raise RuntimeError("Network offline")

    monkeypatch.setattr("httpx.AsyncClient.get", mock_failing_get)

    res = client.get("/api/news/positive")
    assert res.status_code == 200
    data = res.json()
    assert data["available"] is False
    assert data["items"] == []
