"""User related API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from .. import models, schemas
from ..auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    get_password_hash,
)
from ..database import get_session

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/register", response_model=schemas.UserRead, status_code=status.HTTP_201_CREATED)
def register_user(user_in: schemas.UserCreate, session: Session = Depends(get_session)):
    existing = session.exec(select(models.User).where(models.User.username == user_in.username)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")

    user = models.User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.post("/login", response_model=schemas.Token)
def login(user_in: schemas.UserLogin, session: Session = Depends(get_session)):
    user = authenticate_user(session, user_in.username, user_in.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    token = create_access_token({"sub": str(user.id)})
    return schemas.Token(access_token=token)


@router.get("/me", response_model=schemas.UserRead)
async def read_current_user(current_user: models.User = Depends(get_current_user)):
    return current_user
