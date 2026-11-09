"""Pydantic-Modelle für die Home-Assistant-Integration (Kalender + To-dos)."""
import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

# Entity-ID-Muster: nur Kleinbuchstaben, Ziffern und Unterstriche.
TODO_ENTITY_PATTERN = r"^todo\.[a-z0-9_]+$"


class AgendaEvent(BaseModel):
    calendar: str
    calendar_name: Optional[str] = None
    title: str
    all_day: bool
    start: str
    end: str
    location: Optional[str] = None


class AgendaResponse(BaseModel):
    available: bool
    date: Optional[datetime.date] = None
    events: List[AgendaEvent] = Field(default_factory=list)


class TodoItem(BaseModel):
    uid: str
    summary: str
    status: str
    due: Optional[str] = None


class TodoList(BaseModel):
    entity_id: str
    name: str
    items: List[TodoItem] = Field(default_factory=list)


class TodosResponse(BaseModel):
    available: bool
    lists: List[TodoList] = Field(default_factory=list)


class TodoToggle(BaseModel):
    entity_id: str = Field(pattern=TODO_ENTITY_PATTERN)
    uid: str
    completed: bool
