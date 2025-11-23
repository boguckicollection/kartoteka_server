"""User collections API routes for tracking sets, artists, and custom collections."""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_session
from ..utils import sets as set_utils

router = APIRouter(prefix="/collections", tags=["collections"])

logger = logging.getLogger(__name__)


def _calculate_progress(total: int, owned: int) -> float:
    """Calculate progress percentage."""
    if total <= 0:
        return 0.0
    return round((owned / total) * 100, 2)


def _collection_to_read_schema(collection: models.Collection) -> schemas.CollectionRead:
    """Convert Collection model to read schema."""
    return schemas.CollectionRead(
        id=collection.id,
        user_id=collection.user_id,
        name=collection.name,
        description=collection.description,
        collection_type=collection.collection_type,
        set_code=collection.set_code,
        set_name=collection.set_name,
        set_type=collection.set_type,
        artist_name=collection.artist_name,
        cover_image=collection.cover_image,
        total_cards=collection.total_cards,
        owned_cards=collection.owned_cards,
        progress_percent=_calculate_progress(collection.total_cards, collection.owned_cards),
        created_at=collection.created_at,
        updated_at=collection.updated_at,
    )


def _get_set_cards_query(
    set_code: str,
    set_type: str | None,
    session: Session,
) -> list[models.CardRecord]:
    """Get cards for a set based on set type (baseset/masterset)."""
    set_code_clean = set_utils.clean_code(set_code) or set_code.lower()
    
    stmt = select(models.CardRecord).where(
        or_(
            models.CardRecord.set_code == set_code,
            models.CardRecord.set_code_clean == set_code_clean,
        )
    )
    
    cards = list(session.exec(stmt).all())
    
    if set_type == models.SetType.BASESET.value:
        # Filter only base cards (number <= total)
        filtered_cards = []
        for card in cards:
            try:
                # Extract numeric part from card number
                number_str = card.number or "0"
                number_clean = ''.join(c for c in number_str if c.isdigit())
                card_number = int(number_clean) if number_clean else 0
                
                # Get set total
                total_str = card.total or "999"
                total_clean = ''.join(c for c in total_str if c.isdigit())
                set_total = int(total_clean) if total_clean else 999
                
                if card_number <= set_total:
                    filtered_cards.append(card)
            except (ValueError, TypeError):
                # Include card if we can't parse numbers
                filtered_cards.append(card)
        cards = filtered_cards
    
    # Sort by number
    def sort_key(card: models.CardRecord) -> tuple:
        number_str = card.number or "0"
        number_clean = ''.join(c for c in number_str if c.isdigit())
        try:
            num = int(number_clean) if number_clean else 0
        except ValueError:
            num = 0
        return (num, card.number or "", card.name or "")
    
    return sorted(cards, key=sort_key)


def _get_artist_cards_query(
    artist_name: str,
    session: Session,
) -> list[models.CardRecord]:
    """Get all cards by a specific artist."""
    artist_lower = artist_name.lower().strip()
    
    stmt = select(models.CardRecord).where(
        func.lower(models.CardRecord.artist) == artist_lower
    ).order_by(
        models.CardRecord.release_date,
        models.CardRecord.set_name,
        models.CardRecord.number,
    )
    
    return list(session.exec(stmt).all())


def _populate_collection_cards(
    collection: models.Collection,
    cards: list[models.CardRecord],
    session: Session,
) -> int:
    """Populate collection with cards and return count."""
    count = 0
    for card in cards:
        # Check if card already exists in collection
        existing = session.exec(
            select(models.CollectionCard).where(
                models.CollectionCard.collection_id == collection.id,
                models.CollectionCard.card_record_id == card.id,
            )
        ).first()
        
        if not existing:
            collection_card = models.CollectionCard(
                collection_id=collection.id,
                card_record_id=card.id,
                is_owned=False,
                quantity=0,
            )
            session.add(collection_card)
            count += 1
    
    return count


