"""User related API routes."""

from __future__ import annotations

import re
import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
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
from ..rate_limit import (
    check_login_rate_limit,
    check_register_rate_limit,
    reset_login_rate_limit,
)

router = APIRouter(prefix="/users", tags=["users"])

# Email validation regex (RFC 5322 simplified)
EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)

# Password complexity regex
# At least 8 chars, 1 uppercase, 1 lowercase, 1 digit, 1 special char
PASSWORD_REGEX = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$"
)

# Lockout settings
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15

# Reserved usernames that cannot be registered via public API
RESERVED_USERNAMES = {
    "admin", "administrator", "root", "system", "support", 
    "moderator", "bogus", "kartoteka", "superuser"
}


def validate_password_strength(password: str):
    """Validate password complexity."""
    if not PASSWORD_REGEX.match(password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hasło musi mieć min. 8 znaków, zawierać wielką literę, cyfrę i znak specjalny (@$!%*?&).",
        )


@router.post("/register", response_model=schemas.UserRead, status_code=status.HTTP_201_CREATED)
def register_user(
    user_in: schemas.UserCreate,
    request: Request,
    session: Session = Depends(get_session),
    _rate_limit: None = Depends(check_register_rate_limit),
):
    clean_username = user_in.username.strip()
    if not clean_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username cannot be empty",
        )
    
    if clean_username.lower() in RESERVED_USERNAMES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ta nazwa użytkownika jest zastrzeżona i nie może zostać użyta.",
        )
    
    # Password validation
    validate_password_strength(user_in.password)

    clean_email = None
    if user_in.email is not None:
        stripped_email = user_in.email.strip()
        if stripped_email:
            # Validate email format
            if not EMAIL_REGEX.match(stripped_email):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Nieprawidłowy format adresu email.",
                )
            clean_email = stripped_email

    clean_avatar_url = None
    if user_in.avatar_url is not None:
        stripped_avatar = user_in.avatar_url.strip()
        clean_avatar_url = stripped_avatar or None

    # Case-insensitive check for existing username
    existing = session.exec(
        select(models.User).where(models.User.username == clean_username)
    ).first()
    
    # Double check with case-insensitive loop if needed (SQLite usually handles this, but to be safe)
    if not existing:
        all_users = session.exec(select(models.User.username)).all()
        if clean_username.lower() in [u.lower() for u in all_users]:
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")

    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")

    user = models.User(
        username=clean_username,
        email=clean_email,
        avatar_url=clean_avatar_url,
        hashed_password=get_password_hash(user_in.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.post("/login", response_model=schemas.Token)
def login(
    user_in: schemas.UserLogin,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    _rate_limit: None = Depends(check_login_rate_limit),
):
    clean_username = user_in.username.strip()
    user = session.exec(select(models.User).where(models.User.username == clean_username)).first()
    
    if not user:
        # Generic error message to prevent username enumeration
        # But we still consume rate limit
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")

    # Check for lockout
    if user.locked_until and user.locked_until > dt.datetime.now(dt.timezone.utc):
        lockout_remaining = int((user.locked_until - dt.datetime.now(dt.timezone.utc)).total_seconds() / 60)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail=f"Konto zablokowane z powodu zbyt wielu nieudanych prób. Spróbuj za {lockout_remaining + 1} min."
        )

    if not verify_password(user_in.password, user.hashed_password):
        # Increment failed attempts
        user.failed_login_attempts += 1
        user.last_failed_login = dt.datetime.now(dt.timezone.utc)
        
        if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
            user.locked_until = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=LOCKOUT_DURATION_MINUTES)
            session.add(user)
            session.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail=f"Zbyt wiele nieudanych prób. Konto zablokowane na {LOCKOUT_DURATION_MINUTES} minut."
            )
        
        session.add(user)
        session.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    
    # Successful login - reset counters
    user.failed_login_attempts = 0
    user.last_failed_login = None
    user.locked_until = None
    session.add(user)
    session.commit()
    
    # Reset rate limit on successful login
    reset_login_rate_limit(request)
    
    token = create_access_token({"sub": str(user.id)})
    
    # Set HttpOnly Cookie for server-side rendering persistence
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=60 * 60 * 24, # 24 hours
        samesite="lax",
        secure=False, # Set to True in production (HTTPS)
    )
    
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
        # Use robust password validation
        validate_password_strength(payload.new_password)
        
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


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_current_user(
    current_user: models.User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Delete current user and all associated data."""
    # 1. Delete collection entries (cards owned)
    stmt_entries = select(models.CollectionEntry).where(models.CollectionEntry.user_id == current_user.id)
    entries = session.exec(stmt_entries).all()
    for entry in entries:
        session.delete(entry)
        
    # 2. Delete user collections and their cards
    stmt_collections = select(models.Collection).where(models.Collection.user_id == current_user.id)
    collections = session.exec(stmt_collections).all()
    for collection in collections:
        # Delete collection cards first
        stmt_coll_cards = select(models.CollectionCard).where(models.CollectionCard.collection_id == collection.id)
        coll_cards = session.exec(stmt_coll_cards).all()
        for cc in coll_cards:
            session.delete(cc)
        session.delete(collection)
    
    # 3. Delete user
    session.delete(current_user)
    session.commit()
    return None
