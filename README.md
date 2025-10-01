![Kartoteka web banner](banner22.png)

# Kartoteka Web Collection App

## Overview
Kartoteka is a FastAPI-powered web collection app for managing a private Pokémon card library end to end. The service delivers authenticated dashboards, responsive forms and portfolio views backed by a local SQLModel database so collectors can browse, audit and enrich their inventory from any modern browser.

## Feature Highlights
- **Secure authentication flow** with dedicated login, registration and settings views backed by OAuth2 token handling and session-aware templates.
- **Collection management APIs** for searching, adding and updating cards, including intelligent card-number parsing and set resolution to help locate entries quickly.
- **Rich dashboards** for monitoring the collection, per-card details and overall portfolio value directly from the built-in web interface.
- **Hardened delivery** featuring strict security headers, static asset hosting and automatic database initialisation during application startup.

## Tech Stack
- **Backend:** FastAPI with SQLModel for async HTTP endpoints and persistence.
- **Database:** SQLite by default, configurable through `KARTOTEKA_DATABASE_URL` for other SQLAlchemy-compatible engines.
- **Templates & Static Assets:** Jinja2 templates served alongside modern JavaScript, CSS and service worker assets under `kartoteka_web/static`.
- **Utilities:** Reusable modules for image management, set metadata and text sanitisation ensure consistent presentation and speedy lookups.

## Getting Started

### Prerequisites
- Python 3.9 or newer and `pip` for installing backend dependencies.
- Optional: a modern Node.js toolchain if you plan to rebuild the front-end assets before publishing them to `kartoteka_web/static`.

### Installation
1. Clone the repository and move into the project directory.
2. Create a virtual environment.
3. Install the backend dependencies:

   ```bash
   pip install -r requirements.txt
   ```

The application initialises its SQL database automatically on first launch. Set `KARTOTEKA_DATABASE_URL` if you prefer a different location or engine.

### Running the FastAPI Server
Start the API and server-rendered frontend with Uvicorn:

```bash
uvicorn server:app --reload
```

The development server defaults to `http://127.0.0.1:8000/` and serves the dashboard, collection and portfolio pages alongside the JSON API.

### Developing the Frontend
The shipped UI is compiled into `kartoteka_web/static`. When iterating on the new branding or implementing a custom JavaScript frontend:

1. Build your modern frontend (for example with Vite, Next.js or another SPA framework) against the FastAPI endpoints.
2. Output the production build into `kartoteka_web/static` so the server can deliver the refreshed assets.
3. Reload the Uvicorn process to pick up the new files.

## Branding Assets
![Kartoteka interface preview](LOGO_male.png)

Updated badges, favicons and screenshots should reflect the latest design language and live in the repository root for convenient reuse across documentation and the deployed UI.
