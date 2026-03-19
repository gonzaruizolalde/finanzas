from pydantic import BaseModel
from typing import Optional


# ── Transactions ──────────────────────────────────────────────────────────────

class TransactionCreate(BaseModel):
    id:           str
    type:         str
    date:         str
    desc:         str
    category:     str
    currency:     str
    amount:       float
    payment:      str = "none"
    cuotas:       int = 1
    cuota_num:    int = 1
    parent_id:    Optional[str] = None
    total_amount: Optional[float] = None


class TransactionOut(TransactionCreate):
    class Config:
        from_attributes = True


# ── Budgets ───────────────────────────────────────────────────────────────────

class BudgetCreate(BaseModel):
    id:       str
    category: str
    amount:   float
    currency: str


class BudgetOut(BudgetCreate):
    class Config:
        from_attributes = True


# ── Goals ─────────────────────────────────────────────────────────────────────

class GoalCreate(BaseModel):
    id:       str
    name:     str
    target:   float
    currency: str
    current:  float = 0.0
    deadline: Optional[str] = None


class GoalOut(GoalCreate):
    class Config:
        from_attributes = True


class GoalDeposit(BaseModel):
    amount: float