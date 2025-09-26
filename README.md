![Kartoteka banner](banner22.png)
# Kartoteka

## Overview
Kartoteka is a lightweight Tkinter app for organising a private Pokémon card collection. The interface helps catalogue scans,
track storage locations and record personal valuations without relying on shop integrations.

## Python Compatibility
Kartoteka supports Python 3.9 through 3.13. The default requirements use `Pillow>=10.4`, which ships pre-built wheels for Python 3.13.

If you must stay on an older Python release that cannot install Pillow 10.4 or later, pin `Pillow<10.4` in `requirements.txt` and use a compatible Python version (for example, Python 3.12).

## Running the App
With dependencies installed, launch the interface:

```bash
python main.py
```

## Web API and dashboard

Kartoteka now exposes a FastAPI service with JWT authentication, REST
endpoints and a lightweight dashboard for browsing the collection in a web
browser.  To start the server locally use uvicorn:

```bash
uvicorn server:app --reload
```

### RapidAPI configuration

Price lookups use the same configuration as the desktop app.  Provide a
RapidAPI host and key either via shell variables (`export RAPIDAPI_HOST=…`,
`export RAPIDAPI_KEY=…`) or by creating a `.env` file in the project root.
The repository ships with a `.env.example`; copy it and fill in the desired
values:

```bash
cp .env.example .env
```

Both the Tkinter UI (`python main.py`) and the web server (`uvicorn
server:app --reload`) load this file automatically on startup, so the
credentials only need to be set once.

By default the API stores data in `kartoteka.db` (SQLite).  Override the
location with the `KARTOTEKA_DATABASE_URL` environment variable if you prefer
a different database path.  Background tasks automatically refresh card prices
at regular intervals using the shared pricing module.

The web UI is available at `http://localhost:8000/` and provides pages for
logging in, registering new users, managing the collection and monitoring the
portfolio value.  JavaScript widgets communicate with the REST API to perform
CRUD operations on stored cards.

### Card detail dashboard

The card-detail view exposes interactive price history charts with range
toggles for the last day, week, month or the entire dataset ("Całość").  When a
shorter window would be empty the UI automatically highlights the full-range
option so the chart stays populated whenever historical data exists.

## Set validation

OpenAI responses normally validate set and era names against a built-in list.
To allow unrecognised values and rely on internal mapping instead, disable
strict validation:

```bash
STRICT_SET_VALIDATION=0 python main.py
```


## Card Identifier Format and CSV Export
Cards are identified with the pattern `PKM-<SET>-<NR>-<VARIANT>`:

* `SET` – the set code, e.g. `BS` for Base Set.
* `NR` – the card number within that set.
* `VARIANT` – optional variant flag such as `H` (holofoil) or `R` (reverse).

Examples:

* `PKM-BS-1-H`
* `PKM-BS-1-R`

Exporting creates `collection_export.csv`, a collection-focused CSV containing fields such as `language`, `condition`,
`variant`, `estimated_value` and the assigned `warehouse_code`. Entries are keyed by product code so the newest valuation
replaces older data.

## Storage configuration

Box layout and capacities are centralised in `kartoteka/storage_config.py`.
The module defines shared constants such as the number of regular boxes
(`BOX_COUNT`), column counts (`STANDARD_BOX_COLUMNS`), per-column capacity
(`BOX_COLUMN_CAPACITY`), total capacity of each box (`BOX_CAPACITY`), and
details for the overflow box (`SPECIAL_BOX_NUMBER`, `SPECIAL_BOX_CAPACITY`).
Both `storage.py` and `ui.py` import these values so any changes to the
physical warehouse setup only need to be made in a single place.
