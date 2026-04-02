import os
import uuid
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Float, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./finanzas.db")

if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    engine = create_engine(DATABASE_URL, connect_args=connect_args)
else:
    # PostgreSQL / Neon: requiere SSL y pool adaptado a serverless
    engine = create_engine(
        DATABASE_URL,
        connect_args={"sslmode": "require"},
        pool_size=1,
        max_overflow=0,
        pool_pre_ping=True,
    )
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id            = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email         = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    created_at    = Column(String, default=lambda: datetime.utcnow().isoformat())


class Card(Base):
    __tablename__ = "cards"
    id           = Column(String, primary_key=True, index=True)
    name         = Column(String, nullable=False)
    network      = Column(String, nullable=False)
    color        = Column(String, default="#1A5C8A")
    currency     = Column(String, default="ARS")
    limit_amount = Column(Float, nullable=True)
    close_day    = Column(Integer, nullable=False)
    due_day      = Column(Integer, nullable=False)
    user_id      = Column(String, nullable=True)   # nullable para no romper datos existentes


class Transaction(Base):
    __tablename__ = "transactions"
    id           = Column(String, primary_key=True, index=True)
    type         = Column(String, nullable=False)
    date         = Column(String, nullable=False)
    billing_date = Column(String, nullable=True)
    desc         = Column(String, nullable=False)
    category     = Column(String, nullable=False)
    currency     = Column(String, nullable=False)
    amount       = Column(Float, nullable=False)
    payment      = Column(String, default="none")
    card_id      = Column(String, nullable=True)
    cuotas       = Column(Integer, default=1)
    cuota_num    = Column(Integer, default=1)
    parent_id    = Column(String, nullable=True)
    total_amount = Column(Float, nullable=True)
    user_id      = Column(String, nullable=True)   # nullable para no romper datos existentes


class Budget(Base):
    __tablename__ = "budgets"
    id       = Column(String, primary_key=True, index=True)
    category = Column(String, nullable=False)
    amount   = Column(Float, nullable=False)
    currency = Column(String, nullable=False)
    user_id  = Column(String, nullable=True)       # nullable para no romper datos existentes


class Goal(Base):
    __tablename__ = "goals"
    id       = Column(String, primary_key=True, index=True)
    name     = Column(String, nullable=False)
    target   = Column(Float, nullable=False)
    currency = Column(String, nullable=False)
    current  = Column(Float, default=0.0)
    deadline = Column(String, nullable=True)
    user_id  = Column(String, nullable=True)       # nullable para no romper datos existentes


def create_tables():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