@router.get("/", response_model=list[schemas.CollectionRead])
def list_collections(
    current_user: models.User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """List all collections for the current user."""
    collections = session.exec(
        select(models.Collection)
        .where(models.Collection.user_id == current_user.id)
        .order_by(models.Collection.updated_at.desc())
    ).all()
    
    return [_collection_to_read_schema(c) for c in collections]


@router.post("/", response_model=schemas.CollectionRead, status_code=status.HTTP_201_CREATED)
def create_collection(
    payload: schemas.CollectionCreate,
    current_user: models.User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Create a new collection."""
    collection_type = payload.collection_type.lower()
    
    # Validate collection type
    if collection_type not in [t.value for t in models.CollectionType]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid collection type: {collection_type}"
        )
    
    # Create base collection
    collection = models.Collection(
        user_id=current_user.id,
        name=payload.name,
        description=payload.description,
        collection_type=collection_type,
    )
    
    cards_to_add: list[models.CardRecord] = []
    
    if collection_type == models.CollectionType.SET.value:
        if not payload.set_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="set_code is required for set collections"
            )
        
        collection.set_code = payload.set_code
        collection.set_type = payload.set_type or models.SetType.BASESET.value
        
        # Get set info
        set_code_clean = set_utils.clean_code(payload.set_code) or payload.set_code.lower()
        set_info = session.exec(
            select(models.SetInfo).where(
                or_(
                    models.SetInfo.code == payload.set_code,
                    models.SetInfo.code == set_code_clean,
                )
            )
        ).first()
        
        if set_info:
            collection.set_name = set_info.name
            collection.cover_image = None  # Could add set logo here
        
        # Get cards for this set
        cards_to_add = _get_set_cards_query(payload.set_code, collection.set_type, session)
        
    elif collection_type == models.CollectionType.ARTIST.value:
        if not payload.artist_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="artist_name is required for artist collections"
            )
        
        collection.artist_name = payload.artist_name
        
        # Get cards by this artist
        cards_to_add = _get_artist_cards_query(payload.artist_name, session)
        
        if not cards_to_add:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No cards found for artist: {payload.artist_name}"
            )
    
    # Set total cards and cover image
    collection.total_cards = len(cards_to_add)
    if cards_to_add and cards_to_add[0].image_small:
        collection.cover_image = cards_to_add[0].image_small
    
    session.add(collection)
    session.flush()  # Get the collection ID
    
    # Populate collection with cards
    if cards_to_add:
        _populate_collection_cards(collection, cards_to_add, session)
    
    session.commit()
    session.refresh(collection)
    
    return _collection_to_read_schema(collection)


@router.get("/{collection_id}", response_model=schemas.CollectionDetailRead)
def get_collection(
    collection_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    filter: str = Query("all", regex="^(all|owned|missing)$"),
    current_user: models.User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Get collection details with cards."""
    collection = session.exec(
        select(models.Collection)
        .where(
            models.Collection.id == collection_id,
            models.Collection.user_id == current_user.id,
        )
    ).first()
    
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found"
        )
    
    # Build query for collection cards
    stmt = (
        select(models.CollectionCard)
        .where(models.CollectionCard.collection_id == collection_id)
        .options(selectinload(models.CollectionCard.card_record))
    )
    
    # Apply filter
    if filter == "owned":
        stmt = stmt.where(models.CollectionCard.is_owned == True)
    elif filter == "missing":
        stmt = stmt.where(models.CollectionCard.is_owned == False)
    
    # Get all cards for sorting
    all_cards = list(session.exec(stmt).all())
    
    # Sort by card number
    def sort_key(cc: models.CollectionCard) -> tuple:
        if not cc.card_record:
            return (999999, "", "")
        number_str = cc.card_record.number or "0"
        number_clean = ''.join(c for c in number_str if c.isdigit())
        try:
            num = int(number_clean) if number_clean else 0
        except ValueError:
            num = 0
        return (num, cc.card_record.number or "", cc.card_record.name or "")
    
    all_cards.sort(key=sort_key)
    
    # Paginate
    total_cards = len(all_cards)
    start = (page - 1) * per_page
    end = start + per_page
    page_cards = all_cards[start:end]
    
    # Convert to schema
    cards_info = []
    for cc in page_cards:
        if cc.card_record:
            cards_info.append(schemas.CollectionCardInfo(
                id=cc.id,
                card_record_id=cc.card_record_id,
                name=cc.card_record.name,
                number=cc.card_record.number,
                number_display=cc.card_record.number_display,
                set_name=cc.card_record.set_name,
                set_code=cc.card_record.set_code,
                rarity=cc.card_record.rarity,
                artist=cc.card_record.artist,
                image_small=cc.card_record.image_small,
                image_large=cc.card_record.image_large,
                is_owned=cc.is_owned,
                quantity=cc.quantity,
                is_reverse=cc.is_reverse,
                is_holo=cc.is_holo,
            ))
    
    return schemas.CollectionDetailRead(
        id=collection.id,
        user_id=collection.user_id,
        name=collection.name,
        description=collection.description,
        collection_type=collection.collection_type,
        set_code=collection.set_code,
        set_name=collection.set_name,
        set_type=collection.set_type,
        artist_name=collection.artist_name,
        cover_image=collection.cover_image,
        total_cards=collection.total_cards,
        owned_cards=collection.owned_cards,
        progress_percent=_calculate_progress(collection.total_cards, collection.owned_cards),
        created_at=collection.created_at,
        updated_at=collection.updated_at,
        cards=cards_info,
    )


@router.patch("/{collection_id}", response_model=schemas.CollectionRead)
def update_collection(
    collection_id: int,
    payload: schemas.CollectionUpdate,
    current_user: models.User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Update collection name or description."""
    collection = session.exec(
        select(models.Collection)
        .where(
            models.Collection.id == collection_id,
            models.Collection.user_id == current_user.id,
        )
    ).first()
    
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found"
        )
    
    if payload.name is not None:
        collection.name = payload.name
    if payload.description is not None:
        collection.description = payload.description
    
    collection.updated_at = dt.datetime.now(dt.timezone.utc)
    
    session.add(collection)
    session.commit()
    session.refresh(collection)
    
    return _collection_to_read_schema(collection)


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_collection(
    collection_id: int,
    current_user: models.User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Delete a collection and all its cards."""
    collection = session.exec(
        select(models.Collection)
        .where(
            models.Collection.id == collection_id,
            models.Collection.user_id == current_user.id,
        )
    ).first()
    
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found"
        )
    
    # Delete all collection cards first
    session.exec(
        select(models.CollectionCard)
        .where(models.CollectionCard.collection_id == collection_id)
    )
    for cc in session.exec(
        select(models.CollectionCard)
        .where(models.CollectionCard.collection_id == collection_id)
    ).all():
        session.delete(cc)
    
    session.delete(collection)
    session.commit()
    
    return None


@router.patch("/{collection_id}/cards/{card_id}", response_model=schemas.CollectionCardInfo)
def update_collection_card(
    collection_id: int,
    card_id: int,
    payload: schemas.CollectionCardUpdate,
    current_user: models.User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Update card ownership status in a collection."""
    # Verify collection belongs to user
    collection = session.exec(
        select(models.Collection)
        .where(
            models.Collection.id == collection_id,
            models.Collection.user_id == current_user.id,
        )
    ).first()
    
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found"
        )
    
    # Get the collection card
    collection_card = session.exec(
        select(models.CollectionCard)
        .where(
            models.CollectionCard.id == card_id,
            models.CollectionCard.collection_id == collection_id,
        )
        .options(selectinload(models.CollectionCard.card_record))
    ).first()
    
    if not collection_card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found in collection"
        )
    
    # Track if ownership changed
    was_owned = collection_card.is_owned
    
    # Update fields
    if payload.is_owned is not None:
        collection_card.is_owned = payload.is_owned
        if payload.is_owned and collection_card.quantity == 0:
            collection_card.quantity = 1
        elif not payload.is_owned:
            collection_card.quantity = 0
    
    if payload.quantity is not None:
        collection_card.quantity = payload.quantity
        collection_card.is_owned = payload.quantity > 0
    
    if payload.is_reverse is not None:
        collection_card.is_reverse = payload.is_reverse
    if payload.is_holo is not None:
        collection_card.is_holo = payload.is_holo
    if payload.notes is not None:
        collection_card.notes = payload.notes
    
    collection_card.updated_at = dt.datetime.now(dt.timezone.utc)
    
    # Update collection owned count
    if was_owned != collection_card.is_owned:
        if collection_card.is_owned:
            collection.owned_cards += 1
        else:
            collection.owned_cards = max(0, collection.owned_cards - 1)
        collection.updated_at = dt.datetime.now(dt.timezone.utc)
        session.add(collection)
    
    session.add(collection_card)
    session.commit()
    session.refresh(collection_card)
    
    card_record = collection_card.card_record
    return schemas.CollectionCardInfo(
        id=collection_card.id,
        card_record_id=collection_card.card_record_id,
        name=card_record.name if card_record else "",
        number=card_record.number if card_record else "",
        number_display=card_record.number_display if card_record else None,
        set_name=card_record.set_name if card_record else "",
        set_code=card_record.set_code if card_record else None,
        rarity=card_record.rarity if card_record else None,
        artist=card_record.artist if card_record else None,
        image_small=card_record.image_small if card_record else None,
        image_large=card_record.image_large if card_record else None,
        is_owned=collection_card.is_owned,
        quantity=collection_card.quantity,
        is_reverse=collection_card.is_reverse,
        is_holo=collection_card.is_holo,
    )


@router.post("/{collection_id}/cards/{card_id}/toggle", response_model=schemas.CollectionCardInfo)
def toggle_card_ownership(
    collection_id: int,
    card_id: int,
    current_user: models.User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Toggle card ownership status (owned/not owned)."""
    # Verify collection belongs to user
    collection = session.exec(
        select(models.Collection)
        .where(
            models.Collection.id == collection_id,
            models.Collection.user_id == current_user.id,
        )
    ).first()
    
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found"
        )
    
    # Get the collection card
    collection_card = session.exec(
        select(models.CollectionCard)
        .where(
            models.CollectionCard.id == card_id,
            models.CollectionCard.collection_id == collection_id,
        )
        .options(selectinload(models.CollectionCard.card_record))
    ).first()
    
    if not collection_card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found in collection"
        )
    
    # Toggle ownership
    collection_card.is_owned = not collection_card.is_owned
    if collection_card.is_owned:
        collection_card.quantity = max(1, collection_card.quantity)
        collection.owned_cards += 1
    else:
        collection_card.quantity = 0
        collection.owned_cards = max(0, collection.owned_cards - 1)
    
    collection_card.updated_at = dt.datetime.now(dt.timezone.utc)
    collection.updated_at = dt.datetime.now(dt.timezone.utc)
    
    session.add(collection_card)
    session.add(collection)
    session.commit()
    session.refresh(collection_card)
    
    card_record = collection_card.card_record
    return schemas.CollectionCardInfo(
        id=collection_card.id,
        card_record_id=collection_card.card_record_id,
        name=card_record.name if card_record else "",
        number=card_record.number if card_record else "",
        number_display=card_record.number_display if card_record else None,
        set_name=card_record.set_name if card_record else "",
        set_code=card_record.set_code if card_record else None,
        rarity=card_record.rarity if card_record else None,
        artist=card_record.artist if card_record else None,
        image_small=card_record.image_small if card_record else None,
        image_large=card_record.image_large if card_record else None,
        is_owned=collection_card.is_owned,
        quantity=collection_card.quantity,
        is_reverse=collection_card.is_reverse,
        is_holo=collection_card.is_holo,
    )


