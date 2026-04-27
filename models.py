from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    tg_id = Column(Integer, unique=True, nullable=False)
    first_name = Column(String(100))
    age = Column(Integer)
    weight = Column(Float)
    height = Column(Float)
    level = Column(String(20))      # beginner, intermediate, advanced
    goal = Column(String(20))       # mass, functional
    program = Column(JSON)          # список упражнений с подходами/повторениями
    created_at = Column(DateTime, default=datetime.utcnow)

class Workout(Base):
    __tablename__ = "workouts"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    date = Column(DateTime, default=datetime.utcnow)
    exercises_data = Column(JSON)   # детали выполнения: упражнения -> списки подходов с результатами
    completed = Column(Integer, default=0)  # 0 - не завершена, 1 - завершена
    
    user = relationship("User", backref="workouts")