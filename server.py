"""FastAPI entry point for the Kartoteka web API and interface."""

from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import logging
from typing import Optional

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import selectinload
from sqlmodel import select

from kartoteka import pricing
from kartoteka_web import models
from kartoteka_web.auth import get_current_user
from kartoteka_web.database import init_db, session_scope
from kartoteka_web.routes import cards, users

logger = logging.getLogger(__name__)

def _apply_variant_multiplier(entry: models.CollectionEntry, base_price: Optional[float]) -> Optional[float]:
    if base_price is None:
        return None
    multiplier = 1.0
    if entry.is_reverse or entry.is_holo:
        multiplier *= pricing.HOLO_REVERSE_MULTIPLIER
    try:
        return round(float(base_price) * multiplier, 2)
    except (TypeError, ValueError):
        return base_price


def _refresh_prices() -> int:
    """Synchronously refresh prices for all collection entries."""

    updated = 0
    with session_scope() as session:
        entries = session.exec(
            select(models.CollectionEntry).options(selectinload(models.CollectionEntry.card))
        ).all()
        for entry in entries:
            card = entry.card
            if not card:
                continue
            price = pricing.fetch_card_price(
                name=card.name,
                number=card.number,
                set_name=card.set_name,
                set_code=card.set_code,
            )
            new_price = _apply_variant_multiplier(entry, price)
            if new_price is not None:
                entry.current_price = new_price
                entry.last_price_update = dt.datetime.now(dt.timezone.utc)
                updated += 1
        session.flush()
    return updated


async def _price_update_loop(interval: int = 3600) -> None:
    while True:
        updated = await asyncio.to_thread(_refresh_prices)
        if updated:
            logger.info("Background price refresh updated %s entries", updated)
        await asyncio.sleep(interval)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    task = asyncio.create_task(_price_update_loop())
    app.state.price_task = task
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="Kartoteka Web", version="1.0.0", lifespan=lifespan)
app.include_router(users.router)
app.include_router(cards.router)

app.mount("/static", StaticFiles(directory="kartoteka_web/static"), name="static")

templates = Jinja2Templates(directory="kartoteka_web/templates")


@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("register.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request, current_user: models.User = Depends(get_current_user)
) -> HTMLResponse:
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "username": current_user.username},
    )


@app.get("/portfolio", response_class=HTMLResponse)
async def portfolio_page(
    request: Request, current_user: models.User = Depends(get_current_user)
) -> HTMLResponse:
    return templates.TemplateResponse(
        "portfolio.html",
        {"request": request, "username": current_user.username},
    )


def run() -> None:
    """Helper to run the development server."""

    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    run()
