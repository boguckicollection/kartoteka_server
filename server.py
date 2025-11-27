"""FastAPI entry point for the Kartoteka web API and interface."""

from __future__ import annotations

import contextlib
import logging
import os
from pathlib import Path
import contextlib
import logging
import os
from pathlib import Path
from typing import Any, Optional

import anyio
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, Request, Response, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select, func

load_dotenv(Path(__file__).resolve().with_name(".env"))

from kartoteka_web import models, scheduler
from kartoteka_web.auth import get_current_user, oauth2_scheme
from kartoteka_web.database import init_db, session_scope, get_session
from kartoteka_web.routes import cards, users, products, collections, admin
from kartoteka_web.services import set_icons, tcg_api
from kartoteka_web.services.tcg_api import get_latest_products
from kartoteka_web.utils import images as image_utils, sets as set_utils, text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting application...")
    print("🚀 Kartoteka: Starting application...")
    init_db()
    try:
        print("🔧 Kartoteka: Starting scheduler...")
        scheduler.start_scheduler()
        print("✅ Kartoteka: Scheduler started!")
    except Exception as e:
        print(f"❌ Kartoteka: Scheduler failed to start: {e}")
        logger.error(f"Scheduler failed to start: {e}", exc_info=True)
    # await anyio.to_thread.run_sync(set_icons.ensure_set_icons)
    yield
    # Shutdown
    logger.info("Shutting down application...")
    print("🛑 Kartoteka: Shutting down application...")
    try:
        scheduler.stop_scheduler()
    except Exception as e:
        print(f"⚠️  Kartoteka: Error stopping scheduler: {e}")
        logger.warning(f"Error stopping scheduler: {e}")


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
            "manifest-src 'self'; "
            "frame-ancestors 'none';",
        )
        return response


app = FastAPI(title="Kartoteka Web", version="1.0.0", lifespan=lifespan)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")
app.include_router(users.router)
app.include_router(cards.router)
app.include_router(products.router)
app.include_router(admin.router)
app.include_router(collections.router)

app.mount("/static", StaticFiles(directory="kartoteka_web/static"), name="static")
app.mount("/icon", StaticFiles(directory="icon"), name="icon-assets")

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
async def home_page(
    request: Request,
    db: Session = Depends(get_session),
):
    rapidapi_key = os.getenv("RAPIDAPI_KEY")
    rapidapi_host = os.getenv("RAPIDAPI_HOST")

    latest_products = get_latest_products(
        rapidapi_key=rapidapi_key, rapidapi_host=rapidapi_host
    )

    username, invalid_credentials, avatar_url, is_admin = await _resolve_request_user(request)

    # Get user data if logged in
    collection_stats = None
    recently_added = []
    price_changes = []

    if username and not invalid_credentials:
        try:
            # Get current user
            token = await oauth2_scheme(request)
            with session_scope() as session:
                user = await get_current_user(session=session, token=token)

                # Get collection stats
                from kartoteka_web.routes.cards import get_collection_stats, get_recently_added_cards, get_price_changes

                # Temporarily set user for function calls
                # Note: These functions expect Depends(get_current_user) but we'll call them directly
                entries = session.exec(
                    select(models.CollectionEntry)
                    .where(models.CollectionEntry.user_id == user.id)
                    .options(
                        selectinload(models.CollectionEntry.card),
                        selectinload(models.CollectionEntry.product)
                    )
                ).all()

                # Calculate stats manually
                total_cards = sum(entry.quantity or 0 for entry in entries)
                unique_cards = len(entries)
                total_value = 0.0

                for entry in entries:
                    if entry.card and entry.card.price:
                        total_value += entry.card.price
                    elif entry.product and entry.product.price:
                        total_value += entry.product.price

                collection_stats = {
                    "total_cards": total_cards,
                    "unique_cards": unique_cards,
                    "total_value": round(total_value, 2),
                }

                # Get recently added (last 5)
                recent_entries = session.exec(
                    select(models.CollectionEntry)
                    .where(models.CollectionEntry.user_id == user.id)
                    .options(
                        selectinload(models.CollectionEntry.card),
                        selectinload(models.CollectionEntry.product)
                    )
                    .order_by(models.CollectionEntry.id.desc())
                    .limit(5)
                ).all()

                for entry in recent_entries:
                    if entry.card:
                        recently_added.append({
                            "type": "card",
                            "name": entry.card.name,
                            "image_small": entry.card.image_small,
                            "set_name": entry.card.set_name,
                            "price": entry.card.price,
                        })
                    elif entry.product:
                        recently_added.append({
                            "type": "product",
                            "name": entry.product.name,
                            "image_small": entry.product.image_small,
                            "set_name": entry.product.set_name,
                            "price": entry.product.price,
                        })

                # Get price changes (top 5)
                for entry in entries[:50]:  # Limit to first 50 to avoid performance issues
                    if entry.card:
                        current_price = entry.card.price or 0.0
                        avg_price = entry.card.price_7d_average or 0.0

                        if current_price > 0 and avg_price > 0:
                            change = current_price - avg_price
                            change_percent = (change / avg_price) * 100

                            price_changes.append({
                                "name": entry.card.name,
                                "image_small": entry.card.image_small,
                                "current_price": current_price,
                                "change_percent": round(change_percent, 2),
                            })
                    elif entry.product:
                        current_price = entry.product.price or 0.0
                        avg_price = entry.product.price_7d_average or 0.0

                        if current_price > 0 and avg_price > 0:
                            change = current_price - avg_price
                            change_percent = (change / avg_price) * 100

                            price_changes.append({
                                "name": entry.product.name,
                                "image_small": entry.product.image_small,
                                "current_price": current_price,
                                "change_percent": round(change_percent, 2),
                            })

                # Sort by absolute change percent
                price_changes.sort(key=lambda x: abs(x["change_percent"]), reverse=True)
                price_changes = price_changes[:5]

        except HTTPException:
            pass

    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "latest_products": latest_products,
            "username": username if not invalid_credentials else "",
            "avatar_url": avatar_url if not invalid_credentials else "",
            "is_admin": is_admin if not invalid_credentials else False,
            "collection_stats": collection_stats,
            "recently_added": recently_added,
            "price_changes": price_changes,
        },
    )


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    username, invalid_credentials, avatar_url, is_admin = await _resolve_request_user(request)
    context = {
        "request": request,
        "username": username if not invalid_credentials else "",
        "avatar_url": avatar_url if not invalid_credentials else "",
        "is_admin": is_admin if not invalid_credentials else False,
    }
    return templates.TemplateResponse("login.html", context)


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request) -> HTMLResponse:
    username, invalid_credentials, avatar_url, is_admin = await _resolve_request_user(request)
    context = {
        "request": request,
        "username": username if not invalid_credentials else "",
        "avatar_url": avatar_url if not invalid_credentials else "",
        "is_admin": is_admin if not invalid_credentials else False,
    }
    return templates.TemplateResponse("register.html", context)



