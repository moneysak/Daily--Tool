from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime, date


# --- Gemeinsame Validierungs-Helfer ---
def _parse_weekdays(value):
    """Normalisiert Wochentage: akzeptiert Liste oder CSV-String (Mo=0..So=6).

    Dedupliziert, sortiert und validiert den Wertebereich 0..6. Ein
    ``None``-Wert bleibt ``None``. Ein ungültiger Wert (z.B. 7) führt zu
    einem Validierungsfehler (HTTP 422 bei Eingabe).
    """
    if value is None:
        return None
    if isinstance(value, str):
        value = [part for part in value.split(",") if part.strip() != ""]
    days = []
    for item in value:
        try:
            day = int(item)
        except (TypeError, ValueError):
            raise ValueError("weekdays müssen ganze Zahlen sein")
        if day < 0 or day > 6:
            raise ValueError("weekdays müssen zwischen 0 (Mo) und 6 (So) liegen")
        if day not in days:
            days.append(day)
    return sorted(days)


def _validate_frequency(value):
    """Erlaubt nur 'daily' oder 'weekly' (None bleibt None)."""
    if value is None:
        return value
    if value not in ("daily", "weekly"):
        raise ValueError("frequency muss 'daily' oder 'weekly' sein")
    return value


# --- Task Schemas ---
class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    completed: bool = False
    due_date: Optional[date] = None

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    due_date: Optional[date] = None

class Task(TaskBase):
    id: int
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    is_overdue: bool = False

    class Config:
        from_attributes = True

# --- Shopping Schemas ---
class ShoppingItemBase(BaseModel):
    name: str
    quantity: Optional[str] = "1"
    category: Optional[str] = "Allgemein"
    checked: bool = False

class ShoppingItemCreate(ShoppingItemBase):
    pass

class ShoppingItemUpdate(BaseModel):
    name: Optional[str] = None
    quantity: Optional[str] = None
    category: Optional[str] = None
    checked: Optional[bool] = None

class ShoppingItem(ShoppingItemBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# --- Routine Schemas ---
class RoutineBase(BaseModel):
    title: str
    description: Optional[str] = None
    # frequency bleibt beim Lesen bewusst tolerant (Alt-Daten "monthly" werden
    # nicht als Fehler behandelt); die strikte Validierung erfolgt in Create/Update.
    frequency: Optional[str] = "daily"
    active: bool = True
    completed_today: bool = False
    weekdays: Optional[List[int]] = None

    @field_validator("weekdays", mode="before")
    @classmethod
    def _validate_weekdays(cls, value):
        return _parse_weekdays(value)

class RoutineCreate(RoutineBase):
    @field_validator("frequency")
    @classmethod
    def _validate_create_frequency(cls, value):
        return _validate_frequency(value)

class RoutineUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    frequency: Optional[str] = None
    active: Optional[bool] = None
    completed_today: Optional[bool] = None
    weekdays: Optional[List[int]] = None

    @field_validator("weekdays", mode="before")
    @classmethod
    def _validate_weekdays(cls, value):
        return _parse_weekdays(value)

    @field_validator("frequency")
    @classmethod
    def _validate_update_frequency(cls, value):
        return _validate_frequency(value)

class Routine(RoutineBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
