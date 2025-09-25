"""FastAPI entry point for the Kartoteka web API and interface."""

from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import logging
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import selectinload
from sqlmodel import select

load_dotenv(Path(__file__).resolve().with_name(".env"))

from kartoteka import pricing
from kartoteka_web import catalogue, models
from kartoteka_web.auth import get_current_user, oauth2_scheme
from kartoteka_web.database import init_db, session_scope
from kartoteka_web.routes import cards, users
from kartoteka_web.utils import images as image_utils, sets as set_utils

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


def _refresh_catalogue(force: bool = False) -> int:
    with session_scope() as session:
        return catalogue.refresh_catalogue(session, force=force)


async def _catalogue_update_loop() -> None:
    while True:
        try:
            await asyncio.sleep(_seconds_until_next_midnight())
        except asyncio.CancelledError:
            raise
        updated = await asyncio.to_thread(_refresh_catalogue)
        if updated:
            logger.info("Background catalogue refresh changed %s records", updated)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    await asyncio.to_thread(_refresh_catalogue)
    price_task = asyncio.create_task(_price_update_loop())
    catalogue_task = asyncio.create_task(_catalogue_update_loop())
    app.state.price_task = price_task
    app.state.catalogue_task = catalogue_task
    try:
        yield
    finally:
        for task in (getattr(app.state, "price_task", None), getattr(app.state, "catalogue_task", None)):
            if task is None:
                continue
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Inject strict security headers for every HTTP response."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        response = await call_next(request)
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload"
        )
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()",
        )
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none';",
        )
        return response


app = FastAPI(title="Kartoteka Web", version="1.0.0", lifespan=lifespan)
app.add_middleware(SecurityHeadersMiddleware)
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
async def home_page(request: Request) -> HTMLResponse:
    username, invalid_credentials, avatar_url = await _resolve_request_user(request)
    context = {
        "request": request,
        "username": username if not invalid_credentials else "",
        "avatar_url": avatar_url if not invalid_credentials else "",
    }
    return templates.TemplateResponse("home.html", context)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    username, invalid_credentials, avatar_url = await _resolve_request_user(request)
    context = {
        "request": request,
        "username": username if not invalid_credentials else "",
        "avatar_url": avatar_url if not invalid_credentials else "",
    }
    return templates.TemplateResponse("login.html", context)


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request) -> HTMLResponse:
    username, invalid_credentials, avatar_url = await _resolve_request_user(request)
    context = {
        "request": request,
        "username": username if not invalid_credentials else "",
        "avatar_url": avatar_url if not invalid_credentials else "",
    }
    return templates.TemplateResponse("register.html", context)


async def _resolve_request_user(request: Request) -> tuple[str, bool, str]:
    """Return ``(username, invalid, avatar_url)`` for the current request."""

    try:
        token = await oauth2_scheme(request)
    except HTTPException:
        return "", bool(request.headers.get("Authorization")), ""

    with session_scope() as session:
        try:
            user = await get_current_user(session=session, token=token)
        except HTTPException:
            return "", True, ""
        return user.username, False, user.avatar_url or ""


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request) -> HTMLResponse:
    username, invalid_credentials, avatar_url = await _resolve_request_user(request)
    if invalid_credentials:
        return templates.TemplateResponse(
            "login.html", {"request": request, "username": ""}
        )
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "username": username, "avatar_url": avatar_url},
    )


@app.get("/cards/add", response_class=HTMLResponse)
async def add_card_page(request: Request) -> HTMLResponse:
    username, invalid_credentials, avatar_url = await _resolve_request_user(request)
    if invalid_credentials:
        return templates.TemplateResponse(
            "login.html", {"request": request, "username": ""}
        )
    return templates.TemplateResponse(
        "add_card.html",
        {"request": request, "username": username, "avatar_url": avatar_url},
    )


@app.get("/portfolio", response_class=HTMLResponse)
async def portfolio_page(request: Request) -> HTMLResponse:
    username, invalid_credentials, avatar_url = await _resolve_request_user(request)
    if invalid_credentials:
        return templates.TemplateResponse(
            "login.html", {"request": request, "username": ""}
        )
    return templates.TemplateResponse(
        "portfolio.html",
        {"request": request, "username": username, "avatar_url": avatar_url},
    )


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request) -> HTMLResponse:
    username, invalid_credentials, avatar_url = await _resolve_request_user(request)
    if invalid_credentials:
        return templates.TemplateResponse(
            "login.html", {"request": request, "username": ""}
        )
    return templates.TemplateResponse(
        "settings.html",
        {"request": request, "username": username, "avatar_url": avatar_url},
    )