async def _resolve_request_user(request: Request) -> tuple[str, bool, str, bool]:
    """Return ``(username, invalid, avatar_url, is_admin)`` for the current request."""
    
    token = None
    # 1. Try OAuth2 header (Bearer ...)
    try:
        token = await oauth2_scheme(request)
    except HTTPException:
        pass
    
    # 2. Try Cookie
    if not token:
        token = request.cookies.get("access_token")
        # Remove 'Bearer ' prefix if present in cookie (though usually we store just the token)
        if token and token.startswith("Bearer "):
            token = token[7:]

    if not token:
        # No token found
        return "", bool(request.headers.get("Authorization")), "", False

    with session_scope() as session:
        try:
            user = await get_current_user(session=session, token=token)
        except HTTPException:
            return "", True, "", False
        return user.username, False, user.avatar_url or "", user.is_admin


async def _render_authenticated_page(
    request: Request, template_name: str, extra_context: dict[str, Any] | None = None
) -> HTMLResponse:
    username, invalid_credentials, avatar_url, is_admin = await _resolve_request_user(request)
    
    # If strict auth required (for dashboard/collection), redirect to login if no user
    if not username:
        return templates.TemplateResponse("login.html", {"request": request, "username": ""})

    context: dict[str, Any] = {
        "request": request,
        "username": username,
        "avatar_url": avatar_url,
        "is_admin": is_admin,
    }
    if extra_context:
        context.update(extra_context)
    return templates.TemplateResponse(template_name, context)



@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request) -> HTMLResponse:
    return await _render_authenticated_page(request, "dashboard.html")


@app.get("/collection", response_class=HTMLResponse)
async def collection_page(request: Request) -> HTMLResponse:
    return await _render_authenticated_page(request, "dashboard.html")


@app.get("/cards/add", response_class=HTMLResponse)
async def add_card_page(request: Request) -> HTMLResponse:
    return await _render_authenticated_page(request, "add_card.html")


@app.get("/portfolio", response_class=HTMLResponse)
async def portfolio_page(request: Request) -> HTMLResponse:
    return await _render_authenticated_page(request, "portfolio.html")


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request) -> HTMLResponse:
    return await _render_authenticated_page(request, "settings.html")