@router.get("/{collection_id}/progress", response_model=schemas.CollectionProgress)
def get_collection_progress(
    collection_id: int,
    current_user: models.User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Get detailed progress statistics for a collection."""
    collection = session.exec(
        select(models.Collection)
        .where(
            models.Collection.id == collection_id,
            models.Collection.user_id == current_user.id,
        )
    ).first()
    
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found"
        )
    
    # Get all collection cards with their card records
    collection_cards = session.exec(
        select(models.CollectionCard)
        .where(models.CollectionCard.collection_id == collection_id)
        .options(selectinload(models.CollectionCard.card_record))
    ).all()
    
    owned_value = 0.0
    missing_value = 0.0
    cards_with_price = 0
    cards_without_price = 0
    
    # Track top cards
    owned_cards_with_price: list[tuple[models.CollectionCard, float]] = []
    missing_cards_with_price: list[tuple[models.CollectionCard, float]] = []
    
    for cc in collection_cards:
        if cc.card_record:
            if cc.card_record.price and cc.card_record.price > 0:
                cards_with_price += 1
                if cc.is_owned:
                    card_value = cc.card_record.price * max(1, cc.quantity)
                    owned_value += card_value
                    owned_cards_with_price.append((cc, cc.card_record.price))
                else:
                    missing_value += cc.card_record.price
                    missing_cards_with_price.append((cc, cc.card_record.price))
            else:
                cards_without_price += 1
    
    total_value = owned_value + missing_value
    avg_card_price = total_value / cards_with_price if cards_with_price > 0 else 0.0
    
    # Find top cards
    most_expensive_owned = None
    most_expensive_missing = None
    cheapest_missing = None
    
    if owned_cards_with_price:
        owned_cards_with_price.sort(key=lambda x: x[1], reverse=True)
        top_owned = owned_cards_with_price[0]
        if top_owned[0].card_record:
            most_expensive_owned = schemas.CollectionProgressCard(
                name=top_owned[0].card_record.name,
                number=top_owned[0].card_record.number,
                set_name=top_owned[0].card_record.set_name,
                image_small=top_owned[0].card_record.image_small,
                price=top_owned[1],
                is_owned=True,
            )
    
    if missing_cards_with_price:
        missing_cards_with_price.sort(key=lambda x: x[1], reverse=True)
        top_missing = missing_cards_with_price[0]
        if top_missing[0].card_record:
            most_expensive_missing = schemas.CollectionProgressCard(
                name=top_missing[0].card_record.name,
                number=top_missing[0].card_record.number,
                set_name=top_missing[0].card_record.set_name,
                image_small=top_missing[0].card_record.image_small,
                price=top_missing[1],
                is_owned=False,
            )
        
        # Cheapest missing
        cheapest = missing_cards_with_price[-1]
        if cheapest[0].card_record:
            cheapest_missing = schemas.CollectionProgressCard(
                name=cheapest[0].card_record.name,
                number=cheapest[0].card_record.number,
                set_name=cheapest[0].card_record.set_name,
                image_small=cheapest[0].card_record.image_small,
                price=cheapest[1],
                is_owned=False,
            )
    
    return schemas.CollectionProgress(
        total_cards=collection.total_cards,
        owned_cards=collection.owned_cards,
        missing_cards=collection.total_cards - collection.owned_cards,
        progress_percent=_calculate_progress(collection.total_cards, collection.owned_cards),
        owned_value=round(owned_value, 2),
        missing_value=round(missing_value, 2),
        total_value=round(total_value, 2),
        avg_card_price=round(avg_card_price, 2),
        cards_with_price=cards_with_price,
        cards_without_price=cards_without_price,
        most_expensive_owned=most_expensive_owned,
        most_expensive_missing=most_expensive_missing,
        cheapest_missing=cheapest_missing,
    )


# ============================================================================
# Print templates for albums
# ============================================================================

@router.get("/{collection_id}/print-data")
def get_print_data(
    collection_id: int,
    cards_filter: str = Query("all", regex="^(all|owned|missing)$"),
    current_user: models.User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Get collection data formatted for printing album templates."""
    collection = session.exec(
        select(models.Collection)
        .where(
            models.Collection.id == collection_id,
            models.Collection.user_id == current_user.id,
        )
    ).first()
    
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found"
        )
    
    # Get all collection cards with their card records
    stmt = (
        select(models.CollectionCard)
        .where(models.CollectionCard.collection_id == collection_id)
        .options(selectinload(models.CollectionCard.card_record))
    )
    
    collection_cards = list(session.exec(stmt).all())
    
    # Filter cards
    if cards_filter == "owned":
        collection_cards = [cc for cc in collection_cards if cc.is_owned]
    elif cards_filter == "missing":
        collection_cards = [cc for cc in collection_cards if not cc.is_owned]
    
    # Sort by number
    def sort_key(cc: models.CollectionCard) -> tuple:
        if not cc.card_record:
            return (999999, "", "")
        number_str = cc.card_record.number or "0"
        number_clean = ''.join(c for c in number_str if c.isdigit())
        try:
            num = int(number_clean) if number_clean else 0
        except ValueError:
            num = 0
        return (num, cc.card_record.number or "", cc.card_record.name or "")
    
    collection_cards.sort(key=sort_key)
    
    # Format cards for print
    cards_data = []
    for cc in collection_cards:
        if cc.card_record:
            cards_data.append({
                "name": cc.card_record.name,
                "number": cc.card_record.number,
                "number_display": cc.card_record.number_display or cc.card_record.number,
                "set_name": cc.card_record.set_name,
                "set_code": cc.card_record.set_code,
                "rarity": cc.card_record.rarity,
                "artist": cc.card_record.artist,
                "image_small": cc.card_record.image_small,
                "is_owned": cc.is_owned,
            })
    
    return {
        "collection": {
            "id": collection.id,
            "name": collection.name,
            "set_name": collection.set_name,
            "set_code": collection.set_code,
            "artist_name": collection.artist_name,
            "collection_type": collection.collection_type,
            "total_cards": len(cards_data),
        },
        "cards": cards_data,
    }


