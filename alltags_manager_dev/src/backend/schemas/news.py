"""Pydantic-Modelle für 'Gute Nachrichten' (RSS-Feed)."""
from typing import List, Optional
from pydantic import BaseModel, Field


class NewsItem(BaseModel):
    title: str
    link: str
    summary: Optional[str] = None
    published: Optional[str] = None


class NewsResponse(BaseModel):
    available: bool
    items: List[NewsItem] = Field(default_factory=list)
