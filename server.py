"""FastAPI entry point for the Kartoteka web API and interface."""

from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import logging
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import selectinload
from sqlmodel import select

load_dotenv(Path(__file__).resolve().with_name(".env"))

from kartoteka import pricing
from kartoteka_web import models
from kartoteka_web.auth import get_current_user, oauth2_scheme
from kartoteka_web.database import init_db, session_scope
from kartoteka_web.routes import cards, users
from kartoteka_web.utils import images as image_utils

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
    now = dt.datetime.now(dt.timezone.utc)
    with session_scope() as session:
        entries = session.exec(
            select(models.CollectionEntry).options(selectinload(models.CollectionEntry.card))
        ).all()
        price_cache: dict[int, Optional[float]] = {}
        recorded_cards: set[int] = set()
        for entry in entries:
            card = entry.card
            if not card or card.id is None:
                continue
            if card.id not in price_cache:
                price_cache[card.id] = pricing.fetch_card_price(
                    name=card.name,
                    number=card.number,
                    set_name=card.set_name,
                    set_code=card.set_code,
                )
            price = price_cache[card.id]
            new_price = _apply_variant_multiplier(entry, price)
            if new_price is not None:
                entry.current_price = new_price
                entry.last_price_update = now
                updated += 1
            if price is not None and card.id not in recorded_cards:
                cards.record_price_history(session, card, price, now)
                recorded_cards.add(card.id)
        session.flush()
    return updated


def _seconds_until_next_midnight(now: dt.datetime | None = None) -> float:
    """Return seconds until the next local midnight."""

    reference = (now or dt.datetime.now(dt.timezone.utc)).astimezone()
    next_midnight = (reference + dt.timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    delta = next_midnight - reference
    return max(delta.total_seconds(), 1.0)


async def _price_update_loop() -> None:
    while True:
        try:
            await asyncio.sleep(_seconds_until_next_midnight())
        except asyncio.CancelledError:
            raise
        updated = await asyncio.to_thread(_refresh_prices)
        if updated:
            logger.info("Background price refresh updated %s entries", updated)


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
if Path("set_logos").exists():
    app.mount("/set-logos", StaticFiles(directory="set_logos"), name="set-logos")

image_utils.ensure_directory()
card_image_mount = image_utils.CARD_IMAGE_URL_PREFIX
if not card_image_mount.startswith("/"):
    card_image_mount = f"/{card_image_mount}"
app.mount(
    card_image_mount,
    StaticFiles(directory=str(image_utils.CARD_IMAGE_DIR)),
    name="card-images",
)

templates = Jinja2Templates(directory="kartoteka_web/templates")


@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("register.html", {"request": request})


async def _resolve_request_username(request: Request) -> tuple[str, bool]:
    """Return the username for the request or flag invalid credentials."""

    try:
        token = await oauth2_scheme(request)
    except HTTPException:
        return "", bool(request.headers.get("Authorization"))

    with session_scope() as session:
        try:
            user = await get_current_user(session=session, token=token)
        except HTTPException:
            return "", True
        return user.username, False


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request) -> HTMLResponse:
    username, invalid_credentials = await _resolve_request_username(request)
    if invalid_credentials:
        return templates.TemplateResponse(
            "login.html", {"request": request, "username": ""}
        )
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "username": username},
    )


@app.get("/cards/add", response_class=HTMLResponse)
async def add_card_page(request: Request) -> HTMLResponse:
    username, invalid_credentials = await _resolve_request_username(request)
    if invalid_credentials:
        return templates.TemplateResponse(
            "login.html", {"request": request, "username": ""}
        )
    return templates.TemplateResponse(
        "add_card.html",
        {"request": request, "username": username},
    )


@app.get("/portfolio", response_class=HTMLResponse)
async def portfolio_page(request: Request) -> HTMLResponse:
    username, invalid_credentials = await _resolve_request_username(request)
    if invalid_credentials:
        return templates.TemplateResponse(
            "login.html", {"request": request, "username": ""}
        )
    return templates.TemplateResponse(
        "portfolio.html",
        {"request": request, "username": username},
    )


@app.get("/cards/{set_identifier}/{number}", response_class=HTMLResponse)
async def card_detail_page(request: Request, set_identifier: str, number: str) -> HTMLResponse:
    username, invalid_credentials = await _resolve_request_username(request)
    if invalid_credentials:
        return templates.TemplateResponse(
            "login.html", {"request": request, "username": ""}
        )
    query = dict(request.query_params)
    context = {
        "request": request,
        "username": username,
        "card_name": query.get("name", ""),
        "card_number": number,
        "card_set_code": set_identifier,
        "card_set_name": query.get("set_name", ""),
        "card_total": query.get("total", ""),
    }
    return templates.TemplateResponse("card_detail.html", context)


def run() -> None:
    """Helper to run the development server."""

    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    run()
