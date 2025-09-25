"""Database models for the web API."""

import datetime as dt
from typing import List, Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


class User(SQLModel, table=True):
    """Registered API user."""

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    email: Optional[str] = Field(default=None, index=True)
    avatar_url: Optional[str] = Field(default=None)
    hashed_password: str
    created_at: dt.datetime = Field(
        default_factory=lambda: dt.datetime.now(dt.timezone.utc)
    )

    collections: List["CollectionEntry"] = Relationship(back_populates="owner")


class Card(SQLModel, table=True):
    """Trading card tracked in the collection."""

    __table_args__ = (
        UniqueConstraint("name", "number", "set_name", name="uq_card_identity"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    number: str = Field(index=True)
    set_name: str = Field(index=True)
    set_code: Optional[str] = Field(default=None, index=True)
    rarity: Optional[str] = None
    image_small: Optional[str] = Field(default=None)
    image_large: Optional[str] = Field(default=None)

    entries: List["CollectionEntry"] = Relationship(back_populates="card")
    price_history: List["PriceHistory"] = Relationship(back_populates="card")


class CardRecord(SQLModel, table=True):
    """Cached catalogue entry for faster search and detail pages."""

    __table_args__ = (
        UniqueConstraint("name", "number", "set_name", name="uq_cardrecord_identity"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    name_normalized: str = Field(index=True)
    number: str = Field(index=True)
    number_display: Optional[str] = Field(default=None)
    total: Optional[str] = Field(default=None, index=True)
    set_name: str = Field(index=True)
    set_name_normalized: Optional[str] = Field(default=None, index=True)
    set_code: Optional[str] = Field(default=None, index=True)
    set_code_clean: Optional[str] = Field(default=None, index=True)
    rarity: Optional[str] = Field(default=None)
    artist: Optional[str] = Field(default=None)
    series: Optional[str] = Field(default=None)
    release_date: Optional[str] = Field(default=None)
    image_small: Optional[str] = Field(default=None)
    image_large: Optional[str] = Field(default=None)
    set_icon: Optional[str] = Field(default=None)
    price_pln: Optional[float] = Field(default=None)
    price_updated_at: Optional[dt.datetime] = Field(default=None)
    created_at: dt.datetime = Field(
        default_factory=lambda: dt.datetime.now(dt.timezone.utc)
    )
    updated_at: dt.datetime = Field(
        default_factory=lambda: dt.datetime.now(dt.timezone.utc)
    )

class CollectionEntry(SQLModel, table=True):
    """Link between a user and the cards they own."""

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    card_id: int = Field(foreign_key="card.id", index=True)
    quantity: int = Field(default=1, ge=0)
    purchase_price: Optional[float] = Field(default=None, ge=0)
    current_price: Optional[float] = Field(default=None, ge=0)
    is_reverse: bool = Field(default=False)
    is_holo: bool = Field(default=False)
    last_price_update: Optional[dt.datetime] = Field(default=None)

    owner: Optional["User"] = Relationship(back_populates="collections")
    card: Optional["Card"] = Relationship(back_populates="entries")


class PriceHistory(SQLModel, table=True):
    """Stored snapshots of card prices for chart generation."""

    id: Optional[int] = Field(default=None, primary_key=True)
    card_id: int = Field(foreign_key="card.id", index=True)
    price: float = Field(ge=0)
    recorded_at: dt.datetime = Field(
        default_factory=lambda: dt.datetime.now(dt.timezone.utc)
    )

    card: Optional["Card"] = Relationship(back_populates="price_history")
