from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# --- Task Schemas ---
class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    completed: bool = False

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None

class Task(TaskBase):
    id: int
    created_at: Optional[datetime] = None

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
    frequency: Optional[str] = "daily"
    active: bool = True
    completed_today: bool = False

class RoutineCreate(RoutineBase):
    pass

class RoutineUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    frequency: Optional[str] = None
    active: Optional[bool] = None
    completed_today: Optional[bool] = None

class Routine(RoutineBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
