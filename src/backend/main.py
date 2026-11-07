from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

from db.database import SessionLocal, engine, Base
from crud import task as crud_task
from schemas import task as schema_task

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Alltags-Manager Dashboard API")

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def read_root():
    return {"message": "Willkommen zur Alltags-Manager Dashboard API"}

@app.post("/tasks/", response_model=schema_task.Task)
def create_task(task: schema_task.TaskCreate, db: Session = Depends(get_db)):
    return crud_task.create_task(db=db, task=task)

@app.get("/tasks/", response_model=list[schema_task.Task])
def read_tasks(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    tasks = crud_task.get_tasks(db, skip=skip, limit=limit)
    return tasks
