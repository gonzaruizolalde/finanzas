from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from typing import List
import os

from database import create_tables, get_db, Transaction, Budget, Goal, Card, User
from schemas import (
    CardCreate, CardOut, CardUpdate,
    TransactionCreate, TransactionOut, TransactionUpdate,
    BudgetCreate, BudgetOut,
    GoalCreate, GoalOut, GoalDeposit,
    UserRegister, UserLogin, UserOut,
)
from auth import hash_password, verify_password, create_token, get_current_user

create_tables()

app = FastAPI(title="Finanzas Personales API", version="2.0.0")


# ── Frontend ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=FileResponse)
def serve_frontend():
    return FileResponse("static/index.html")


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.post("/api/auth/register", response_model=UserOut)
def register(data: UserRegister, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(400, "El email ya está registrado")
    user = User(email=data.email, password_hash=hash_password(data.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_token(user.id)
    response = JSONResponse({"id": user.id, "email": user.email})
    response.set_cookie(
        key="auth_token", value=token,
        httponly=True, samesite="lax", secure=True,
        max_age=60 * 60 * 24 * 7
    )
    return response


@app.post("/api/auth/login")
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Credenciales incorrectas")
    token = create_token(user.id)
    response = JSONResponse({"id": user.id, "email": user.email})
    response.set_cookie(
        key="auth_token", value=token,
        httponly=True, samesite="lax", secure=True,
        max_age=60 * 60 * 24 * 7
    )
    return response


@app.post("/api/auth/logout")
def logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie("auth_token")
    return response


@app.get("/api/auth/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


# ── Cards ─────────────────────────────────────────────────────────────────────

@app.get("/api/cards", response_model=List[CardOut])
def get_cards(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Card).filter(Card.user_id == current_user.id).all()


@app.post("/api/cards", response_model=CardOut)
def create_card(card: CardCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if db.query(Card).filter(Card.id == card.id, Card.user_id == current_user.id).first():
        raise HTTPException(400, "Tarjeta ya existe")
    db_card = Card(**card.model_dump(), user_id=current_user.id)
    db.add(db_card)
    db.commit()
    db.refresh(db_card)
    return db_card


@app.patch("/api/cards/{card_id}", response_model=CardOut)
def update_card(card_id: str, data: CardUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    card = db.query(Card).filter(Card.id == card_id, Card.user_id == current_user.id).first()
    if not card:
        raise HTTPException(404, "Tarjeta no encontrada")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(card, field, value)
    db.commit()
    db.refresh(card)
    return card


@app.delete("/api/cards/{card_id}")
def delete_card(card_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    card = db.query(Card).filter(Card.id == card_id, Card.user_id == current_user.id).first()
    if not card:
        raise HTTPException(404, "Tarjeta no encontrada")
    db.delete(card)
    db.commit()
    return {"ok": True}


# ── Transactions ──────────────────────────────────────────────────────────────

@app.get("/api/transactions", response_model=List[TransactionOut])
def get_transactions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Transaction).filter(Transaction.user_id == current_user.id).all()


@app.post("/api/transactions", response_model=TransactionOut)
def create_transaction(tx: TransactionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if db.query(Transaction).filter(Transaction.id == tx.id, Transaction.user_id == current_user.id).first():
        raise HTTPException(400, "Transacción ya existe")
    db_tx = Transaction(**tx.model_dump(), user_id=current_user.id)
    db.add(db_tx)
    db.commit()
    db.refresh(db_tx)
    return db_tx


@app.post("/api/transactions/batch", response_model=List[TransactionOut])
def create_transactions_batch(txs: List[TransactionCreate], db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    created = []
    for tx in txs:
        if not db.query(Transaction).filter(Transaction.id == tx.id).first():
            db_tx = Transaction(**tx.model_dump(), user_id=current_user.id)
            db.add(db_tx)
            created.append(db_tx)
    db.commit()
    for t in created:
        db.refresh(t)
    return created


@app.patch("/api/transactions/{tx_id}", response_model=TransactionOut)
def update_transaction(tx_id: str, data: TransactionUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    tx = db.query(Transaction).filter(Transaction.id == tx_id, Transaction.user_id == current_user.id).first()
    if not tx:
        raise HTTPException(404, "Transacción no encontrada")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(tx, field, value)
    db.commit()
    db.refresh(tx)
    return tx


@app.delete("/api/transactions/{tx_id}")
def delete_transaction(tx_id: str, cascade: bool = False, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    tx = db.query(Transaction).filter(Transaction.id == tx_id, Transaction.user_id == current_user.id).first()
    if not tx:
        raise HTTPException(404, "Transacción no encontrada")
    if cascade:
        db.query(Transaction).filter(
            Transaction.parent_id == tx_id,
            Transaction.user_id == current_user.id
        ).delete()
    db.delete(tx)
    db.commit()
    return {"ok": True}


# ── Budgets ───────────────────────────────────────────────────────────────────

@app.get("/api/budgets", response_model=List[BudgetOut])
def get_budgets(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Budget).filter(Budget.user_id == current_user.id).all()


@app.post("/api/budgets", response_model=BudgetOut)
def upsert_budget(budget: BudgetCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    existing = db.query(Budget).filter(
        Budget.category == budget.category,
        Budget.currency == budget.currency,
        Budget.user_id == current_user.id
    ).first()
    if existing:
        existing.amount = budget.amount
        db.commit()
        db.refresh(existing)
        return existing
    db_b = Budget(**budget.model_dump(), user_id=current_user.id)
    db.add(db_b)
    db.commit()
    db.refresh(db_b)
    return db_b


@app.delete("/api/budgets/{budget_id}")
def delete_budget(budget_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    b = db.query(Budget).filter(Budget.id == budget_id, Budget.user_id == current_user.id).first()
    if not b:
        raise HTTPException(404, "Presupuesto no encontrado")
    db.delete(b)
    db.commit()
    return {"ok": True}


# ── Goals ─────────────────────────────────────────────────────────────────────

@app.get("/api/goals", response_model=List[GoalOut])
def get_goals(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Goal).filter(Goal.user_id == current_user.id).all()


@app.post("/api/goals", response_model=GoalOut)
def create_goal(goal: GoalCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if db.query(Goal).filter(Goal.id == goal.id, Goal.user_id == current_user.id).first():
        raise HTTPException(400, "Meta ya existe")
    db_g = Goal(**goal.model_dump(), user_id=current_user.id)
    db.add(db_g)
    db.commit()
    db.refresh(db_g)
    return db_g


@app.patch("/api/goals/{goal_id}/deposit", response_model=GoalOut)
def deposit_to_goal(goal_id: str, deposit: GoalDeposit, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    g = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == current_user.id).first()
    if not g:
        raise HTTPException(404, "Meta no encontrada")
    g.current = min(g.current + deposit.amount, g.target)
    db.commit()
    db.refresh(g)
    return g


@app.delete("/api/goals/{goal_id}")
def delete_goal(goal_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    g = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == current_user.id).first()
    if not g:
        raise HTTPException(404, "Meta no encontrada")
    db.delete(g)
    db.commit()
    return {"ok": True}
