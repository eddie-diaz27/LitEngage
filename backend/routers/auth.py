"""Authentication API endpoints."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.database.models import UserAccount
from backend.schemas.auth import LoginRequest, LoginResponse, RegisterRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a bcrypt hash."""
    import bcrypt
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def _hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    import bcrypt
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate a user and return their profile info."""
    user = (
        db.query(UserAccount)
        .filter(UserAccount.username == request.username)
        .first()
    )

    if not user or not _verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()

    logger.info(f"User logged in: {user.username} (role={user.role})")

    return LoginResponse(
        user_id=user.id,
        username=user.username,
        role=user.role,
        student_id=user.student_id,
        display_name=user.display_name,
    )


@router.post("/register", response_model=LoginResponse)
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user account."""
    existing = (
        db.query(UserAccount)
        .filter(UserAccount.username == request.username)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")

    user = UserAccount(
        username=request.username,
        hashed_password=_hash_password(request.password),
        role=request.role,
        student_id=request.student_id,
        display_name=request.display_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info(f"User registered: {user.username} (role={user.role})")

    return LoginResponse(
        user_id=user.id,
        username=user.username,
        role=user.role,
        student_id=user.student_id,
        display_name=user.display_name,
    )
