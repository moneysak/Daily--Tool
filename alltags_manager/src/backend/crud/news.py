"""CRUD-Logik für Gute Nachrichten (Good News RSS Feed).

- Fetcht https://goodnews.eu/feed/ mit httpx.AsyncClient(timeout=5.0)
- Parst RSS XML mit xml.etree.ElementTree
- Filtert / entfernt HTML-Tags aus description / summary
- In-Memory-Cache für 3600 Sekunden (1 Stunde)
- Graceful Fallback: liefert {"available": False, "items": []} bei Fehlern/Offline
"""
import html
import logging
import re
import time
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

import httpx

from schemas.news import NewsItem, NewsResponse

logger = logging.getLogger(__name__)

GOOD_NEWS_FEED_URL = "https://goodnews.eu/feed/"
FEED_TIMEOUT = 5.0
CACHE_TTL = 3600  # 1 Stunde

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")

# In-Memory-Cache: {"timestamp": float, "data": NewsResponse}
_NEWS_CACHE: Dict[str, Optional[object]] = {
    "timestamp": 0.0,
    "data": None,
}


def strip_html(text: Optional[str]) -> str:
    """Entfernt HTML-Tags (auch mehrfach encoded), löst Entities auf und normalisiert Whitespace."""
    if not text:
        return ""
    # Erst Entities auflösen (&lt;b&gt; -> <b>), dann Tags entfernen
    decoded = html.unescape(text)
    clean = _TAG_RE.sub(" ", decoded)
    clean = html.unescape(clean)
    clean = _WHITESPACE_RE.sub(" ", clean).strip()
    return clean


def parse_rss_feed(content: str, max_items: int = 4) -> List[NewsItem]:
    """Parst RSS-XML-String und liefert eine Liste von NewsItem zurück."""
    root = ET.fromstring(content)
    # Typischerweise rss -> channel -> item
    items: List[NewsItem] = []
    
    channel = root.find("channel")
    item_nodes = channel.findall("item") if channel is not None else root.findall(".//item")
    
    for item_node in item_nodes[:max_items]:
        title_node = item_node.find("title")
        link_node = item_node.find("link")
        desc_node = item_node.find("description")
        pub_node = item_node.find("pubDate")
        
        title = strip_html(title_node.text) if title_node is not None and title_node.text else "Gute Nachricht"
        link = (link_node.text or "").strip() if link_node is not None and link_node.text else ""
        if not (link.startswith("http://") or link.startswith("https://")):
            link = ""
        summary = strip_html(desc_node.text) if desc_node is not None and desc_node.text else None
        published = pub_node.text.strip() if pub_node is not None and pub_node.text else None
        
        # Falls summary zu lang ist (z. B. Teaser), kürzen
        if summary and len(summary) > 280:
            summary = summary[:277] + "..."
            
        items.append(NewsItem(
            title=title,
            link=link,
            summary=summary,
            published=published,
        ))
    return items


async def fetch_positive_news(client: Optional[httpx.AsyncClient] = None) -> NewsResponse:
    """Holt die neuesten positiven Nachrichten (mit In-Memory-Cache)."""
    now = time.time()
    cached_data = _NEWS_CACHE.get("data")
    cached_time = float(_NEWS_CACHE.get("timestamp") or 0.0)
    
    if cached_data is not None and (now - cached_time) < CACHE_TTL:
        if isinstance(cached_data, NewsResponse):
            return cached_data

    owns_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=FEED_TIMEOUT)
        owns_client = True

    try:
        response = await client.get(GOOD_NEWS_FEED_URL)
        if response.status_code == 200:
            items = parse_rss_feed(response.text, max_items=4)
            result = NewsResponse(available=True, items=items)
            _NEWS_CACHE["timestamp"] = now
            _NEWS_CACHE["data"] = result
            return result
        logger.warning(f"GoodNews RSS returned status {response.status_code}")
    except Exception as exc:
        logger.warning(f"Error fetching GoodNews RSS feed: {exc}")
    finally:
        if owns_client:
            await client.aclose()

    return NewsResponse(available=False, items=[])


def clear_news_cache() -> None:
    """Hilfsfunktion für Tests zum Leeren des Caches."""
    _NEWS_CACHE["timestamp"] = 0.0
    _NEWS_CACHE["data"] = None
