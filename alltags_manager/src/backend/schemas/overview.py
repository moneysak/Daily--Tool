from pydantic import BaseModel
from typing import Optional, List
from datetime import date

from schemas.task import Task, Routine


class TasksOverview(BaseModel):
    due_today: List[Task]
    overdue: List[Task]
    someday: List[Task]
    done_today: List[Task]


class ShoppingOverview(BaseModel):
    open_count: int


class ProgressOverview(BaseModel):
    done: int
    total: int
    percent: int


class Overview(BaseModel):
    today: date
    user_name: Optional[str] = None
    tasks: TasksOverview
    routines: List[Routine]
    shopping: ShoppingOverview
    progress: ProgressOverview
