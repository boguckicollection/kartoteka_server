"""Pydantic/SQLModel schemas for the web API."""

from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlmodel import SQLModel


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


class UserBase(SQLModel):
    username: str
    email: Optional[str] = None


class UserCreate(UserBase):
    password: str


class UserLogin(SQLModel):
    username: str
    password: str


class UserRead(UserBase):
    id: int
    created_at: dt.datetime


class CardBase(SQLModel):
    name: str
    number: str
    set_name: str
    set_code: Optional[str] = None
    rarity: Optional[str] = None


class CardRead(CardBase):
    id: int


class CardSearchResult(SQLModel):
    name: str
    number: str
    number_display: Optional[str] = None
    total: Optional[str] = None
    set_name: str
    set_code: Optional[str] = None
    rarity: Optional[str] = None
    image_small: Optional[str] = None
    image_large: Optional[str] = None


class CollectionEntryBase(SQLModel):
    quantity: int = 1
    purchase_price: Optional[float] = None
    is_reverse: bool = False
    is_holo: bool = False


class CollectionEntryCreate(CollectionEntryBase):
    card: CardBase


class CollectionEntryUpdate(SQLModel):
    quantity: Optional[int] = None
    purchase_price: Optional[float] = None
    is_reverse: Optional[bool] = None
    is_holo: Optional[bool] = None


class CollectionEntryRead(CollectionEntryBase):
    id: int
    current_price: Optional[float] = None
    last_price_update: Optional[dt.datetime] = None
    card: CardRead


class PortfolioSummary(SQLModel):
    total_cards: int
    total_quantity: int
    estimated_value: float
