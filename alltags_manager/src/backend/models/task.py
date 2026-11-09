from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date
from datetime import datetime
from db.database import Base

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True, nullable=False)
    description = Column(String, nullable=True)
    completed = Column(Boolean, default=False)
    due_date = Column(Date, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class ShoppingItem(Base):
    __tablename__ = "shopping_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    quantity = Column(String, default="1")
    category = Column(String, default="Allgemein")
    checked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Routine(Base):
    __tablename__ = "routines"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True, nullable=False)
    description = Column(String, nullable=True)
    frequency = Column(String, default="daily") # daily, weekly
    weekdays = Column(String, nullable=True) # CSV der Wochentage Mo=0..So=6, z.B. "0,2,4"
    active = Column(Boolean, default=True)
    completed_today = Column(Boolean, default=False)
    last_completed_on = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
