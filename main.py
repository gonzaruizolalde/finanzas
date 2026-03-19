from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
import os

from database import create_tables, get_db, Transaction, Budget, Goal
from schemas import (
    TransactionCreate, TransactionOut,
    BudgetCreate, BudgetOut,
    GoalCreate, GoalOut, GoalDeposit,
)

# Crear tablas al iniciar
create_tables()

app = FastAPI(title="Finanzas Personales API", version="1.0.0")


# ── Servir el frontend ────────────────────────────────────────────────────────

@app.get("/", response_class=FileResponse)
def serve_frontend():
    return FileResponse("static/index.html")


# ── Transactions ──────────────────────────────────────────────────────────────

@app.get("/api/transactions", response_model=List[TransactionOut])
def get_transactions(db: Session = Depends(get_db)):
    return db.query(Transaction).all()


@app.post("/api/transactions", response_model=TransactionOut)
def create_transaction(tx: TransactionCreate, db: Session = Depends(get_db)):
    # Verificar que no exista ya
    existing = db.query(Transaction).filter(Transaction.id == tx.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Transacción ya existe")

    db_tx = Transaction(
        id=tx.id,
        type=tx.type,
        date=tx.date,
        desc=tx.desc,
        category=tx.category,
        currency=tx.currency,
        amount=tx.amount,
        payment=tx.payment,
        cuotas=tx.cuotas,
        cuota_num=tx.cuota_num,
        parent_id=tx.parent_id,
        total_amount=tx.total_amount,
    )
    db.add(db_tx)
    db.commit()
    db.refresh(db_tx)
    return db_tx


@app.post("/api/transactions/batch", response_model=List[TransactionOut])
def create_transactions_batch(txs: List[TransactionCreate], db: Session = Depends(get_db)):
    """Guarda múltiples transacciones de una sola vez (útil para cuotas)."""
    created = []
    for tx in txs:
        existing = db.query(Transaction).filter(Transaction.id == tx.id).first()
        if not existing:
            db_tx = Transaction(**tx.model_dump())
            db.add(db_tx)
            created.append(db_tx)
    db.commit()
    for t in created:
        db.refresh(t)
    return created


@app.delete("/api/transactions/{tx_id}")
def delete_transaction(tx_id: str, cascade: bool = False, db: Session = Depends(get_db)):
    """
    Elimina una transacción.
    Si cascade=true, también elimina todas las cuotas hijas (parent_id == tx_id).
    """
    tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transacción no encontrada")

    if cascade:
        db.query(Transaction).filter(Transaction.parent_id == tx_id).delete()

    db.delete(tx)
    db.commit()
    return {"ok": True}


# ── Budgets ───────────────────────────────────────────────────────────────────

@app.get("/api/budgets", response_model=List[BudgetOut])
def get_budgets(db: Session = Depends(get_db)):
    return db.query(Budget).all()


@app.post("/api/budgets", response_model=BudgetOut)
def upsert_budget(budget: BudgetCreate, db: Session = Depends(get_db)):
    """Crea o actualiza un presupuesto por categoría + moneda."""
    existing = db.query(Budget).filter(
        Budget.category == budget.category,
        Budget.currency == budget.currency
    ).first()

    if existing:
        existing.amount = budget.amount
        db.commit()
        db.refresh(existing)
        return existing

    db_budget = Budget(**budget.model_dump())
    db.add(db_budget)
    db.commit()
    db.refresh(db_budget)
    return db_budget


@app.delete("/api/budgets/{budget_id}")
def delete_budget(budget_id: str, db: Session = Depends(get_db)):
    b = db.query(Budget).filter(Budget.id == budget_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
    db.delete(b)
    db.commit()
    return {"ok": True}


# ── Goals ─────────────────────────────────────────────────────────────────────

@app.get("/api/goals", response_model=List[GoalOut])
def get_goals(db: Session = Depends(get_db)):
    return db.query(Goal).all()


@app.post("/api/goals", response_model=GoalOut)
def create_goal(goal: GoalCreate, db: Session = Depends(get_db)):
    existing = db.query(Goal).filter(Goal.id == goal.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Meta ya existe")
    db_goal = Goal(**goal.model_dump())
    db.add(db_goal)
    db.commit()
    db.refresh(db_goal)
    return db_goal


@app.patch("/api/goals/{goal_id}/deposit", response_model=GoalOut)
def deposit_to_goal(goal_id: str, deposit: GoalDeposit, db: Session = Depends(get_db)):
    g = db.query(Goal).filter(Goal.id == goal_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Meta no encontrada")
    g.current = min(g.current + deposit.amount, g.target)
    db.commit()
    db.refresh(g)
    return g


@app.delete("/api/goals/{goal_id}")
def delete_goal(goal_id: str, db: Session = Depends(get_db)):
    g = db.query(Goal).filter(Goal.id == goal_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Meta no encontrada")
    db.delete(g)
    db.commit()
    return {"ok": True}