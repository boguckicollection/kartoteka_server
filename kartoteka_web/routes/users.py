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
    verify_password,
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
        avatar_url=user_in.avatar_url,
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


@router.patch("/me", response_model=schemas.UserRead)
def update_current_user(
    payload: schemas.UserUpdate,
    current_user: models.User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    updated = False

    if payload.email is not None:
        email_value = payload.email.strip() or None
        if current_user.email != email_value:
            current_user.email = email_value
            updated = True

    if payload.avatar_url is not None:
        avatar_value = payload.avatar_url.strip() or None
        if current_user.avatar_url != avatar_value:
            current_user.avatar_url = avatar_value
            updated = True

    if payload.new_password:
        if len(payload.new_password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Hasło musi zawierać co najmniej 8 znaków.",
            )
        if not payload.current_password or not verify_password(
            payload.current_password, current_user.hashed_password
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Niepoprawne bieżące hasło.",
            )
        current_user.hashed_password = get_password_hash(payload.new_password)
        updated = True

    if updated:
        session.add(current_user)
        session.commit()
        session.refresh(current_user)

    return current_user