@app.get("/cards/{set_identifier}/{number}", response_class=HTMLResponse)
async def card_detail_page(request: Request, set_identifier: str, number: str) -> HTMLResponse:
    username, invalid_credentials, avatar_url = await _resolve_request_user(request)
    if invalid_credentials:
        return templates.TemplateResponse(
            "login.html", {"request": request, "username": ""}
        )
    raw_query = {key: value for key, value in request.query_params.items()}
    card_name = (raw_query.get("name") or "").strip()
    set_name = (raw_query.get("set_name") or "").strip()
    set_code = (raw_query.get("set_code") or "").strip()
    total = (raw_query.get("total") or "").strip()

    number_clean = pricing.sanitize_number(number)
    resolved_number = number_clean or number
    resolved_name = card_name
    resolved_set_name = set_name
    resolved_set_code = set_code
    resolved_total = total

    identifier = set_utils.clean_code(set_identifier) or set_identifier.strip().lower()

    with session_scope() as session:
        record = None
        if resolved_number:
            candidates = session.exec(
                select(models.CardRecord).where(models.CardRecord.number == resolved_number)
            ).all()
            for candidate in candidates:
                candidate_identifier = set_utils.slugify_set_identifier(
                    set_code=candidate.set_code, set_name=candidate.set_name
                )
                candidate_name = (candidate.set_name or "").strip().lower()
                if identifier and candidate_identifier == identifier:
                    record = candidate
                    break
                if resolved_set_name and candidate_name == resolved_set_name.lower():
                    record = candidate
                    break
            if record is None and candidates:
                record = candidates[0]

        if record:
            resolved_name = resolved_name or record.name
            resolved_set_name = resolved_set_name or (record.set_name or "")
            if not resolved_set_code:
                resolved_set_code = (
                    record.set_code_clean or record.set_code or ""
                )
            if not resolved_total and record.total:
                resolved_total = record.total
            if not resolved_number:
                resolved_number = record.number

    if resolved_set_code and not resolved_set_name:
        info = set_utils.get_set_info(set_code=resolved_set_code)
        if info:
            resolved_set_name = info.get("name") or resolved_set_name
            if not resolved_total and info.get("total"):
                resolved_total = str(info.get("total"))
    elif resolved_set_name and not resolved_set_code:
        guessed_code = set_utils.guess_set_code(resolved_set_name)
        if guessed_code:
            resolved_set_code = guessed_code

    resolved_set_code = set_utils.clean_code(resolved_set_code) or ""

    context = {
        "request": request,
        "username": username,
        "avatar_url": avatar_url,
        "card_name": resolved_name,
        "card_number": resolved_number,
        "card_set_code": resolved_set_code or identifier,
        "card_set_name": resolved_set_name,
        "card_total": resolved_total,
    }
    return templates.TemplateResponse("card_detail.html", context)


def _public_page_context(
    request: Request, username: str, invalid: bool, avatar_url: str
) -> dict[str, Any]:
    return {
        "request": request,
        "username": "" if invalid else username,
        "avatar_url": "" if invalid else avatar_url,
    }


@app.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request) -> HTMLResponse:
    username, invalid_credentials, avatar_url = await _resolve_request_user(request)
    context = _public_page_context(request, username, invalid_credentials, avatar_url)
    return templates.TemplateResponse("terms.html", context)


@app.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request) -> HTMLResponse:
    username, invalid_credentials, avatar_url = await _resolve_request_user(request)
    context = _public_page_context(request, username, invalid_credentials, avatar_url)
    return templates.TemplateResponse("privacy.html", context)


@app.get("/cookies", response_class=HTMLResponse)
async def cookies_page(request: Request) -> HTMLResponse:
    username, invalid_credentials, avatar_url = await _resolve_request_user(request)
    context = _public_page_context(request, username, invalid_credentials, avatar_url)
    return templates.TemplateResponse("cookies.html", context)


def run() -> None:
    """Helper to run the development server."""

    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    run()