@app.get("/my-collections", response_class=HTMLResponse)
async def my_collections_page(request: Request) -> HTMLResponse:
    return await _render_authenticated_page(request, "collections.html")


@app.get("/my-collections/{collection_id}", response_class=HTMLResponse)
async def collection_detail_page(request: Request, collection_id: int) -> HTMLResponse:
    return await _render_authenticated_page(
        request, "collection_detail.html", {"collection_id": collection_id}
    )


@app.get("/my-collections/{collection_id}/print", response_class=HTMLResponse)
async def collection_print_page(request: Request, collection_id: int) -> HTMLResponse:
    return await _render_authenticated_page(
        request, "collection_print.html", {"collection_id": collection_id}
    )


@app.get("/sets", response_class=HTMLResponse)
async def sets_list_page(request: Request) -> HTMLResponse:
    """Page showing all available Pokemon TCG sets with print option."""
    username, invalid_credentials, avatar_url, is_admin = await _resolve_request_user(request)
    context = _public_page_context(request, username, invalid_credentials, avatar_url, is_admin)
    return templates.TemplateResponse("sets.html", context)


@app.get("/sets/{set_code}/print", response_class=HTMLResponse)
async def set_print_page(request: Request, set_code: str) -> HTMLResponse:
    """Print template page for a specific set (without collection)."""
    username, invalid_credentials, avatar_url, is_admin = await _resolve_request_user(request)
    context = _public_page_context(request, username, invalid_credentials, avatar_url, is_admin)
    context["set_code"] = set_code
    return templates.TemplateResponse("set_print.html", context)


@app.get("/cards/{set_identifier}/{number}", response_class=HTMLResponse)
async def card_detail_page(request: Request, set_identifier: str, number: str) -> HTMLResponse:
    username, invalid_credentials, avatar_url, is_admin = await _resolve_request_user(request)
    if invalid_credentials:
        return templates.TemplateResponse(
            "login.html", {"request": request, "username": ""}
        )
    raw_query = {key: value for key, value in request.query_params.items()}
    card_name = (raw_query.get("name") or "").strip()
    set_name = (raw_query.get("set_name") or "").strip()
    set_code = (raw_query.get("set_code") or "").strip()
    total = (raw_query.get("total") or "").strip()

    number_clean = text.sanitize_number(number)
    resolved_number = number_clean or number
    resolved_name = card_name
    resolved_set_name = set_name
    resolved_set_code = set_code
    resolved_total = total

    identifier = set_utils.clean_code(set_identifier) or set_identifier.strip().lower()
    with session_scope() as session:
        record: models.Card | None = None

        def _pick_candidate(candidates: list[models.Card]) -> models.Card | None:
            if not candidates:
                return None
            for candidate in candidates:
                slug = set_utils.slugify_set_identifier(
                    set_code=candidate.set_code, set_name=candidate.set_name
                )
                if identifier and slug == identifier:
                    return candidate
            target_name = (resolved_set_name or "").strip().lower()
            if target_name:
                for candidate in candidates:
                    if (candidate.set_name or "").strip().lower() == target_name:
                        return candidate
            target_code = (resolved_set_code or "").strip().lower()
            if target_code:
                for candidate in candidates:
                    if (candidate.set_code or "").strip().lower() == target_code:
                        return candidate
            target_card_name = (resolved_name or "").strip().lower()
            if target_card_name:
                for candidate in candidates:
                    if (candidate.name or "").strip().lower() == target_card_name:
                        return candidate
            return candidates[0]

        if resolved_number:
            candidate_stmt = select(models.Card).where(models.Card.number == resolved_number)
            candidates = session.exec(candidate_stmt).all()
            record = _pick_candidate(candidates)

        if record is None and resolved_number and resolved_number != number:
            candidate_stmt = select(models.Card).where(models.Card.number == number)
            candidates = session.exec(candidate_stmt).all()
            record = _pick_candidate(candidates)

        if record is None and resolved_name:
            candidate_stmt = select(models.Card).where(models.Card.name == resolved_name)
            candidates = session.exec(candidate_stmt).all()
            record = _pick_candidate(candidates)

        if record is None and identifier:
            all_cards = session.exec(select(models.Card)).all()
            candidates = [
                candidate
                for candidate in all_cards
                if set_utils.slugify_set_identifier(
                    set_code=candidate.set_code, set_name=candidate.set_name
                )
                == identifier
            ]
            record = _pick_candidate(candidates) or (candidates[0] if candidates else None)

        if record and not resolved_name:
            resolved_name = record.name
        if record and record.set_name:
            resolved_set_name = record.set_name
        if record and record.set_code:
            resolved_set_code = record.set_code
        if record and not resolved_number:
            resolved_number = record.number

    if not resolved_name:
        raise HTTPException(status_code=404, detail="Nie znaleziono karty.")

    resolved_set_code = set_utils.clean_code(resolved_set_code) or identifier or ""

    context = {
        "request": request,
        "username": username,
        "avatar_url": avatar_url,
        "is_admin": is_admin,
        "card_name": resolved_name,
        "card_number": resolved_number,
        "card_set_code": resolved_set_code or identifier,
        "card_set_name": resolved_set_name,
        "card_total": resolved_total,
    }
    return templates.TemplateResponse("card_detail.html", context)


