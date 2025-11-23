# Application Context: Kartoteka Server

This project is a web application designed for collecting, searching, browsing, and managing the value of a Pokémon card collection.

## Recent Changes and Current Status:

### 1. Collection Value History Chart (Completed)
**Problem:** The collection value history chart was showing a flat line, and the UI controls were confusing.
**Solution:**
    -   **Backend:** Refactored the `_fetch_collection_history` function in `kartoteka_web/routes/cards.py` to correctly and efficiently calculate daily collection values. This involved fetching the complete price history for all cards and building the daily totals chronologically.
    -   **Database:** Corrected an `AttributeError: card_id` in `kartoteka_web/services/crud.py` by using the correct `card_record_id` field.
    -   **Frontend:**
        -   Fixed a `TypeError` related to timezone-naive and -aware datetime comparisons in `app.js`.
        -   Added a checkbox to toggle the visibility of the "purchase cost" line on the chart.
        -   Implemented a date range selector (90D, 60D, 30D, 7D) to allow users to view different time periods.
        -   Simplified the UI by removing unnecessary buttons (`toggle-history`, `refresh-collection`, `refresh-prices`) and making the historical chart view the default.
        -   Corrected the chart's x-axis configuration to properly handle time-series data, fixing date display issues.
**Status:** The collection value chart is now fully functional and interactive.

### 2. Single Card Price History Chart (Next Steps)
**Goal:** Replace the placeholder chart on the single card detail page (`card_detail.html`) with a fully functional Chart.js chart, similar to the one implemented for the collection view.
**Plan:**
1.  **UI Update (`card_detail.html`):**
    *   Standardize the date range selector buttons to match the collection chart (90D, 60D, 30D, 7D).
2.  **JavaScript Implementation (`app.js`):**
    *   Refactor the existing `createPriceHistoryModule` to initialize a new Chart.js instance on the `#card-price-chart` canvas.
    *   Configure the chart with a time scale x-axis and appropriate tooltips.
    *   Use the `price_history` data already fetched with the card details to populate the chart.
    *   Implement the date range filtering logic based on the selected button.
    *   Ensure the styling is consistent with the collection chart.

### 3. Application Startup Issue (Resolved with Workaround)
**Problem:** The application initially failed to start due to the `lifespan` function hanging during the execution of `set_icons.ensure_set_icons`. This function attempts to download Pokémon TCG set icons from an external API (`api.pokemontcg.io`). The API was found to be unresponsive, causing the startup process to block indefinitely.
**Workaround:** The call to `await anyio.to_thread.run_sync(set_icons.ensure_set_icons)` in `server.py` has been commented out.
**Impact:** The application now starts successfully, but the set icons are not downloaded or displayed. This is a temporary measure. The line can be uncommented if the external API becomes responsive again.

### 4. Frontend Styling and Script Loading Issues (Resolved)
**Problem:** The frontend experienced issues with loading stylesheets, scripts, images, and the web app manifest, resulting in browser console errors related to Content Security Policy (CSP) and mixed content. This occurred because the application, when served via ngrok (HTTPS), was generating HTTP URLs for its static assets.
**Solution:**
    -   **Mixed Content:** `uvicorn.middleware.proxy_headers.ProxyHeadersMiddleware` was added to `server.py` to correctly handle `X-Forwarded-Proto` headers, making FastAPI aware that it's running behind an HTTPS proxy.
    -   **Content Security Policy:** The `Content-Security-Policy` in `server.py` was updated to include `manifest-src 'self'` to allow the web app manifest to load correctly.
**Status:** Frontend assets now load correctly, and CSP violations are resolved.

### 5. ngrok Authentication (Resolved)
**Problem:** The `ngrok` service failed to start due to a missing `NGROK_AUTHTOKEN`.
**Solution:** The user provided a correct `.env` file containing the `NGROK_AUTHTOKEN`.
**Status:** The ngrok tunnel is now established and working correctly.
