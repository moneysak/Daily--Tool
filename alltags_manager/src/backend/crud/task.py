from sqlalchemy.orm import Session
from models.task import Task, ShoppingItem, Routine
from schemas import task as schemas
from crud.overview import local_now, local_today


def _weekdays_to_csv(value):
    """Wochentags-Liste -> CSV-String (None bleibt None, String bleibt String)."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return ",".join(str(int(day)) for day in value)


def _apply_effective_completed_today(routine: Routine, today=None) -> Routine:
    """Setzt ``completed_today`` auf den effektiv berechneten Wert.

    Quelle der Wahrheit ist ``last_completed_on`` (lazy reset, kein Cron).
    """
    if today is None:
        today = local_today()
    routine.completed_today = routine.last_completed_on == today
    return routine


# --- Tasks CRUD ---
def get_tasks(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Task).offset(skip).limit(limit).all()

def create_task(db: Session, task: schemas.TaskCreate):
    db_task = Task(**task.model_dump())
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

def update_task(db: Session, task_id: int, task: schemas.TaskUpdate):
    db_task = db.query(Task).filter(Task.id == task_id).first()
    if db_task:
        update_data = task.model_dump(exclude_unset=True)
        if "completed" in update_data:
            new_completed = update_data["completed"]
            if new_completed and not db_task.completed:
                # False -> True: Zeitpunkt festhalten (für "heute erledigt").
                update_data["completed_at"] = local_now()
            elif not new_completed and db_task.completed:
                # True -> False: wieder öffnen, Zeitpunkt löschen.
                update_data["completed_at"] = None
        for key, value in update_data.items():
            setattr(db_task, key, value)
        db.commit()
        db.refresh(db_task)
    return db_task

def delete_task(db: Session, task_id: int) -> bool:
    db_task = db.query(Task).filter(Task.id == task_id).first()
    if db_task:
        db.delete(db_task)
        db.commit()
        return True
    return False

# --- Shopping Items CRUD ---
def get_shopping_items(db: Session, skip: int = 0, limit: int = 200):
    return db.query(ShoppingItem).offset(skip).limit(limit).all()

def create_shopping_item(db: Session, item: schemas.ShoppingItemCreate):
    db_item = ShoppingItem(**item.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

def update_shopping_item(db: Session, item_id: int, item: schemas.ShoppingItemUpdate):
    db_item = db.query(ShoppingItem).filter(ShoppingItem.id == item_id).first()
    if db_item:
        update_data = item.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_item, key, value)
        db.commit()
        db.refresh(db_item)
    return db_item

def delete_shopping_item(db: Session, item_id: int) -> bool:
    db_item = db.query(ShoppingItem).filter(ShoppingItem.id == item_id).first()
    if db_item:
        db.delete(db_item)
        db.commit()
        return True
    return False

def clear_checked_shopping_items(db: Session) -> int:
    deleted_count = db.query(ShoppingItem).filter(ShoppingItem.checked == True).delete()
    db.commit()
    return deleted_count

# --- Routines CRUD ---
def get_routines(db: Session, skip: int = 0, limit: int = 100):
    routines = db.query(Routine).offset(skip).limit(limit).all()
    today = local_today()
    for routine in routines:
        _apply_effective_completed_today(routine, today)
    return routines

def create_routine(db: Session, routine: schemas.RoutineCreate):
    data = routine.model_dump()
    weekdays = data.pop("weekdays", None)
    completed = data.pop("completed_today", False)
    data["weekdays"] = _weekdays_to_csv(weekdays)
    if completed:
        data["last_completed_on"] = local_today()
    db_routine = Routine(**data)
    db.add(db_routine)
    db.commit()
    db.refresh(db_routine)
    _apply_effective_completed_today(db_routine)
    return db_routine

def update_routine(db: Session, routine_id: int, routine: schemas.RoutineUpdate):
    db_routine = db.query(Routine).filter(Routine.id == routine_id).first()
    if db_routine:
        update_data = routine.model_dump(exclude_unset=True)
        if "weekdays" in update_data:
            update_data["weekdays"] = _weekdays_to_csv(update_data["weekdays"])
        if "completed_today" in update_data:
            # Schreiben steuert last_completed_on (Quelle der Wahrheit).
            if update_data.pop("completed_today"):
                update_data["last_completed_on"] = local_today()
            else:
                update_data["last_completed_on"] = None
        for key, value in update_data.items():
            setattr(db_routine, key, value)
        db.commit()
        db.refresh(db_routine)
        _apply_effective_completed_today(db_routine)
    return db_routine

def delete_routine(db: Session, routine_id: int) -> bool:
    db_routine = db.query(Routine).filter(Routine.id == routine_id).first()
    if db_routine:
        db.delete(db_routine)
        db.commit()
        return True
    return False
