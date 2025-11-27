"""Database models for the web API."""

import datetime as dt
from enum import Enum
from typing import List, Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


class CollectionType(str, Enum):
    """Type of user collection."""
    CUSTOM = "custom"      # Custom collection with any cards
    SET = "set"            # Complete Pokemon TCG set
    ARTIST = "artist"      # All cards by specific artist


class SetType(str, Enum):
    """Type of set collection (baseset vs masterset)."""
    BASESET = "baseset"    # Only base cards (up to set total)
    MASTERSET = "masterset"  # All cards including secret rares


class User(SQLModel, table=True):
    """Registered API user."""

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    email: Optional[str] = Field(default=None, index=True)
    avatar_url: Optional[str] = Field(default=None)
    is_admin: bool = Field(default=False)
    
    # Security fields
    failed_login_attempts: int = Field(default=0)
    last_failed_login: Optional[dt.datetime] = Field(default=None)
    locked_until: Optional[dt.datetime] = Field(default=None)
    
    hashed_password: str
    created_at: dt.datetime = Field(
        default_factory=lambda: dt.datetime.now(dt.timezone.utc)
    )

    collections: List["CollectionEntry"] = Relationship(back_populates="owner")
    user_collections: List["Collection"] = Relationship(back_populates="owner")


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
    price: Optional[float] = Field(default=None)
    price_7d_average: Optional[float] = Field(default=None)

    entries: List["CollectionEntry"] = Relationship(back_populates="card")


