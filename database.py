import os
from sqlalchemy import create_engine, Column, String, Float, Integer, Boolean, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Local: usa SQLite. En Vercel: usa DATABASE_URL con PostgreSQL (Neon)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./finanzas.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Transaction(Base):
    __tablename__ = "transactions"

    id         = Column(String, primary_key=True, index=True)
    type       = Column(String, nullable=False)          # "income" | "expense"
    date       = Column(String, nullable=False)          # "YYYY-MM-DD"
    desc       = Column(String, nullable=False)
    category   = Column(String, nullable=False)
    currency   = Column(String, nullable=False)          # "ARS" | "USD"
    amount     = Column(Float, nullable=False)
    payment    = Column(String, default="none")          # "cash" | "debit" | "credit" | "none"
    cuotas     = Column(Integer, default=1)
    cuota_num  = Column(Integer, default=1)
    parent_id  = Column(String, nullable=True)
    total_amount = Column(Float, nullable=True)


class Budget(Base):
    __tablename__ = "budgets"

    id       = Column(String, primary_key=True, index=True)
    category = Column(String, nullable=False)
    amount   = Column(Float, nullable=False)
    currency = Column(String, nullable=False)


class Goal(Base):
    __tablename__ = "goals"

    id       = Column(String, primary_key=True, index=True)
    name     = Column(String, nullable=False)
    target   = Column(Float, nullable=False)
    currency = Column(String, nullable=False)
    current  = Column(Float, default=0.0)
    deadline = Column(String, nullable=True)


def create_tables():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()