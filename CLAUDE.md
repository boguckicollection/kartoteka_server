# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Kartoteka is a FastAPI-powered web application for managing a private Pokémon card collection. It provides authenticated dashboards, card search, portfolio tracking, and collection management backed by SQLModel/SQLite.

## Development Commands

### Running the Server
```bash
# Local development (auto-reload enabled)
uvicorn server:app --reload

# Or use the helper
python server.py

# Docker Compose (includes ngrok tunnel)
docker compose up --build
```

Server defaults to `http://127.0.0.1:8000/`. Configure via environment variables:
- `HOST` / `KARTOTEKA_HOST` (default: `0.0.0.0`)
- `PORT` / `KARTOTEKA_PORT` (default: `8000`)
- `KARTOTEKA_RELOAD` (default: `false`, set to `1`/`true` to enable)

### Testing
```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a single test file
pytest tests/api/test_cards.py

# Run a specific test
pytest tests/api/test_cards.py::test_collection_crud_lifecycle
```

### Syncing Card Catalog
```bash
# Full sync (requires RAPIDAPI_KEY in .env)
./sync_catalog.py --verbose

# Limited sync for testing
./sync_catalog.py --sets sv01 sv02 --limit 25
```

Populates `CardRecord` table from RapidAPI for offline card search.

## Architecture

### Application Entry Point
- **`server.py`**: FastAPI application with lifespan management, security headers middleware, static file mounts, and HTML template rendering
- Routes are modularized in `kartoteka_web/routes/` (users, cards, products)
- Database initializes automatically on startup via `lifespan` context manager

### Database Layer
- **`kartoteka_web/database.py`**: SQLModel engine configuration, session management, and schema migrations
- **`kartoteka_web/models.py`**: Core models:
  - `User`: Authentication and collection ownership
  - `Card` & `Product`: User's owned items with pricing
  - `CardRecord` & `ProductRecord`: Cached catalog for search (normalized fields for fuzzy matching)
  - `CollectionEntry`: Join table linking users to cards/products with quantity and metadata
- Uses SQLite by default (`kartoteka.db`), configurable via `KARTOTEKA_DATABASE_URL`
- Thread-safe write locks for SQLite (`DATABASE_WRITE_LOCK` in `database.py`)

### Authentication
- **`kartoteka_web/auth.py`**: OAuth2 with JWT tokens (bcrypt password hashing)
- Token endpoint: `/users/login`
- Configure secret via `KARTOTEKA_SECRET_KEY` or `SECRET_KEY` (defaults to `change-me`)
- Session-aware templates resolve user via `_resolve_request_user()` helper in `server.py`

### API Routes
- **`kartoteka_web/routes/cards.py`**: Card search, detail, collection CRUD
  - Search supports fuzzy matching on normalized names/numbers from `CardRecord`
  - Parses card numbers from query strings (e.g., "Pikachu 25/100")
  - Falls back to RapidAPI when local catalog misses
  - **GET `/cards/stats`**: Collection statistics (total cards, value, value history)
  - **GET `/cards/recently-added`**: Recently added cards/products (limit=10)
  - **GET `/cards/price-changes`**: Cards with biggest price changes in user's collection
  - **POST `/cards/refresh-prices`**: Refresh prices for all cards in collection
- **`kartoteka_web/routes/users.py`**: Registration, login, profile updates
- **`kartoteka_web/routes/products.py`**: Product search and collection

### External API Integration
- **`kartoteka_web/services/tcg_api.py`**: RapidAPI wrapper for Pokémon TCG data
- Requires `RAPIDAPI_KEY` and `RAPIDAPI_HOST` in `.env`
- Also accepts legacy variable names (`KARTOTEKA_RAPIDAPI_KEY`, `POKEMONTCG_RAPIDAPI_KEY`)
- Handles EUR→PLN conversion for pricing
- **Product filtering**: `get_latest_products()` filters to show products from last 90 days OR next 60 days (eliminates far-future releases)
- Only shows ETB, Booster Box, and Booster products (filters out bundles, cases, etc.)
- **`kartoteka_web/services/set_icons.py`**: Downloads set icons from `api.pokemontcg.io` (currently disabled in `server.py` lifespan due to API issues)

### Utilities
- **`kartoteka_web/utils/text.py`**: Text normalization and card number sanitization
- **`kartoteka_web/utils/sets.py`**: Set code cleaning, slugification, and metadata
- **`kartoteka_web/utils/images.py`**: Card image directory management and URL generation

### Frontend
- Templates in `kartoteka_web/templates/` (Jinja2)
- Static assets in `kartoteka_web/static/` (CSS, JS, service worker)
- Icons served from `icon/` directory
- Card images served from configured `CARD_IMAGE_DIR` (see `images.py`)
- **Personalized home page**: For logged-in users, home page (`/`) displays:
  - Collection summary (total cards, unique cards, total value)
  - Recently added cards (last 5)
  - Price changes in user's collection (top 5 by % change)
  - Latest products from API
