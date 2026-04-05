from pydantic import BaseModel
from typing import Optional, List


# ── Auth ──────────────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    email:    str
    password: str

class UserLogin(BaseModel):
    email:    str
    password: str

class UserOut(BaseModel):
    id:    str
    email: str
    class Config:
        from_attributes = True


# ── Cards ─────────────────────────────────────────────────────────────────────

class CardCreate(BaseModel):
    id:           str
    name:         str
    network:      str
    color:        str = "#1A5C8A"
    currency:     str = "ARS"
    limit_amount: Optional[float] = None
    close_day:    int
    due_day:      int


class CardOut(CardCreate):
    class Config:
        from_attributes = True


class CardUpdate(BaseModel):
    name:         Optional[str] = None
    network:      Optional[str] = None
    color:        Optional[str] = None
    currency:     Optional[str] = None
    limit_amount: Optional[float] = None
    close_day:    Optional[int] = None
    due_day:      Optional[int] = None


# ── Transactions ──────────────────────────────────────────────────────────────

class TransactionCreate(BaseModel):
    id:           str
    type:         str
    date:         str
    billing_date: Optional[str] = None
    desc:         str
    category:     str
    currency:     str
    amount:       float
    payment:      str = "none"
    card_id:      Optional[str] = None
    cuotas:       int = 1
    cuota_num:    int = 1
    parent_id:    Optional[str] = None
    total_amount: Optional[float] = None


class TransactionOut(TransactionCreate):
    class Config:
        from_attributes = True


class TransactionUpdate(BaseModel):
    type:         Optional[str] = None
    date:         Optional[str] = None
    billing_date: Optional[str] = None
    desc:         Optional[str] = None
    category:     Optional[str] = None
    currency:     Optional[str] = None
    amount:       Optional[float] = None
    payment:      Optional[str] = None
    card_id:      Optional[str] = None


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


# ── Categories ────────────────────────────────────────────────────────────────

class CategoryCreate(BaseModel):
    name: str

class CategoryOut(BaseModel):
    id:      str
    name:    str
    user_id: str
    class Config:
        from_attributes = True


# ── Password Reset ────────────────────────────────────────────────────────────

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token:    str
    password: str
