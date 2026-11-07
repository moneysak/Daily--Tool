import os
import httpx
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

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

@app.put("/tasks/{task_id}", response_model=schema_task.Task)
def update_task(task_id: int, task: schema_task.TaskUpdate, db: Session = Depends(get_db)):
    return crud_task.update_task(db=db, task_id=task_id, task=task)

HERMES_API_URL = os.getenv("HERMES_API_URL")
HERMES_API_TOKEN = os.getenv("HERMES_API_TOKEN")

class ChatMessage(BaseModel):
    message: str

@app.post("/api/hermes/chat")
async def chat_with_hermes(payload: ChatMessage):
    if not HERMES_API_URL or not HERMES_API_TOKEN:
        raise HTTPException(status_code=500, detail="Hermes API nicht konfiguriert.")

    headers = {
        "Authorization": f"Bearer {HERMES_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                HERMES_API_URL, 
                json={"message": payload.message}, 
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Kommunikationsfehler: {str(e)}")
