"""Pydantic-Modelle für den Home-Status (Home Assistant Proxy)."""
from typing import List, Optional
from pydantic import BaseModel


class DoorStatus(BaseModel):
    locked: Optional[bool] = None
    open: Optional[bool] = None


class WindowStatus(BaseModel):
    open_count: int = 0
    open_windows: List[str] = []


class LightStatus(BaseModel):
    on_count: int = 0


class ClimateStatus(BaseModel):
    current_temperature: Optional[float] = None
    target_temperature: Optional[float] = None


class ApplianceStatus(BaseModel):
    washing_machine_running: Optional[bool] = None


class HomeStatusResponse(BaseModel):
    available: bool
    door: Optional[DoorStatus] = None
    windows: Optional[WindowStatus] = None
    lights: Optional[LightStatus] = None
    climate: Optional[ClimateStatus] = None
    appliances: Optional[ApplianceStatus] = None
