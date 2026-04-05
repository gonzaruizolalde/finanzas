from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta
import os
import httpx
import secrets

from database import create_tables, get_db, Transaction, Budget, Goal, Card, User, Category, PasswordReset
from schemas import (
    CardCreate, CardOut, CardUpdate,
    TransactionCreate, TransactionOut, TransactionUpdate,
    BudgetCreate, BudgetOut,
    GoalCreate, GoalOut, GoalDeposit,
    UserRegister, UserLogin, UserOut,
    CategoryCreate, CategoryOut,
    ForgotPasswordRequest, ResetPasswordRequest,
)
from auth import hash_password, verify_password, create_token, get_current_user

create_tables()

app = FastAPI(title="Finanzas Personales API", version="2.0.0")


# ── Frontend ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=FileResponse)
def serve_frontend():
    return FileResponse("static/index.html")


# ── Password Reset ───────────────────────────────────────────────────────────

@app.post("/api/auth/forgot-password")
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    # Siempre responder OK para no revelar si el email existe
    if not user:
        return {"ok": True}

    # Invalidar tokens anteriores
    db.query(PasswordReset).filter(
        PasswordReset.user_id == user.id,
        PasswordReset.used == "false"
    ).update({"used": "true"})

    # Crear token nuevo
    token = secrets.token_urlsafe(32)
    expires = (datetime.utcnow() + timedelta(hours=1)).isoformat()
    reset = PasswordReset(user_id=user.id, token=token, expires_at=expires)
    db.add(reset)
    db.commit()

    # Obtener URL base del request
    reset_url = f"https://project-qe219.vercel.app/reset-password?token={token}"

    # Enviar email via Resend
    resend_key = os.getenv("RESEND_API_KEY")
    if resend_key:
        try:
            httpx.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
                json={
                    "from": "Mis Finanzas <onboarding@resend.dev>",
                    "to": [user.email],
                    "subject": "Restablecer contraseña — Mis Finanzas",
                    "html": f"""
                    <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px;">
                        <h2 style="font-size:22px;margin-bottom:8px;">Restablecer contraseña</h2>
                        <p style="color:#666;margin-bottom:24px;">
                            Recibimos una solicitud para restablecer la contraseña de tu cuenta.
                            El enlace expira en 1 hora.
                        </p>
                        <a href="{reset_url}"
                           style="display:inline-block;background:#1a1a1a;color:#fff;
                                  padding:12px 24px;border-radius:8px;text-decoration:none;
                                  font-weight:500;">
                            Restablecer contraseña
                        </a>
                        <p style="color:#999;font-size:12px;margin-top:24px;">
                            Si no solicitaste este cambio, podés ignorar este email.
                        </p>
                    </div>
                    """
                },
                timeout=10
            )
        except Exception as e:
            print(f"Error enviando email: {e}")

    return {"ok": True}


@app.post("/api/auth/reset-password")
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    reset = db.query(PasswordReset).filter(
        PasswordReset.token == data.token,
        PasswordReset.used == "false"
    ).first()

    if not reset:
        raise HTTPException(400, "Token inválido o ya utilizado")

    # Verificar expiración
    if datetime.fromisoformat(reset.expires_at) < datetime.utcnow():
        raise HTTPException(400, "El token expiró. Solicitá un nuevo enlace.")

    if len(data.password) < 8:
        raise HTTPException(400, "La contraseña debe tener al menos 8 caracteres")

    # Actualizar contraseña
    user = db.query(User).filter(User.id == reset.user_id).first()
    if not user:
        raise HTTPException(404, "Usuario no encontrado")

    user.password_hash = hash_password(data.password)
    reset.used = "true"
    db.commit()

    return {"ok": True}


# ── Categories ───────────────────────────────────────────────────────────────

@app.get("/api/categories", response_model=List[CategoryOut])
def get_categories(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Category).filter(Category.user_id == current_user.id).all()


@app.post("/api/categories", response_model=CategoryOut)
def create_category(data: CategoryCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    name = data.name.strip()
    if not name:
        raise HTTPException(400, "El nombre no puede estar vacío")
    # Evitar duplicados para este usuario (case-insensitive)
    existing = db.query(Category).filter(
        Category.user_id == current_user.id,
        Category.name.ilike(name)
    ).first()
    if existing:
        return existing
    cat = Category(user_id=current_user.id, name=name)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@app.delete("/api/categories/{category_id}")
def delete_category(category_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    cat = db.query(Category).filter(
        Category.id == category_id,
        Category.user_id == current_user.id
    ).first()
    if not cat:
        raise HTTPException(404, "Categoría no encontrada")
    db.delete(cat)
    db.commit()
    return {"ok": True}


# ── Dólar ────────────────────────────────────────────────────────────────────

_dolar_cache = {"data": None, "expires": datetime.utcnow()}

@app.get("/api/dolar")
def get_dolar():
    global _dolar_cache
    now = datetime.utcnow()
    if _dolar_cache["data"] and now < _dolar_cache["expires"]:
        return _dolar_cache["data"]
    try:
        response = httpx.get("https://dolarapi.com/v1/dolares", timeout=5)
        data = response.json()
        _dolar_cache = {"data": data, "expires": now + timedelta(minutes=15)}
        return data
    except Exception:
        if _dolar_cache["data"]:
            return _dolar_cache["data"]
        raise HTTPException(503, "No se pudo obtener el tipo de cambio")


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
