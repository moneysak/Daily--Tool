"""Pydantic-Modelle für Wetterdaten (Home Assistant Proxy)."""
from typing import Optional
from pydantic import BaseModel


class WeatherForecast(BaseModel):
    condition: Optional[str] = None
    templow: Optional[float] = None
    temperature: Optional[float] = None


class WeatherResponse(BaseModel):
    available: bool
    condition: Optional[str] = None
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    wind_speed: Optional[float] = None
    forecast_today: Optional[WeatherForecast] = None