# ============================================================================
# Helper endpoints for sets and artists
# ============================================================================

@router.get("/sets/list", response_model=list[schemas.SetInfoRead])
def list_available_sets(
    session: Session = Depends(get_session),
):
    """List all available Pokemon TCG sets from local card database."""
    import json
    from pathlib import Path
    
    # Load sets from JSON file for additional metadata
    json_sets: dict[str, dict] = {}  # code -> {name, series, abbr}
    json_path = Path(__file__).parent.parent.parent / "tcg_sets.json"
    if json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for series_name, sets_list in data.items():
                for s in sets_list:
                    code = s.get("code", "")
                    if code:
                        json_sets[code.lower()] = {
                            "name": s.get("name", ""),
                            "series": series_name,
                            "abbr": s.get("abbr", ""),
                            "original_code": code,  # Keep original case
                        }
        except Exception as e:
            logger.warning(f"Failed to load tcg_sets.json: {e}")
    
    # Load API mapping for logo URLs
    api_mapping: dict[str, dict] = {}
    api_mapping_path = Path(__file__).parent.parent.parent / "set_code_to_api.json"
    if api_mapping_path.exists():
        try:
            with open(api_mapping_path, "r", encoding="utf-8") as f:
                api_mapping = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load set_code_to_api.json: {e}")
    
    # Get unique sets from CardRecord with card counts
    stmt = (
        select(
            models.CardRecord.set_code,
            models.CardRecord.set_name,
            models.CardRecord.series,
            func.count(models.CardRecord.id).label("card_count"),
            func.min(models.CardRecord.release_date).label("release_date"),
        )
        .where(models.CardRecord.set_code.is_not(None))
        .where(models.CardRecord.set_code != "")
        .group_by(models.CardRecord.set_code)
        .order_by(func.min(models.CardRecord.release_date).desc())
    )
    
    results = session.exec(stmt).all()
    
    sets_output = []
    seen_codes = set()
    
    # Helper to get logo URL - prioritize local logos, then pokemontcg.io
    def get_logo_url(code: str) -> str:
        # 1. Check for local logo (downloaded from TCGGO)
        local_logo_path = Path(__file__).parent.parent / "static" / "img" / "sets" / f"{code.lower()}_logo.png"
        if local_logo_path.exists():
            return f"/static/img/sets/{code.lower()}_logo.png"
        
        # 2. Try pokemontcg.io with code variations
        import re
        code_variations = [
            code.lower(),
            re.sub(r'0(\d)', r'\1', code.lower()),  # sv01 -> sv1
        ]
        for c in code_variations:
            # We'll use pokemontcg.io as fallback - most work
            pass
        
        # 3. Fallback to pokemontcg.io URL (may or may not work)
        return f"https://images.pokemontcg.io/{code.lower()}/logo.png"
    
    def get_symbol_url(code: str) -> str:
        # Symbol URLs use pokemontcg.io format
        return f"https://images.pokemontcg.io/{code.lower()}/symbol.png"
    
    for row in results:
        set_code = row[0]
        if not set_code or set_code.lower() in seen_codes:
            continue
        seen_codes.add(set_code.lower())
        
        set_name = row[1] or ""
        series = row[2] or ""
        card_count = row[3] or 0
        release_date = row[4]
        
        # Enrich with JSON data if available
        json_info = json_sets.get(set_code.lower(), {})
        original_code = set_code
        if json_info:
            if not series:
                series = json_info.get("series", "")
            # Prefer JSON name if it looks more complete
            json_name = json_info.get("name", "")
            if json_name and len(json_name) > len(set_name):
                set_name = json_name
            # Use original code case from JSON for API lookup
            original_code = json_info.get("original_code", set_code)
        
        sets_output.append(schemas.SetInfoRead(
            code=set_code,
            name=set_name,
            series=series,
            release_date=release_date,
            total_cards=card_count,
            logo_url=get_logo_url(original_code),
            symbol_url=get_symbol_url(set_code),
        ))
    
    # Also add sets from JSON that are not in CardRecord yet
    for code, info in json_sets.items():
        if code not in seen_codes:
            original_code = info.get("original_code", code)
            sets_output.append(schemas.SetInfoRead(
                code=info.get("original_code", code),  # Use original case
                name=info.get("name", code),
                series=info.get("series", ""),
                release_date=None,
                total_cards=0,
                logo_url=get_logo_url(original_code),
                symbol_url=get_symbol_url(code),
            ))
    
    # Sort by series (era) order, then by release date
    series_order = [
        "Mega Evolution",  # Newest era - 2025+
        "Scarlet & Violet",
        "Sword & Shield", 
        "Sun & Moon",
        "XY",
        "Black & White",
        "HeartGold & SoulSilver",
        "HeartGold SoulSilver",
        "Platinum",
        "Diamond & Pearl",
        "EX",
        "EX Series",
        "E-Card",
        "e-Card",
        "Neo",
        "Gym",
        "Base",
        "Base Set",
        "Other",
        "",
    ]
    
    def sort_key(s):
        try:
            series_idx = series_order.index(s.series) if s.series in series_order else len(series_order) - 2
        except ValueError:
            series_idx = len(series_order) - 2
        # Secondary sort by release date (newest first) or name
        date_key = s.release_date or "0000-00-00"
        return (series_idx, date_key, s.name)
    
    # Sort: first by series order, then by release date descending within series
    sets_output.sort(key=lambda s: (
        series_order.index(s.series) if s.series in series_order else len(series_order) - 2,
        s.release_date or "0000-00-00"
    ), reverse=False)
    
    # Reverse within each series to get newest first
    result = []
    current_series = None
    series_batch = []
    for s in sets_output:
        if s.series != current_series:
            if series_batch:
                series_batch.sort(key=lambda x: x.release_date or "0000-00-00", reverse=True)
                result.extend(series_batch)
            current_series = s.series
            series_batch = [s]
        else:
            series_batch.append(s)
    if series_batch:
        series_batch.sort(key=lambda x: x.release_date or "0000-00-00", reverse=True)
        result.extend(series_batch)
    
    return result