def _public_page_context(
    request: Request, username: str, invalid: bool, avatar_url: str, is_admin: bool
) -> dict[str, Any]:
    return {
        "request": request,
        "username": "" if invalid else username,
        "avatar_url": "" if invalid else avatar_url,
        "is_admin": False if invalid else is_admin,
    }


@app.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request) -> HTMLResponse:
    username, invalid_credentials, avatar_url, is_admin = await _resolve_request_user(request)
    context = _public_page_context(request, username, invalid_credentials, avatar_url, is_admin)
    return templates.TemplateResponse("terms.html", context)


@app.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request) -> HTMLResponse:
    username, invalid_credentials, avatar_url, is_admin = await _resolve_request_user(request)
    context = _public_page_context(request, username, invalid_credentials, avatar_url, is_admin)
    return templates.TemplateResponse("privacy.html", context)


@app.get("/cookies", response_class=HTMLResponse)
async def cookies_page(request: Request) -> HTMLResponse:
    username, invalid_credentials, avatar_url, is_admin = await _resolve_request_user(request)
    context = _public_page_context(request, username, invalid_credentials, avatar_url, is_admin)
    return templates.TemplateResponse("cookies.html", context)


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Admin dashboard with system statistics."""
    username, invalid_credentials, avatar_url, is_admin = await _resolve_request_user(request)
    
    if not username:
        return templates.TemplateResponse("login.html", {"request": request, "username": ""})
    
    if not is_admin:
        raise HTTPException(status_code=403, detail="Brak uprawnień administratora")

    # Calculate statistics
    total_users = session.exec(select(func.count(models.User.id))).one()
    total_cards = session.exec(select(func.count(models.CardRecord.id))).one()
    total_products = session.exec(select(func.count(models.ProductRecord.id))).one()
    total_collections = session.exec(select(func.count(models.Collection.id))).one()
    
    # Calculate total value of all user collections (approximate)
    # This is a simplified query - summing all prices from all entries
    # For better performance in production, this should be cached or materialized
    total_value = 0.0
    # Note: This might be heavy if table is huge. For now it's fine.
    # Alternative: session.exec(select(func.sum(models.CollectionEntry.purchase_price))).one() 
    # but purchase_price is often null. We want market value.
    # We'll skip complex join for now and just show collection count/size.
    
    stats = {
        "total_users": total_users,
        "total_cards": total_cards,
        "total_products": total_products,
        "total_collections": total_collections,
        "total_value": 0.0, # Placeholder for now
    }

    # Get recent users
    recent_users = session.exec(
        select(models.User).order_by(models.User.created_at.desc()).limit(10)
    ).all()

    context = {
        "request": request,
        "username": username,
        "avatar_url": avatar_url,
        "stats": stats,
        "users": recent_users,
    }
    return templates.TemplateResponse("admin_dashboard.html", context)


def _uvicorn_config() -> tuple[str, int, bool]:
    """Return host, port and reload flag for running the server."""

    host = os.getenv("HOST") or os.getenv("KARTOTEKA_HOST") or "0.0.0.0"
    host = host.strip() or "0.0.0.0"

    port_value = os.getenv("PORT") or os.getenv("KARTOTEKA_PORT") or "8000"
    try:
        port = int(port_value)
    except (TypeError, ValueError):
        logger.warning("Invalid port value %r provided; falling back to 8000", port_value)
        port = 8000

    reload_value = os.getenv("KARTOTEKA_RELOAD", "").strip().lower()
    reload_enabled = reload_value in {"1", "true", "yes", "on"}

    return host, port, reload_enabled


def run() -> None:
    """Helper to run the development server."""

    import uvicorn

    host, port, reload_enabled = _uvicorn_config()
    uvicorn.run("server:app", host=host, port=port, reload=reload_enabled)


if __name__ == "__main__":
    run()
