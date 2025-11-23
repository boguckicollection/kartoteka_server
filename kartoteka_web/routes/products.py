"""API routes for products."""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session

from ..database import get_session
from ..services import tcg_api
from .. import models, schemas
from ..auth import get_current_user
from ..utils import text
from sqlmodel import Session, select

router = APIRouter(prefix="/products", tags=["products"])


def _apply_product_price(product: models.Product, session: Session) -> bool:
    """Fetch and update price from ProductRecord catalog if available."""
    
    # Try to find price in ProductRecord catalog
    name_norm = text.normalize(product.name, keep_spaces=True)
    set_name_norm = text.normalize(product.set_name, keep_spaces=True)
    
    # Try to find matching ProductRecord
    stmt = select(models.ProductRecord).where(
        models.ProductRecord.name_normalized == name_norm,
        models.ProductRecord.set_name_normalized == set_name_norm
    ).limit(1)
    
    product_record = session.exec(stmt).first()
    
    updated = False
    if product_record:
        # Update price if available
        if product_record.price is not None and product.price != product_record.price:
            product.price = product_record.price
            updated = True
        # Update 7-day average if available
        if product_record.price_7d_average is not None and product.price_7d_average != product_record.price_7d_average:
            product.price_7d_average = product_record.price_7d_average
            updated = True
    
    return updated

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY") or os.getenv("KARTOTEKA_RAPIDAPI_KEY")
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST") or os.getenv("KARTOTEKA_RAPIDAPI_HOST")


@router.get("/search")
async def search_products(
    request: Request,
    q: str | None = None,  # Alias parameter
    query: str | None = None,  # Main parameter
    page: int = 1,
    per_page: int = 20,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Search for products by name."""
    # Accept both 'q' and 'query' parameters
    search_query = query or q
    if not search_query or len(search_query) < 2:
        raise HTTPException(status_code=400, detail="Query must be at least 2 characters")
    
    results, filtered_total, total_count = tcg_api.search_products(
        name=search_query,
        limit=per_page,
        rapidapi_key=RAPIDAPI_KEY,
        rapidapi_host=RAPIDAPI_HOST,
    )
    
    # Return consistent structure with cards endpoint
    return {
        "items": results,  # Changed from 'results' to 'items'
        "total": filtered_total or len(results),
        "total_count": total_count or len(results),
        "page": page,
        "per_page": per_page,
    }


@router.post("/", response_model=schemas.CollectionEntryRead, status_code=201)
def add_product(
    payload: schemas.ProductCollectionEntryCreate,
    current_user: models.User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    product_data = payload.product
    name_value = product_data.name.strip()
    set_name_value = product_data.set_name.strip()
    set_code_value = (product_data.set_code or "").strip() or None

    if not name_value or not set_name_value:
        raise HTTPException(status_code=400, detail="Missing product details")

    product = session.exec(
        select(models.Product)
        .where(models.Product.name == name_value)
        .where(models.Product.set_name == set_name_value)
    ).first()

    if product is None:
        product = models.Product(
            name=name_value,
            set_name=set_name_value,
            set_code=set_code_value,
            image_small=product_data.image_small,
            image_large=product_data.image_large,
            release_date=product_data.release_date,
            price=product_data.price,
            price_7d_average=product_data.price_7d_average,
        )
        session.add(product)
        session.flush()
        # Try to get price from ProductRecord if not provided
        if product.price is None or product.price_7d_average is None:
            _apply_product_price(product, session)
        session.commit()
        session.refresh(product)
    else:
        # Update existing product with new data if available
        updated = False
        if product_data.price is not None and product.price != product_data.price:
            product.price = product_data.price
            updated = True
        if product_data.price_7d_average is not None and product.price_7d_average != product_data.price_7d_average:
            product.price_7d_average = product_data.price_7d_average
            updated = True
        if product_data.image_small and not product.image_small:
            product.image_small = product_data.image_small
            updated = True
        if product_data.image_large and not product.image_large:
            product.image_large = product_data.image_large
            updated = True
        # Also try to update price from ProductRecord
        if _apply_product_price(product, session):
            updated = True
        if updated:
            session.add(product)
            session.commit()
            session.refresh(product)

    owner_id = current_user.id
    if owner_id is None:
        raise HTTPException(status_code=401, detail="User not found")

    if product.id is None:
        session.add(product)
        session.flush()

    entry = models.CollectionEntry(
        user_id=owner_id,
        product_id=product.id,
        quantity=payload.quantity,
        purchase_price=payload.purchase_price,
    )

    session.add(entry)
    session.commit()
    session.refresh(entry)
    session.refresh(product)
    return entry

