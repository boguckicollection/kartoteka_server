![Kartoteka banner](banner22.png)
# Kartoteka

## Overview
Kartoteka is a FastAPI service and JavaScript dashboard for organising a private Pokémon card collection. The backend exposes
JWT-secured endpoints for synchronising cards, storage locations and valuations with the hosted single-page application.

## Python Compatibility
Kartoteka supports Python 3.9 through 3.13. The default requirements use `Pillow>=10.4`, which ships pre-built wheels for Python
3.13.

If you must stay on an older Python release that cannot install Pillow 10.4 or later, pin `Pillow<10.4` in `requirements.txt` and
use a compatible Python version (for example, Python 3.12).

## Running the web API and dashboard

Start the FastAPI service with uvicorn:

```bash
uvicorn server:app --reload
```

### Pricing API configuration

Price lookups require a RapidAPI host and key. Provide them either via shell variables (`export RAPIDAPI_HOST=…`,
`export RAPIDAPI_KEY=…`) or by creating a `.env` file in the project root. The repository ships with a `.env.example`; copy it and
fill in the desired values:

```bash
cp .env.example .env
```

The backend loads this file automatically on startup, so the credentials only need to be set once. Card search and set
synchronisation use the official Pokémon TCG API. Place the corresponding `POKEMONTCG_API_KEY` in your local `.env` file (or export
it in the shell) and keep it outside of version control.

By default the API stores data in `kartoteka.db` (SQLite). Override the location with the `KARTOTEKA_DATABASE_URL` environment
variable if you prefer a different database path. Background tasks automatically refresh card prices at regular intervals using the
shared pricing module.

The web UI is available at `http://localhost:8000/` and provides pages for logging in, registering new users, managing the
collection and monitoring the portfolio value. JavaScript widgets communicate with the REST API to perform CRUD operations on stored
cards.

### Card detail dashboard

The card-detail view exposes interactive price history charts with range toggles for the last day, week, month or the entire
dataset ("Całość"). When a shorter window would be empty the UI automatically highlights the full-range option so the chart stays
populated whenever historical data exists.

## Card Identifier Format and CSV Export
Cards are identified with the pattern `PKM-<SET>-<NR>-<VARIANT>`:

* `SET` – the set code, e.g. `BS` for Base Set.
* `NR` – the card number within that set.
* `VARIANT` – optional variant flag such as `H` (holofoil) or `R` (reverse).

Examples:

* `PKM-BS-1-H`
* `PKM-BS-1-R`

Exporting creates `collection_export.csv`, a collection-focused CSV containing fields such as `language`, `condition`,
`variant`, `estimated_value` and the assigned `warehouse_code`. Entries are keyed by product code so the newest valuation replaces
older data.
