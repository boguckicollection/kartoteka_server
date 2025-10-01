"""FastAPI entry point for the Kartoteka web API and interface."""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import selectinload
from sqlmodel import select

load_dotenv(Path(__file__).resolve().with_name(".env"))

from kartoteka_web import models
from kartoteka_web.auth import get_current_user, oauth2_scheme
from kartoteka_web.database import init_db, session_scope
from kartoteka_web.routes import cards, users
from kartoteka_web.utils import images as image_utils, sets as set_utils, text

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


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


async def _render_authenticated_page(
    request: Request, template_name: str, extra_context: dict[str, Any] | None = None
) -> HTMLResponse:
    username, invalid_credentials, avatar_url = await _resolve_request_user(request)
    if invalid_credentials:
        return templates.TemplateResponse("login.html", {"request": request, "username": ""})

    context: dict[str, Any] = {
        "request": request,
        "username": username,
        "avatar_url": avatar_url,
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
