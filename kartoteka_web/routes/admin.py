from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from .. import models
from ..auth import get_current_user, oauth2_scheme
from ..database import get_session
from ..services import catalog_sync

router = APIRouter(prefix="/api/admin", tags=["admin"])

async def get_admin_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> models.User:
    user = await get_current_user(session=session, token=token)
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Brak uprawnień administratora"
        )
    return user

@router.post("/tools/sync-prices")
def sync_prices(
    session: Session = Depends(get_session),
    _admin: models.User = Depends(get_admin_user)
):
    """Force update prices and catalog data."""
    try:
        # In a real scenario, this might be a background task
        # For now, we run it synchronously (might timeout for large sets)
        summary = catalog_sync.sync_sets(session)
        return {
            "message": "Synchronizacja zakończona pomyślnie.",
            "details": {
                "sets": len(summary.set_codes),
                "added": summary.cards_added,
                "updated": summary.cards_updated
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tools/sync-catalog")
def sync_catalog(
    session: Session = Depends(get_session),
    _admin: models.User = Depends(get_admin_user)
):
    """Force update catalog (same as sync-prices for now)."""
    try:
        summary = catalog_sync.sync_sets(session)
        return {
            "message": "Katalog zaktualizowany pomyślnie.",
            "details": {
                "sets": len(summary.set_codes),
                "added": summary.cards_added,
                "updated": summary.cards_updated
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
