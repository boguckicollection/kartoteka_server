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
    avatar_url: Optional[str] = None


class UserCreate(UserBase):
    password: str


class UserLogin(SQLModel):
    username: str
    password: str


class UserRead(UserBase):
    id: int
    created_at: dt.datetime


class UserUpdate(SQLModel):
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None


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
    price: Optional[float] = None
    price_7d_average: Optional[float] = None


class CardSearchResponse(SQLModel):
    items: List[CardSearchResult] = Field(default_factory=list)
    total: int = 0
    total_count: int = 0
    page: int = 1
    per_page: int = 20
    suggested_query: Optional[str] = None


class CardPriceHistoryPoint(SQLModel):
    date: str
    price: Optional[float] = None
    currency: Optional[str] = None


class CardPriceHistory(SQLModel):
    last_7: List[CardPriceHistoryPoint] = Field(default_factory=list)
    last_30: List[CardPriceHistoryPoint] = Field(default_factory=list)
    all: List[CardPriceHistoryPoint] = Field(default_factory=list)


class CardDetail(SQLModel):
    name: str
    number: str
    number_display: Optional[str] = None
    total: Optional[str] = None
    set_name: str
    set_code: Optional[str] = None
    set_icon: Optional[str] = None
    set_icon_path: Optional[str] = None
    image_small: Optional[str] = None
    image_large: Optional[str] = None
    rarity: Optional[str] = None
    artist: Optional[str] = None
    series: Optional[str] = None
    release_date: Optional[str] = None
    price: Optional[float] = None
    price_7d_average: Optional[float] = None
    description: Optional[str] = None
    shop_url: Optional[str] = None
    price_history: CardPriceHistory = Field(default_factory=CardPriceHistory)


class CardDetailResponse(SQLModel):
    card: CardDetail
    related: List[CardSearchResult] = Field(default_factory=list)


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
    card: CardRead