@router.get("/artists/list", response_model=list[schemas.ArtistInfo])
def list_available_artists(
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_session),
):
    """List all available artists with card counts."""
    # Get distinct artists with card counts
    stmt = (
        select(
            models.CardRecord.artist,
            func.count(models.CardRecord.id).label("card_count")
        )
        .where(models.CardRecord.artist.is_not(None))
        .where(models.CardRecord.artist != "")
        .group_by(models.CardRecord.artist)
        .order_by(func.count(models.CardRecord.id).desc())
        .limit(limit)
    )
    
    results = session.exec(stmt).all()
    
    return [
        schemas.ArtistInfo(name=row[0], card_count=row[1])
        for row in results
        if row[0]
    ]


@router.get("/artists/{artist_name}/cards")
def get_artist_cards(
    artist_name: str,
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    """Get cards by a specific artist for preview (no authentication required)."""
    cards = _get_artist_cards_query(artist_name, session)
    
    if not cards:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No cards found for artist: {artist_name}"
        )
    
    # Limit results
    cards = cards[:limit]
    
    return [
        {
            "id": card.id,
            "name": card.name,
            "number": card.number,
            "number_display": card.number_display or card.number,
            "set_name": card.set_name,
            "set_code": card.set_code,
            "rarity": card.rarity,
            "image_small": card.image_small,
        }
        for card in cards
    ]