class Product(SQLModel, table=True):
    """Sealed product tracked in the collection."""

    __table_args__ = (
        UniqueConstraint("name", "set_name", name="uq_product_identity"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    set_name: str = Field(index=True)
    set_code: Optional[str] = Field(default=None, index=True)
    image_small: Optional[str] = Field(default=None)
    image_large: Optional[str] = Field(default=None)
    price: Optional[float] = Field(default=None)
    price_7d_average: Optional[float] = Field(default=None)
    release_date: Optional[str] = Field(default=None)

    entries: List["CollectionEntry"] = Relationship(back_populates="product")


class PriceHistory(SQLModel, table=True):
    """Historical price data for cards and products."""

    __table_args__ = (
        UniqueConstraint("card_record_id", "date", name="uq_price_history"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    card_record_id: Optional[int] = Field(default=None, foreign_key="cardrecord.id", index=True)
    product_record_id: Optional[int] = Field(default=None, foreign_key="productrecord.id", index=True)
    date: dt.date = Field(index=True)
    price: float
    currency: str = Field(default="PLN")
    created_at: dt.datetime = Field(
        default_factory=lambda: dt.datetime.now(dt.timezone.utc)
    )
    updated_at: dt.datetime = Field(
        default_factory=lambda: dt.datetime.now(dt.timezone.utc)
    )

    # Relationships
    card_record: Optional["CardRecord"] = Relationship(back_populates="price_history")


class CardRecord(SQLModel, table=True):
    """Master database of all Pokemon cards - cached catalogue entry."""

    __table_args__ = (
        UniqueConstraint("name", "number", "set_name", name="uq_cardrecord_identity"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    remote_id: Optional[str] = Field(default=None, index=True)  # ID from TCGGO API
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
    price: Optional[float] = Field(default=None)
    price_7d_average: Optional[float] = Field(default=None)
    
    # Sync tracking fields
    sync_status: str = Field(default="pending", index=True)  # "pending", "synced", "failed"
    sync_priority: int = Field(default=5, index=True)  # 1=highest (new sets), 5=lowest (old sets)
    last_synced: Optional[dt.datetime] = Field(default=None)
    last_price_synced: Optional[dt.datetime] = Field(default=None)
    created_at: dt.datetime = Field(
        default_factory=lambda: dt.datetime.now(dt.timezone.utc)
    )
    updated_at: dt.datetime = Field(
        default_factory=lambda: dt.datetime.now(dt.timezone.utc)
    )
    
    # Relationships
    price_history: List["PriceHistory"] = Relationship(back_populates="card_record")
    collection_cards: List["CollectionCard"] = Relationship(back_populates="card_record")



class ProductRecord(SQLModel, table=True):
    """Cached product entry for faster search and detail pages."""

    __table_args__ = (
        UniqueConstraint("name", "set_name", name="uq_productrecord_identity"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    remote_id: Optional[str] = Field(default=None, index=True)  # ID from TCGGO API
    name: str = Field(index=True)
    name_normalized: str = Field(index=True)
    set_name: str = Field(index=True)
    set_name_normalized: Optional[str] = Field(default=None, index=True)
    set_code: Optional[str] = Field(default=None, index=True)
    set_code_clean: Optional[str] = Field(default=None, index=True)
    release_date: Optional[str] = Field(default=None)
    image_small: Optional[str] = Field(default=None)
    image_large: Optional[str] = Field(default=None)
    price: Optional[float] = Field(default=None)
    price_7d_average: Optional[float] = Field(default=None)
    
    # Sync tracking fields
    sync_status: str = Field(default="pending", index=True)
    sync_priority: int = Field(default=5, index=True)
    last_synced: Optional[dt.datetime] = Field(default=None)
    sync_error: Optional[str] = Field(default=None)
    
    created_at: dt.datetime = Field(
        default_factory=lambda: dt.datetime.now(dt.timezone.utc)
    )
    updated_at: dt.datetime = Field(
        default_factory=lambda: dt.datetime.now(dt.timezone.utc)
    )


class SetInfo(SQLModel, table=True):
    """Metadata about Pokemon TCG sets for tracking sync progress."""

    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(unique=True, index=True)  # "sv01", "sv02", etc.
    name: str
    series: Optional[str] = Field(default=None)  # "Scarlet & Violet"
    release_date: Optional[dt.date] = Field(default=None)
    total_cards: Optional[int] = Field(default=None)  # Total cards in set
    synced_cards: int = Field(default=0)  # Number of cards synced
    sync_status: str = Field(default="pending", index=True)  # "pending", "partial", "complete", "failed"
    sync_priority: int = Field(default=5, index=True)  # 1=highest, 5=lowest
    last_synced: Optional[dt.datetime] = Field(default=None)
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
    card_id: Optional[int] = Field(default=None, foreign_key="card.id", index=True)
    product_id: Optional[int] = Field(default=None, foreign_key="product.id", index=True)
    quantity: int = Field(default=1, ge=0)
    purchase_price: Optional[float] = Field(default=None, ge=0)
    is_reverse: bool = Field(default=False)
    is_holo: bool = Field(default=False)

    owner: Optional["User"] = Relationship(back_populates="collections")
    card: Optional["Card"] = Relationship(back_populates="entries")
    product: Optional["Product"] = Relationship(back_populates="entries")


class Collection(SQLModel, table=True):
    """User-defined collection for tracking card ownership."""

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    name: str = Field(index=True)
    description: Optional[str] = Field(default=None)
    
    # Collection type: custom, set, or artist
    collection_type: str = Field(default="custom", index=True)
    
    # For SET type collections
    set_code: Optional[str] = Field(default=None, index=True)
    set_name: Optional[str] = Field(default=None)
    set_type: Optional[str] = Field(default=None)  # baseset or masterset
    
    # For ARTIST type collections
    artist_name: Optional[str] = Field(default=None, index=True)
    
    # Metadata
    cover_image: Optional[str] = Field(default=None)
    total_cards: int = Field(default=0)
    owned_cards: int = Field(default=0)
    
    created_at: dt.datetime = Field(
        default_factory=lambda: dt.datetime.now(dt.timezone.utc)
    )
    updated_at: dt.datetime = Field(
        default_factory=lambda: dt.datetime.now(dt.timezone.utc)
    )

    # Relationships
    owner: Optional["User"] = Relationship(back_populates="user_collections")
    cards: List["CollectionCard"] = Relationship(back_populates="collection")


class CollectionCard(SQLModel, table=True):
    """Link between a collection and individual cards."""

    __table_args__ = (
        UniqueConstraint("collection_id", "card_record_id", name="uq_collection_card"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    collection_id: int = Field(foreign_key="collection.id", index=True)
    card_record_id: int = Field(foreign_key="cardrecord.id", index=True)
    
    # Ownership tracking
    is_owned: bool = Field(default=False, index=True)
    quantity: int = Field(default=0, ge=0)
    is_reverse: bool = Field(default=False)
    is_holo: bool = Field(default=False)
    notes: Optional[str] = Field(default=None)
    
    added_at: dt.datetime = Field(
        default_factory=lambda: dt.datetime.now(dt.timezone.utc)
    )
    updated_at: dt.datetime = Field(
        default_factory=lambda: dt.datetime.now(dt.timezone.utc)
    )

    # Relationships
    collection: Optional["Collection"] = Relationship(back_populates="cards")
    card_record: Optional["CardRecord"] = Relationship(back_populates="collection_cards")
