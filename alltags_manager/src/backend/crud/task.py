from sqlalchemy.orm import Session
from models.task import Task, ShoppingItem, Routine
from schemas import task as schemas

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
    return db.query(Routine).offset(skip).limit(limit).all()

def create_routine(db: Session, routine: schemas.RoutineCreate):
    db_routine = Routine(**routine.model_dump())
    db.add(db_routine)
    db.commit()
    db.refresh(db_routine)
    return db_routine

def update_routine(db: Session, routine_id: int, routine: schemas.RoutineUpdate):
    db_routine = db.query(Routine).filter(Routine.id == routine_id).first()
    if db_routine:
        update_data = routine.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_routine, key, value)
        db.commit()
        db.refresh(db_routine)
    return db_routine

def delete_routine(db: Session, routine_id: int) -> bool:
    db_routine = db.query(Routine).filter(Routine.id == routine_id).first()
    if db_routine:
        db.delete(db_routine)
        db.commit()
        return True
    return False
