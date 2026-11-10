"""Pydantic-Modelle für das Daily Briefing."""
from typing import List
from pydantic import BaseModel


class BriefingResponse(BaseModel):
    available: bool
    greeting: str
    summary: str
    time_of_day: str
    highlights: List[str]
