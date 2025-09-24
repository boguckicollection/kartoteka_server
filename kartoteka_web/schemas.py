"""Pydantic/SQLModel schemas for the web API."""

from __future__ import annotations

import datetime as dt
from typing import List, Optional

from sqlmodel import Field, SQLModel


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
    image_small: Optional[str] = None
    image_large: Optional[str] = None


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
    set_icon: Optional[str] = None
    artist: Optional[str] = None
    series: Optional[str] = None
    release_date: Optional[str] = None


class PricePoint(SQLModel):
    price: float
    recorded_at: dt.datetime


class CardDetail(SQLModel):
    name: str
    number: str
    number_display: Optional[str] = None
    total: Optional[str] = None
    set_name: str
    set_code: Optional[str] = None
    set_icon: Optional[str] = None
    image_small: Optional[str] = None
    image_large: Optional[str] = None
    rarity: Optional[str] = None
    artist: Optional[str] = None
    series: Optional[str] = None
    release_date: Optional[str] = None
    price_pln: Optional[float] = None
    last_price_update: Optional[dt.datetime] = None


class CardDetailResponse(SQLModel):
    card: CardDetail
    history: List[PricePoint] = []
    related: List[CardSearchResult] = []


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
    change_24h: Optional[float] = None
    change_direction: str = "flat"


class PortfolioSummary(SQLModel):
    total_cards: int
    total_quantity: int
    estimated_value: float


class PortfolioHistoryPoint(SQLModel):
    timestamp: dt.datetime
    value: float


class PortfolioHistoryResponse(SQLModel):
    points: List[PortfolioHistoryPoint] = Field(default_factory=list)
    change_24h: float = 0.0
    direction: str = "flat"
    latest_value: float = 0.0
