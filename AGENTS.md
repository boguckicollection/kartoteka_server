# Agent Guidelines for Kartoteka Server

## Commands
- **Run server**: `uvicorn server:app --reload` or `python server.py`
- **Run all tests**: `pytest` or `python -m pytest`
- **Run single test**: `pytest tests/api/test_cards.py::test_collection_crud_lifecycle`
- **Run tests with verbose**: `pytest -v`
- **Sync catalog**: `./sync_catalog.py --verbose` or `./sync_catalog.py --sets sv01 --limit 25`

## Code Style

### Imports
- Use `from __future__ import annotations` at the top of every Python file
- Group imports: stdlib, third-party, local (separated by blank lines)
- Use relative imports for local modules: `from .. import models`, `from ..auth import get_current_user`
- Import modules, not individual functions for common utils: `from ..utils import images as image_utils, text, sets as set_utils`
- Import specific items from FastAPI/SQLModel: `from fastapi import APIRouter, Depends, HTTPException, status`

### Types & Annotations
- Always use type hints for function parameters and return values
- Use `Optional[T]` from `typing` for nullable types (e.g., `Optional[int]`, `Optional[str]`)
- Use union types with `|` for modern type hints: `str | None`, `dict[str, Any]`
- SQLModel fields use `Optional[T] = Field(default=None)` pattern for nullable columns

### Naming
- Functions/variables: `snake_case` (e.g., `search_cards_endpoint`, `name_value`, `set_code_clean`)
- Classes: `PascalCase` (e.g., `User`, `CardRecord`, `CollectionEntry`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `RAPIDAPI_KEY`, `MAX_SEARCH_RESULTS`, `SET_ICON_URL_BASE`)
- Private/internal helpers: prefix with `_` (e.g., `_normalize_lower`, `_apply_card_images`)

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
- Use descriptive test names: `test_collection_crud_lifecycle`, `test_card_search_pagination_clamping`
- Use `monkeypatch` for mocking external dependencies
- Use `api_client` fixture from `conftest.py` for integration tests
- Assert with clear messages: `assert response.status_code == 200, response.text`