- **Non-logged-in home page**: Shows marketing content, login/register buttons, and latest products

## Code Style Guidelines

### Imports
- Use `from __future__ import annotations` at the top of every Python file
- Group imports: stdlib, third-party, local (separated by blank lines)
- Relative imports for local modules: `from .. import models`, `from ..auth import get_current_user`
- Import modules for utils: `from ..utils import images as image_utils, text, sets as set_utils`

### Type Annotations
- Always use type hints for function parameters and return values
- Use `Optional[T]` from `typing` for nullable types
- Use union types with `|` for modern hints: `str | None`, `dict[str, Any]`
- SQLModel fields use `Optional[T] = Field(default=None)` for nullable columns

### Naming
- Functions/variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private/internal helpers: prefix with `_`

### Error Handling
- Use FastAPI's `HTTPException` for API errors: `raise HTTPException(status_code=404, detail="Nie znaleziono karty.")`
- Use try/except with logging for external API calls: `logger.warning("Failed to fetch...")`
- Return `None` for not-found cases in helper functions, handle in caller
- For defensive code, use `# pragma: no cover` comment on except blocks

### Code Organization
- Keep route handlers thin, delegate logic to helper functions
- Helper functions should be private (prefix `_`) unless reused across modules
- Use context managers for database sessions: `with session_scope() as session:`
- Delete unused parameters explicitly: `del current_user  # Only used to enforce authentication`

### Testing
- Test files mirror source structure: `tests/api/test_cards.py` tests `kartoteka_web/routes/cards.py`
- Use descriptive test names: `test_collection_crud_lifecycle`
- Use `monkeypatch` for mocking external dependencies
- Use `api_client` fixture from `conftest.py` for integration tests
- Assert with clear messages: `assert response.status_code == 200, response.text`

## Environment Configuration

Copy `.env.example` to `.env` and configure:
- `RAPIDAPI_KEY` / `RAPIDAPI_HOST`: Required for card catalog sync and fallback search
- `KARTOTEKA_DATABASE_URL`: Database connection string (default: `sqlite:///./kartoteka.db`)
- `KARTOTEKA_SECRET_KEY`: JWT signing key (change in production!)
- `NGROK_AUTHTOKEN`: For ngrok tunnel in Docker Compose setup

## Known Issues

### Set Icons Currently Disabled
The `set_icons.ensure_set_icons` call in `server.py` lifespan is commented out due to `api.pokemontcg.io` being unresponsive. Uncomment when API is available.

### Card Number Parsing
The search query parser in `cards.py` uses regex to extract card numbers (e.g., "25/100") from natural language queries. It handles various formats but may need adjustment for edge cases.

### Collection Value Calculation
**IMPORTANT**: Collection value is calculated as the **sum of prices without multiplying by quantity**.
- Each `CollectionEntry` represents a unique card/product in the collection
- When calculating `total_value`, sum `card.price` or `product.price` directly
- DO NOT multiply by `entry.quantity` - this is intentional per business requirements
- Example: If user has 3x "Pikachu" at 10 PLN each, the value is 10 PLN (not 30 PLN)
- See `kartoteka_web/routes/cards.py:1221-1233` for reference implementation

## Data Flow

### Card Search Flow
1. User enters query → `/cards/search` endpoint
2. Parse query for card number patterns (`CARD_NUMBER_PATTERN`)
3. Query `CardRecord` table with normalized text and number filters
4. If local catalog misses, fall back to RapidAPI via `tcg_api.py`
5. Return paginated results with set icons and pricing

### Collection Management Flow
1. User adds card → `/cards/collection` POST endpoint
2. Create or retrieve `Card` record from payload
3. Create `CollectionEntry` linking `User` and `Card` with quantity/metadata
4. Support for both cards and sealed products via polymorphic `card_id` / `product_id`

### Authentication Flow
1. User submits credentials → `/users/login` endpoint
2. Validate via `authenticate_user()` in `auth.py`
3. Generate JWT with `create_access_token()`
4. Frontend stores token, includes in `Authorization: Bearer <token>` header
5. Protected routes use `get_current_user()` dependency

### Home Page Data Flow (Logged-in Users)
1. User visits `/` → `home_page()` in `server.py`
2. Resolve user from token via `_resolve_request_user()`
3. If authenticated, fetch collection data:
   - Query all `CollectionEntry` records for user
   - Calculate stats: `total_cards` (sum of quantities), `unique_cards` (count), `total_value` (sum of prices **without** quantity multiplication)
   - Get last 5 recently added entries (ordered by `id DESC`)
   - Calculate price changes: compare `price` vs `price_7d_average` for each card/product
   - Sort by absolute change percentage, take top 5
4. Fetch latest products from RapidAPI (filtered to last 90 days + next 60 days)
5. Render template with collection stats, recently added, price changes, and products
6. Template shows different sections based on whether user is logged in