# ============================================================================
# Set Print (without creating collection) - for downloading/printing sets
# ============================================================================

@router.get("/sets/{set_code}/print-data")
def get_set_print_data(
    set_code: str,
    set_type: str = Query("baseset", regex="^(baseset|masterset)$"),
    session: Session = Depends(get_session),
):
    """Get set data formatted for printing album templates (no authentication required)."""
    set_code_clean = set_utils.clean_code(set_code) or set_code.lower()
    
    # Get set info
    set_info = session.exec(
        select(models.SetInfo).where(
            or_(
                models.SetInfo.code == set_code,
                models.SetInfo.code == set_code_clean,
            )
        )
    ).first()
    
    if not set_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Set not found: {set_code}"
        )
    
    # Get cards for this set
    cards = _get_set_cards_query(set_code, set_type, session)
    
    if not cards:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No cards found for set: {set_code}"
        )
    
    # Format cards for print
    cards_data = []
    for card in cards:
        cards_data.append({
            "name": card.name,
            "number": card.number,
            "number_display": card.number_display or card.number,
            "set_name": card.set_name,
            "set_code": card.set_code,
            "rarity": card.rarity,
            "artist": card.artist,
            "image_small": card.image_small,
            "is_owned": False,  # Always false for standalone set print
        })
    
    return {
        "set": {
            "code": set_info.code,
            "name": set_info.name,
            "series": set_info.series,
            "total_cards": len(cards_data),
            "set_type": set_type,
        },
        "cards": cards_data,
    }


