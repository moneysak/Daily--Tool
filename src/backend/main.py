import os
import httpx
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from db.database import SessionLocal, engine, Base
from crud import task as crud_task
from schemas import task as schema_task
from fastapi.staticfiles import StaticFiles

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Alltags-Manager Dashboard API")

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
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

class ChatMessage(BaseModel):
    message: str

@app.post("/api/hermes/chat")
async def chat_with_hermes(payload: ChatMessage):
    # Read the Supervisor Token from the environment variable (with fallback to provided hardcoded one)
    supervisor_token = os.environ.get("SUPERVISOR_TOKEN", "357f8b0f71eec28baf90dfd0c6132351cdf906d427d3c0fd7ff108caa8170c52f4d128510b7b08d461788bb29dabbc6e48e057a9810ddb3e")
    
    headers = {
        "Authorization": f"Bearer {supervisor_token}",
        "Content-Type": "application/json"
    }
    
    # Hardcoded URL for Home Assistant supervisor API
    url = "http://supervisor/core/api/hermes/chat"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                url, 
                json={"message": payload.message}, 
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Kommunikationsfehler: {str(e)}")

app.mount("/", StaticFiles(directory="/app/src/frontend", html=True), name="frontend")
