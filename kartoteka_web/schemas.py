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
    price: Optional[float] = None
    price_7d_average: Optional[float] = None


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
    set_icon_path: Optional[str] = None
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
    total_remote: Optional[int] = None


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
    rarity_symbol: Optional[str] = None
    rarity_symbol_remote: Optional[str] = None
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


class ProductBase(SQLModel):
    name: str
    set_name: str
    set_code: Optional[str] = None
    image_small: Optional[str] = None
    image_large: Optional[str] = None
    release_date: Optional[str] = None
    price: Optional[float] = None
    price_7d_average: Optional[float] = None


class ProductRead(ProductBase):
    id: int


class ProductCollectionEntryCreate(CollectionEntryBase):
    product: ProductBase


class CollectionEntryUpdate(SQLModel):
    quantity: Optional[int] = None
    purchase_price: Optional[float] = None
    is_reverse: Optional[bool] = None
    is_holo: Optional[bool] = None



class CollectionEntryRead(CollectionEntryBase):
    id: int
    card: Optional[CardRead] = None
    product: Optional[ProductRead] = None


class CollectionValueHistoryPoint(SQLModel):
    """Single point in collection value history."""
    date: str
    value: float  # Total value (cards + products)
    cards_value: Optional[float] = None  # Value of cards only
    products_value: Optional[float] = None  # Value of products only


class CollectionStats(SQLModel):
    """Collection statistics and value tracking."""
    total_cards: int = 0
    unique_cards: int = 0
    total_products: int = 0
    total_value: float = 0.0  # cards_value + products_value
    cards_value: float = 0.0  # Value of cards only
    products_value: float = 0.0  # Value of products (boosters, ETBs, etc.)
    purchase_value: float = 0.0  # Total purchase cost
    purchase_cards_value: float = 0.0  # Sum of card values that have purchase price set
    value_history: List[CollectionValueHistoryPoint] = Field(default_factory=list)


# ============================================================================
# User Collection Schemas (for set/artist tracking)
# ============================================================================

class CollectionBase(SQLModel):
    """Base schema for user collections."""
    name: str
    description: Optional[str] = None
    collection_type: str = "custom"  # custom, set, artist


class CollectionCreate(CollectionBase):
    """Schema for creating a new collection."""
    # For SET type
    set_code: Optional[str] = None
    set_type: Optional[str] = None  # baseset or masterset
    
    # For ARTIST type
    artist_name: Optional[str] = None


class CollectionUpdate(SQLModel):
    """Schema for updating a collection."""
    name: Optional[str] = None
    description: Optional[str] = None


class CollectionCardInfo(SQLModel):
    """Card information within a collection."""
    id: int
    card_record_id: int
    name: str
    number: str
    number_display: Optional[str] = None
    set_name: str
    set_code: Optional[str] = None
    rarity: Optional[str] = None
    artist: Optional[str] = None
    image_small: Optional[str] = None
    image_large: Optional[str] = None
    is_owned: bool = False
    quantity: int = 0
    is_reverse: bool = False
    is_holo: bool = False


class CollectionRead(CollectionBase):
    """Schema for reading a collection."""
    id: int
    user_id: int
    set_code: Optional[str] = None
    set_name: Optional[str] = None
    set_type: Optional[str] = None
    artist_name: Optional[str] = None
    cover_image: Optional[str] = None
    total_cards: int = 0
    owned_cards: int = 0
    progress_percent: float = 0.0
    created_at: dt.datetime
    updated_at: dt.datetime


class CollectionDetailRead(CollectionRead):
    """Schema for reading collection with cards."""
    cards: List[CollectionCardInfo] = Field(default_factory=list)


class CollectionCardUpdate(SQLModel):
    """Schema for updating card ownership in collection."""
    is_owned: Optional[bool] = None
    quantity: Optional[int] = None
    is_reverse: Optional[bool] = None
    is_holo: Optional[bool] = None
    notes: Optional[str] = None


class CollectionProgressCard(SQLModel):
    """Card info for progress statistics."""
    name: str
    number: str
    set_name: str
    image_small: Optional[str] = None
    price: Optional[float] = None
    is_owned: bool = False


class CollectionProgress(SQLModel):
    """Progress statistics for a collection."""
    total_cards: int = 0
    owned_cards: int = 0
    missing_cards: int = 0
    progress_percent: float = 0.0
    owned_value: float = 0.0
    missing_value: float = 0.0
    total_value: float = 0.0
    # Additional stats
    avg_card_price: float = 0.0
    cards_with_price: int = 0
    cards_without_price: int = 0
    # Top cards
    most_expensive_owned: Optional[CollectionProgressCard] = None
    most_expensive_missing: Optional[CollectionProgressCard] = None
    cheapest_missing: Optional[CollectionProgressCard] = None


class SetInfoRead(SQLModel):
    """Schema for reading set information."""
    code: str
    name: str
    series: Optional[str] = None
    release_date: Optional[str] = None
    total_cards: Optional[int] = None
    logo_url: Optional[str] = None
    symbol_url: Optional[str] = None


class ArtistInfo(SQLModel):
    """Schema for artist information."""
    name: str
    card_count: int = 0