# ============================================================================
# Custom Collection Card Management
# ============================================================================

@router.post("/{collection_id}/cards/add", response_model=schemas.CollectionCardInfo)
def add_card_to_collection(
    collection_id: int,
    card_record_id: int = Query(..., description="ID of the card record to add"),
    current_user: models.User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Add a card to a custom collection."""
    # Verify collection belongs to user and is custom type
    collection = session.exec(
        select(models.Collection)
        .where(
            models.Collection.id == collection_id,
            models.Collection.user_id == current_user.id,
        )
    ).first()
    
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found"
        )
    
    if collection.collection_type != models.CollectionType.CUSTOM.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only add cards to custom collections"
        )
    
    # Verify card exists
    card_record = session.get(models.CardRecord, card_record_id)
    if not card_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found"
        )
    
    # Check if card already in collection
    existing = session.exec(
        select(models.CollectionCard)
        .where(
            models.CollectionCard.collection_id == collection_id,
            models.CollectionCard.card_record_id == card_record_id,
        )
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Card already in collection"
        )
    
    # Check if user owns this card in their main collection
    user_owns = session.exec(
        select(models.CollectionEntry)
        .where(
            models.CollectionEntry.user_id == current_user.id,
            models.CollectionEntry.card_record_id == card_record_id,
        )
    ).first()
    
    is_owned = user_owns is not None and (user_owns.quantity or 0) > 0
    
    # Add card to collection
    collection_card = models.CollectionCard(
        collection_id=collection.id,
        card_record_id=card_record_id,
        is_owned=is_owned,
        quantity=user_owns.quantity if user_owns else 0,
    )
    
    session.add(collection_card)
    
    # Update collection stats
    collection.total_cards += 1
    if is_owned:
        collection.owned_cards += 1
    
    # Set cover image if first card
    if collection.total_cards == 1 and card_record.image_small:
        collection.cover_image = card_record.image_small
    
    collection.updated_at = dt.datetime.now(dt.timezone.utc)
    session.add(collection)
    
    session.commit()
    session.refresh(collection_card)
    
    return schemas.CollectionCardInfo(
        id=collection_card.id,
        card_record_id=collection_card.card_record_id,
        name=card_record.name,
        number=card_record.number,
        number_display=card_record.number_display,
        set_name=card_record.set_name,
        set_code=card_record.set_code,
        rarity=card_record.rarity,
        artist=card_record.artist,
        image_small=card_record.image_small,
        image_large=card_record.image_large,
        is_owned=collection_card.is_owned,
        quantity=collection_card.quantity,
        is_reverse=collection_card.is_reverse,
        is_holo=collection_card.is_holo,
    )


@router.delete("/{collection_id}/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_card_from_collection(
    collection_id: int,
    card_id: int,
    current_user: models.User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Remove a card from a custom collection."""
    # Verify collection belongs to user and is custom type
    collection = session.exec(
        select(models.Collection)
        .where(
            models.Collection.id == collection_id,
            models.Collection.user_id == current_user.id,
        )
    ).first()
    
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found"
        )
    
    if collection.collection_type != models.CollectionType.CUSTOM.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only remove cards from custom collections"
        )
    
    # Get the collection card
    collection_card = session.exec(
        select(models.CollectionCard)
        .where(
            models.CollectionCard.id == card_id,
            models.CollectionCard.collection_id == collection_id,
        )
    ).first()
    
    if not collection_card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found in collection"
        )
    
    # Update collection stats
    collection.total_cards = max(0, collection.total_cards - 1)
    if collection_card.is_owned:
        collection.owned_cards = max(0, collection.owned_cards - 1)
    
    collection.updated_at = dt.datetime.now(dt.timezone.utc)
    session.add(collection)
    
    session.delete(collection_card)
    session.commit()
    
    return None


@router.get("/{collection_id}/search-cards")
def search_cards_for_collection(
    collection_id: int,
    q: str = Query("", description="Search query"),
    only_owned: bool = Query(False, description="Only show cards from user's main collection"),
    limit: int = Query(20, ge=1, le=50),
    current_user: models.User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Search cards to add to a custom collection."""
    # Verify collection belongs to user
    collection = session.exec(
        select(models.Collection)
        .where(
            models.Collection.id == collection_id,
            models.Collection.user_id == current_user.id,
        )
    ).first()
    
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found"
        )
    
    # Get cards already in this collection
    existing_card_ids = set(
        row[0] for row in session.exec(
            select(models.CollectionCard.card_record_id)
            .where(models.CollectionCard.collection_id == collection_id)
        ).all()
    )
    
    if only_owned:
        # Search only in user's main collection
        stmt = (
            select(models.CardRecord)
            .join(models.CollectionEntry, models.CollectionEntry.card_record_id == models.CardRecord.id)
            .where(models.CollectionEntry.user_id == current_user.id)
            .where(models.CollectionEntry.quantity > 0)
        )
    else:
        # Search all cards
        stmt = select(models.CardRecord)
    
    # Apply search filter
    if q:
        search_pattern = f"%{q}%"
        stmt = stmt.where(
            or_(
                models.CardRecord.name.ilike(search_pattern),
                models.CardRecord.set_name.ilike(search_pattern),
                models.CardRecord.number.ilike(search_pattern),
            )
        )
    
    stmt = stmt.order_by(models.CardRecord.name).limit(limit + len(existing_card_ids))
    
    cards = session.exec(stmt).all()
    
    # Filter out cards already in collection and limit results
    result = []
    for card in cards:
        if card.id not in existing_card_ids:
            # Check if user owns this card
            user_entry = session.exec(
                select(models.CollectionEntry)
                .where(
                    models.CollectionEntry.user_id == current_user.id,
                    models.CollectionEntry.card_record_id == card.id,
                )
            ).first()
            
            result.append({
                "id": card.id,
                "name": card.name,
                "number": card.number,
                "number_display": card.number_display,
                "set_name": card.set_name,
                "set_code": card.set_code,
                "rarity": card.rarity,
                "image_small": card.image_small,
                "is_in_main_collection": user_entry is not None and (user_entry.quantity or 0) > 0,
                "quantity_owned": user_entry.quantity if user_entry else 0,
            })
            
            if len(result) >= limit:
                break
    
    return result
