(() => {
  const TOKEN_KEY = "kartoteka_token";
  let collectionCache = [];
  let currentUser = null;

  const storage = (() => {
    try {
      const { localStorage } = window;
      localStorage.getItem("__kartoteka_test__");
      return localStorage;
    } catch (error) {
      console.warn("Local storage unavailable", error);
      return null;
    }
  })();

  const THEME_KEY = "kartoteka_theme";
  const themeMediaQuery =
    typeof window.matchMedia === "function"
      ? window.matchMedia("(prefers-color-scheme: dark)")
      : null;
  let currentThemePreference = "auto";

  const readStoredTheme = () => {
    if (!storage) return null;
    try {
      return storage.getItem(THEME_KEY);
    } catch (error) {
      console.warn("Unable to read theme preference", error);
      return null;
    }
  };

  const persistThemePreference = (preference) => {
    if (!storage) return;
    try {
      if (preference === "auto") {
        storage.removeItem(THEME_KEY);
      } else {
        storage.setItem(THEME_KEY, preference);
      }
    } catch (error) {
      console.warn("Unable to persist theme preference", error);
    }
  };

  const resolveEffectiveTheme = (preference) => {
    if (preference === "dark" || preference === "light") {
      return preference;
    }
    if (themeMediaQuery && typeof themeMediaQuery.matches === "boolean") {
      return themeMediaQuery.matches ? "dark" : "light";
    }
    return "light";
  };

  const updateThemeMetaTag = () => {
    const meta = document.querySelector("meta[data-theme-color]");
    const root = document.body || document.documentElement;
    if (!meta || !root) return;
    const styles = getComputedStyle(root);
    const fallback = resolveEffectiveTheme(currentThemePreference) === "dark"
      ? "#0b1220"
      : "#ffffff";
    const surface =
      styles.getPropertyValue("--color-surface").trim() ||
      styles.getPropertyValue("--color-background").trim() ||
      fallback;
    meta.setAttribute("content", surface || fallback);
  };

  const updateThemeToggleDisplay = (preference) => {
    const toggle = document.querySelector("[data-theme-toggle]");
    if (!toggle) return;
    const icon = toggle.querySelector("[data-theme-toggle-icon]");
    const effective = resolveEffectiveTheme(preference);
    let label = "Motyw systemowy";
    let iconSymbol = "🌓";
    if (preference === "dark") {
      label = "Motyw ciemny";
      iconSymbol = "🌙";
    } else if (preference === "light") {
      label = "Motyw jasny";
      iconSymbol = "☀️";
    } else {
      label =
        effective === "dark" ? "Motyw systemowy (ciemny)" : "Motyw systemowy (jasny)";
      iconSymbol = "🌓";
    }
    toggle.dataset.mode = preference;
    toggle.setAttribute("aria-label", `${label}. Kliknij, aby zmienić motyw.`);
    toggle.setAttribute("title", `${label} – kliknij, aby zmienić motyw`);
    if (icon) {
      icon.textContent = iconSymbol;
    }
  };

  const applyThemePreference = (preference, options = {}) => {
    const target = document.body;
    if (!target) return;
    const normalized = preference === "dark" || preference === "light" ? preference : "auto";
    target.setAttribute("data-theme", normalized);
    if (options.persist !== false) {
      persistThemePreference(normalized);
    }
    currentThemePreference = normalized;
    updateThemeToggleDisplay(normalized);
    updateThemeMetaTag();
  };

  const initializeTheme = () => {
    const stored = readStoredTheme();
    const initial = stored === "dark" || stored === "light" ? stored : "auto";
    applyThemePreference(initial, { persist: false });

    const toggle = document.querySelector("[data-theme-toggle]");
    if (toggle) {
      toggle.addEventListener("click", () => {
        const next =
          currentThemePreference === "light"
            ? "dark"
            : currentThemePreference === "dark"
              ? "auto"
              : "light";
        applyThemePreference(next);
      });
    }

    if (themeMediaQuery) {
      const handleChange = () => {
        if (currentThemePreference === "auto") {
          applyThemePreference("auto", { persist: false });
        }
      };
      if (typeof themeMediaQuery.addEventListener === "function") {
        themeMediaQuery.addEventListener("change", handleChange);
      } else if (typeof themeMediaQuery.addListener === "function") {
        themeMediaQuery.addListener(handleChange);
      }
      handleChange();
    }
  };

  const CARD_VIEW_STORAGE_KEY = "kartoteka_card_view_mode";
  const CARD_SORT_STORAGE_KEY = "kartoteka_card_sort_order";
  const CARD_SORT_OPTIONS = [
    "relevance",
    "name-asc",
    "name-desc",
    "set-asc",
    "number-asc",
    "number-desc",
    "price-asc",
    "price-desc",
  ];
  const CARD_SORT_ALLOWED = new Set(CARD_SORT_OPTIONS);
  const DEFAULT_SHOP_URL = "https://kartoteka.shop/pl/c/Karty-Pokemon/38";
  let currentCardViewMode = "grid";
  let currentCardSortOrder = "relevance";

  const readStoredCardViewMode = () => {
    if (!storage) return null;
    try {
      const value = storage.getItem(CARD_VIEW_STORAGE_KEY);
      return value === "grid" || value === "list" ? value : null;
    } catch (error) {
      console.warn("Unable to read card view mode", error);
      return null;
    }
  };

  const persistCardViewMode = (mode) => {
    if (!storage) return;
    try {
      storage.setItem(CARD_VIEW_STORAGE_KEY, mode);
    } catch (error) {
      console.warn("Unable to persist card view mode", error);
    }
  };

  const readStoredCardSortOrder = () => {
    if (!storage) return null;
    try {
      const value = storage.getItem(CARD_SORT_STORAGE_KEY);
      return CARD_SORT_ALLOWED.has(value) ? value : null;
    } catch (error) {
      console.warn("Unable to read card sort order", error);
      return null;
    }
  };

  const persistCardSortOrder = (order) => {
    if (!storage) return;
    try {
      storage.setItem(CARD_SORT_STORAGE_KEY, order);
    } catch (error) {
      console.warn("Unable to persist card sort order", error);
    }
  };

  const applyCardResultsViewMode = (mode) => {
    const container = document.getElementById("card-search-results");
    if (!container) return;
    const normalized = mode === "grid" ? "grid" : "list";
    container.classList.toggle("card-search-results--grid", normalized === "grid");
    container.classList.toggle("card-search-results--list", normalized === "list");
    container.dataset.viewMode = normalized;
    currentCardViewMode = normalized;
  };

  const cardResultsCollator =
    typeof Intl !== "undefined" && typeof Intl.Collator === "function"
      ? new Intl.Collator("pl", { numeric: true, sensitivity: "base" })
      : null;

  const cardPriceFormatter =
    typeof Intl !== "undefined" && typeof Intl.NumberFormat === "function"
      ? new Intl.NumberFormat("pl-PL", {
          style: "currency",
          currency: "PLN",
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        })
      : null;

  const normalizePriceInput = (value) => {
    if (typeof value === "number" && Number.isFinite(value)) {
      return Number(value);
    }
    if (typeof value === "string") {
      const normalized = value.replace(/,/g, ".").trim();
      if (!normalized) return null;
      const parsed = Number.parseFloat(normalized);
      return Number.isFinite(parsed) ? parsed : null;
    }
    return null;
  };

  const getCardPriceValue = (item) => {
    if (!item) return null;
    const average = normalizePriceInput(item.price_7d_average);
    if (average !== null) {
      return average;
    }
    return normalizePriceInput(item.price);
  };

  const formatCardPrice = (price) => {
    if (!Number.isFinite(price)) return "";
    if (cardPriceFormatter) {
      try {
        return cardPriceFormatter.format(price);
      } catch (error) {
        console.debug("Unable to format card price", error);
      }
    }
    return `${price.toFixed(2)} zł`;
  };

  const stableSort = (items, compare) =>
    items
      .map((item, index) => ({ item, index }))
      .sort((a, b) => {
        const result = compare(a.item, b.item);
        if (result !== 0) return result;
        return a.index - b.index;
      })
      .map((entry) => entry.item);

  const compareText = (a = "", b = "") => {
    if (cardResultsCollator) {
      return cardResultsCollator.compare(a, b);
    }
    return a.localeCompare(b);
  };

  const comparePriceAsc = (a, b) => {
    const priceA = getCardPriceValue(a);
    const priceB = getCardPriceValue(b);
    if (priceA === null && priceB === null) return 0;
    if (priceA === null) return 1;
    if (priceB === null) return -1;
    if (priceA < priceB) return -1;
    if (priceA > priceB) return 1;
    return 0;
  };

  const comparePriceDesc = (a, b) => {
    const priceA = getCardPriceValue(a);
    const priceB = getCardPriceValue(b);
    if (priceA === null && priceB === null) return 0;
    if (priceA === null) return 1;
    if (priceB === null) return -1;
    if (priceA > priceB) return -1;
    if (priceA < priceB) return 1;
    return 0;
  };

  const sortCardSearchItems = (items = [], order = "relevance") => {
    const list = Array.isArray(items) ? [...items] : [];
    if (list.length <= 1) return list;
    switch (order) {
      case "name-asc":
        return stableSort(list, (a, b) => compareText(a.name || "", b.name || ""));
      case "name-desc":
        return stableSort(list, (a, b) => compareText(b.name || "", a.name || ""));
      case "set-asc":
        return stableSort(list, (a, b) => compareText(a.set_name || "", b.set_name || ""));
      case "number-asc":
        return stableSort(list, (a, b) =>
          compareText(
            a.number_display || a.number || "",
            b.number_display || b.number || "",
          ),
        );
      case "number-desc":
        return stableSort(list, (a, b) =>
          compareText(
            b.number_display || b.number || "",
            a.number_display || a.number || "",
          ),
        );
      case "price-asc":
        return stableSort(list, comparePriceAsc);
      case "price-desc":
        return stableSort(list, comparePriceDesc);
      case "relevance":
      default:
        return list;
    }
  };

  const mapSortOrderToRequest = (order) => {
    switch (order) {
      case "name-asc":
        return { sort: "name", order: "asc" };
      case "name-desc":
        return { sort: "name", order: "desc" };
      case "set-asc":
        return { sort: "set.name", order: "asc" };
      case "number-asc":
        return { sort: "number", order: "asc" };
      case "number-desc":
        return { sort: "number", order: "desc" };
      case "price-asc":
        return { sort: "price", order: "asc" };
      case "price-desc":
        return { sort: "price", order: "desc" };
      case "relevance":
      default:
        return { sort: null, order: null };
    }
  };

  const getToken = () => (storage ? storage.getItem(TOKEN_KEY) : null);
  const setToken = (token) => {
    if (!storage) return;
    try {
      storage.setItem(TOKEN_KEY, token);
    } catch (error) {
      console.warn("Unable to persist token", error);
    }
  };
  const clearToken = () => {
    if (!storage) return;
    try {
      storage.removeItem(TOKEN_KEY);
    } catch (error) {
      console.warn("Unable to remove token", error);
    }
  };

  const escapeHtml = (value) =>
    String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");

  const formToJSON = (form) => {
    const data = new FormData(form);
    const result = {};
    for (const [key, value] of data.entries()) {
      if (Object.prototype.hasOwnProperty.call(result, key)) {
        const existing = result[key];
        if (Array.isArray(existing)) {
          existing.push(value);
        } else {
          result[key] = [existing, value];
        }
      } else {
        result[key] = value;
      }
    }
    return result;
  };

  const ALERT_AUTOHIDE_DELAY = 3600;
  const ALERT_TRANSITION_DURATION = 220;
  const alertTimers = new WeakMap();
  const scheduleFrame =
    typeof window !== "undefined" && typeof window.requestAnimationFrame === "function"
      ? window.requestAnimationFrame.bind(window)
      : (callback) => setTimeout(callback, 16);

  const clearAlertTimer = (element) => {
    const pending = alertTimers.get(element);
    if (pending) {
      clearTimeout(pending);
      alertTimers.delete(element);
    }
  };

  const showAlert = (element, message, variant = "info") => {
    if (!element) return;
    clearAlertTimer(element);
    const isFloating = element.classList.contains("alert--floating");
    if (!message) {
      element.classList.remove("alert--visible");
      delete element.dataset.variant;
      if (!isFloating) {
        element.hidden = true;
        element.textContent = "";
        return;
      }
      const timer = setTimeout(() => {
        element.hidden = true;
        element.textContent = "";
        alertTimers.delete(element);
      }, ALERT_TRANSITION_DURATION);
      alertTimers.set(element, timer);
      return;
    }
    element.textContent = message;
    element.dataset.variant = variant;
    element.hidden = false;
    scheduleFrame(() => {
      element.classList.add("alert--visible");
    });
    if (variant === "success" && isFloating) {
      const timer = setTimeout(() => {
        showAlert(element, "");
      }, ALERT_AUTOHIDE_DELAY);
      alertTimers.set(element, timer);
    }
  };

  const updateUserBadge = (user) => {
    const username = user && user.username ? String(user.username).trim() : "";
    const label = document.querySelector("[data-username-display]");
    if (label) {
      label.textContent = username || "Gość";
    }
    const loginButton = document.getElementById("login-button");
    if (loginButton) {
      loginButton.hidden = Boolean(username);
    }
    const logoutButton = document.getElementById("logout-button");
    if (logoutButton) {
      logoutButton.hidden = !username;
    }
  };

  const apiFetch = async (path, options = {}) => {
    const init = { ...options };
    const headers = { Accept: "application/json", ...(options.headers || {}) };
    if (init.body && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }
    const token = getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    init.headers = headers;
    const response = await fetch(path, init);
    let payload = null;
    if (response.status !== 204) {
      try {
        payload = await response.json();
      } catch (error) {
        payload = null;
      }
    }
    if (!response.ok) {
      if (response.status === 401) {
        clearToken();
      }
      const error = new Error((payload && payload.detail) || "Wystąpił błąd.");
      error.status = response.status;
      throw error;
    }
    return payload;
  };

  const fetchCurrentUser = async () => {
    const token = getToken();
    if (!token) {
      currentUser = null;
      updateUserBadge(null);
      return null;
    }
    try {
      const user = await apiFetch("/users/me");
      currentUser = user;
      updateUserBadge(user);
      return user;
    } catch (error) {
      currentUser = null;
      updateUserBadge(null);
      if (error.status === 401) {
        console.warn("Authentication expired");
      }
      return null;
    }
  };

  const setupNavigation = () => {
    const nav = document.querySelector("[data-nav]");
    const toggle = document.querySelector("[data-nav-toggle]");
    if (nav && toggle) {
      toggle.addEventListener("click", () => {
        const expanded = toggle.getAttribute("aria-expanded") === "true";
        const next = !expanded;
        toggle.setAttribute("aria-expanded", String(next));
        nav.dataset.open = String(next);
      });
      document.addEventListener("click", (event) => {
        if (!nav.contains(event.target) && !toggle.contains(event.target)) {
          nav.dataset.open = "false";
          toggle.setAttribute("aria-expanded", "false");
        }
      });
    }

    const logoutButton = document.querySelector("[data-logout]");
    if (logoutButton) {
      logoutButton.addEventListener("click", () => {
        clearToken();
        currentUser = null;
        updateUserBadge(null);
        window.location.href = "/login";
      });
    }
  };

  const setupAuthForms = () => {
    const loginForm = document.getElementById("login-form");
    if (loginForm) {
      const alertBox = document.getElementById("login-alert");
      loginForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const payload = formToJSON(loginForm);
        showAlert(alertBox, "");
        try {
          const data = await apiFetch("/users/login", {
            method: "POST",
            body: JSON.stringify(payload),
          });
          setToken(data.access_token);
          await fetchCurrentUser();
          window.location.href = "/collection";
        } catch (error) {
          showAlert(alertBox, error.message || "Nie udało się zalogować.", "error");
        }
      });
    }

    const registerForm = document.getElementById("register-form");
    if (registerForm) {
      const alertBox = document.getElementById("register-alert");
      registerForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const payload = formToJSON(registerForm);
        showAlert(alertBox, "");
        try {
          await apiFetch("/users/register", {
            method: "POST",
            body: JSON.stringify(payload),
          });
          showAlert(
            alertBox,
            "Konto utworzone. Możesz się zalogować.",
            "success",
          );
          registerForm.reset();
        } catch (error) {
          showAlert(alertBox, error.message || "Nie udało się utworzyć konta.", "error");
        }
      });
    }
  };

  const buildCollectionRow = (entry) => {
    const tr = document.createElement("tr");
    tr.dataset.entryId = String(entry.id);
    const card = entry.card || {};
    const purchase =
      typeof entry.purchase_price === "number"
        ? entry.purchase_price.toFixed(2)
        : entry.purchase_price || "";
    tr.innerHTML = `
      <td data-label="Karta">
        <strong>${escapeHtml(card.name || "Nieznana karta")}</strong>
      </td>
      <td data-label="Set">${escapeHtml(card.set_name || "–")}</td>
      <td data-label="Numer">${escapeHtml(card.number || "–")}</td>
      <td data-label="Ilość">
        <input type="number" min="0" step="1" value="${entry.quantity}" data-field="quantity" />
      </td>
      <td data-label="Reverse" class="table-checkbox">
        <input type="checkbox" data-field="is_reverse" ${entry.is_reverse ? "checked" : ""} />
      </td>
      <td data-label="Holo" class="table-checkbox">
        <input type="checkbox" data-field="is_holo" ${entry.is_holo ? "checked" : ""} />
      </td>
      <td data-label="Cena zakupu">
        <input
          type="number"
          min="0"
          step="0.01"
          inputmode="decimal"
          placeholder="0.00"
          value="${escapeHtml(purchase)}"
          data-field="purchase_price"
        />
      </td>
      <td data-label="Akcje" class="table-actions">
        <button type="button" class="button inline" data-action="save" data-id="${entry.id}">Zapisz</button>
        <button type="button" class="button inline danger" data-action="delete" data-id="${entry.id}">Usuń</button>
      </td>
    `;
    return tr;
  };

  const renderCollection = (entries) => {
    const body = document.getElementById("collection-table");
    const emptyMessage = document.getElementById("collection-empty");
    if (!body) return;
    body.innerHTML = "";
    if (!entries.length) {
      if (emptyMessage) emptyMessage.hidden = false;
      return;
    }
    if (emptyMessage) emptyMessage.hidden = true;
    for (const entry of entries) {
      body.appendChild(buildCollectionRow(entry));
    }
  };

  const renderPortfolio = (entries) => {
    const container = document.getElementById("portfolio-cards");
    const emptyMessage = document.getElementById("portfolio-empty");
    if (!container) return;
    container.innerHTML = "";
    if (!entries.length) {
      if (emptyMessage) emptyMessage.hidden = false;
      return;
    }
    if (emptyMessage) emptyMessage.hidden = true;
    for (const entry of entries) {
      const card = entry.card || {};
      const item = document.createElement("article");
      item.className = "portfolio-card";
      const purchase =
        typeof entry.purchase_price === "number"
          ? `${entry.purchase_price.toFixed(2)} PLN`
          : entry.purchase_price
            ? `${entry.purchase_price} PLN`
            : "–";
      item.innerHTML = `
        <header>
          <h3>${escapeHtml(card.name || "Nieznana karta")}</h3>
          <p>${escapeHtml(card.set_name || "")}</p>
        </header>
        <dl>
          <div>
            <dt>Numer</dt>
            <dd>${escapeHtml(card.number || "–")}</dd>
          </div>
          <div>
            <dt>Ilość</dt>
            <dd>${entry.quantity}</dd>
          </div>
          <div>
            <dt>Reverse</dt>
            <dd>${entry.is_reverse ? "Tak" : "Nie"}</dd>
          </div>
          <div>
            <dt>Holo</dt>
            <dd>${entry.is_holo ? "Tak" : "Nie"}</dd>
          </div>
          <div>
            <dt>Cena zakupu</dt>
            <dd>${purchase}</dd>
          </div>
        </dl>
        <footer>
          <a class="button inline" href="/collection">Edytuj w tabeli</a>
        </footer>
      `;
      container.appendChild(item);
    }
  };

  const loadCollection = async (options = {}) => {
    const alertElement = options.alert || null;
    const token = getToken();
    if (!token) {
      return;
    }
    try {
      const entries = await apiFetch("/cards/");
      collectionCache = Array.isArray(entries) ? entries : [];
      renderCollection(collectionCache);
      renderPortfolio(collectionCache);
      if (alertElement && options.message) {
        showAlert(alertElement, options.message, "success");
      }
    } catch (error) {
      if (alertElement) {
        showAlert(
          alertElement,
          error.message || "Nie udało się pobrać danych kolekcji.",
          "error",
        );
      }
      if (error.status === 401) {
        window.location.href = "/login";
      }
    }
  };

  const readRowPayload = (row) => {
    const quantityInput = row.querySelector('[data-field="quantity"]');
    const reverseInput = row.querySelector('[data-field="is_reverse"]');
    const holoInput = row.querySelector('[data-field="is_holo"]');
    const priceInput = row.querySelector('[data-field="purchase_price"]');

    const quantity = quantityInput ? Number.parseInt(quantityInput.value, 10) : 0;
    const purchaseRaw = priceInput ? priceInput.value.trim() : "";
    const purchase = purchaseRaw ? Number.parseFloat(purchaseRaw.replace(",", ".")) : null;

    return {
      quantity: Number.isFinite(quantity) && quantity >= 0 ? quantity : 0,
      purchase_price:
        purchaseRaw && Number.isFinite(purchase) && purchase >= 0 ? Number(purchase.toFixed(2)) : null,
      is_reverse: Boolean(reverseInput && reverseInput.checked),
      is_holo: Boolean(holoInput && holoInput.checked),
    };
  };

  const handleSaveEntry = async (id, row) => {
    const alertBox = document.getElementById("collection-alert");
    const payload = readRowPayload(row);
    try {
      const updated = await apiFetch(`/cards/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      collectionCache = collectionCache.map((entry) =>
        entry.id === updated.id ? updated : entry,
      );
      renderCollection(collectionCache);
      renderPortfolio(collectionCache);
      showAlert(alertBox, "Wpis zaktualizowany.", "success");
    } catch (error) {
      showAlert(alertBox, error.message || "Nie udało się zapisać zmian.", "error");
    }
  };

  const handleDeleteEntry = async (id) => {
    const alertBox = document.getElementById("collection-alert");
    try {
      await apiFetch(`/cards/${id}`, { method: "DELETE" });
      collectionCache = collectionCache.filter((entry) => String(entry.id) !== String(id));
      renderCollection(collectionCache);
      renderPortfolio(collectionCache);
      showAlert(alertBox, "Wpis usunięty z kolekcji.", "success");
    } catch (error) {
      showAlert(alertBox, error.message || "Nie udało się usunąć wpisu.", "error");
    }
  };

  const setupCollectionPage = () => {
    const table = document.getElementById("collection-table");
    if (table) {
      table.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement)) return;
        const action = target.dataset.action;
        const id = target.dataset.id;
        if (!action || !id) return;
        const row = target.closest("tr");
        if (!row) return;
        if (action === "save") {
          handleSaveEntry(id, row);
        }
        if (action === "delete") {
          handleDeleteEntry(id);
        }
      });
    }

    const refreshButton = document.getElementById("refresh-collection");
    if (refreshButton) {
      refreshButton.addEventListener("click", () => {
        const alertBox = document.getElementById("collection-alert");
        showAlert(alertBox, "Ładuję dane…");
        loadCollection({ alert: alertBox, message: "Lista została odświeżona." });
      });
    }
  };

  const setupPortfolioPage = () => {
    const refreshButton = document.getElementById("refresh-portfolio");
    if (refreshButton) {
      refreshButton.addEventListener("click", () => {
        const alertBox = document.getElementById("portfolio-alert");
        showAlert(alertBox, "Ładuję dane…");
        loadCollection({ alert: alertBox, message: "Dane zostały odświeżone." });
      });
    }
  };

  const buildCardPayload = (form) => ({
    name: form.elements.card_name?.value?.trim() || "",
    number: form.elements.card_number?.value?.trim() || "",
    set_name: form.elements.card_set_name?.value?.trim() || "",
    set_code: form.elements.card_set_code?.value?.trim() || null,
    rarity: form.elements.card_rarity?.value?.trim() || null,
    image_small: form.elements.card_image_small?.value?.trim() || null,
    image_large: form.elements.card_image_large?.value?.trim() || null,
  });

  const RARITY_ICON_BASE_PATH = "/static/icons/rarity";
  const RARITY_ICON_IMAGE_BASE_PATH = "/icon/rarity";
  const RARITY_ICON_MAP = Object.freeze({
    "common": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Common.png`,
    "uncommon": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Uncommon.png`,
    "rare": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Rare.png`,
    "rare-holo": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Rare.png`,
    "holo-rare": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Rare.png`,
    "double-rare": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Double_Rare.png`,
    "rare-double": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Double_Rare.png`,
    "ultra-rare": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Ultra_Rare.png`,
    "rare-ultra": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Ultra_Rare.png`,
    "hyper-rare": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Hyper_Rare.png`,
    "rare-secret": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Hyper_Rare.png`,
    "secret-rare": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Hyper_Rare.png`,
    "rare-rainbow": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Hyper_Rare.png`,
    "rainbow-rare": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Hyper_Rare.png`,
    "illustration-rare": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Illustration%20Rare.png`,
    "rare-illustration": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Illustration%20Rare.png`,
    "special-illustration-rare": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Special_Illustration_Rare.png`,
    "rare-special-illustration": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Special_Illustration_Rare.png`,
    "shiny-rare": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Shiny_Rare.png`,
    "rare-shiny": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Shiny_Rare.png`,
    "shinyrare": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_ShinyRare.png`,
    "ace-spec": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_ACE_SPEC_Rare.png`,
    "rare-ace": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_ACE_SPEC_Rare.png`,
    "ace-spec-rare": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_ACE_SPEC_Rare.png`,
  });

  const RARITY_ICON_RULES = [
    { pattern: /ace[\s-]?spec/i, key: "ace-spec" },
    { pattern: /special\s+illustration/i, key: "special-illustration-rare" },
    { pattern: /illustration/i, key: "illustration-rare" },
    { pattern: /(hyper|secret|rainbow|gold)/i, key: "hyper-rare" },
    { pattern: /(shiny|shining|radiant)/i, key: "shiny-rare" },
    { pattern: /double/i, key: "double-rare" },
    {
      pattern: /(ultra|vmax|v-star|vstar|v-union|gx|ex|mega|prime|legend)/i,
      key: "ultra-rare",
    },
    { pattern: /holo/i, key: "rare" },
    { pattern: /rare/i, key: "rare" },
    { pattern: /uncommon/i, key: "uncommon" },
    { pattern: /common/i, key: "common" },
  ];

  const normalizeRarityKey = (rarity) => rarity
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+/, "")
    .replace(/-+$/, "");

  const resolveRarityIconUrl = (rarity) => {
    if (!rarity) return null;
    const normalized = normalizeRarityKey(rarity);
    if (normalized && Object.prototype.hasOwnProperty.call(RARITY_ICON_MAP, normalized)) {
      return RARITY_ICON_MAP[normalized];
    }
    const lowerValue = rarity.toLowerCase();
    for (const rule of RARITY_ICON_RULES) {
      if (rule.pattern.test(lowerValue)) {
        return RARITY_ICON_MAP[rule.key] || null;
      }
    }
    return null;
  };

  const SET_ICON_LOCAL_BASE = "/icon/set";

  const resolveSetIconUrl = (item, options = {}) => {
    const { preferLocal = false } = options || {};
    if (!item) {
      return { primary: null, fallback: null };
    }
    const primaryIcon = (item.set_icon || "").trim() || null;
    const explicitFallback = (item.set_icon_path || "").trim() || null;

    const setCodeRaw = (item.set_code || "").trim();
    let derivedFallback = null;
    if (setCodeRaw) {
      const normalizedCode = setCodeRaw.toLowerCase().replace(/[^a-z0-9-]/g, "");
      if (normalizedCode) {
        derivedFallback = `${SET_ICON_LOCAL_BASE}/${encodeURIComponent(normalizedCode)}.png`;
      }
    }

    const localIcon = explicitFallback || derivedFallback;

    if (preferLocal && localIcon) {
      const normalizedFallback = primaryIcon && primaryIcon !== localIcon ? primaryIcon : null;
      return { primary: localIcon, fallback: normalizedFallback };
    }

    if (primaryIcon) {
      const normalizedFallback = localIcon && localIcon !== primaryIcon ? localIcon : null;
      return { primary: primaryIcon, fallback: normalizedFallback };
    }

    if (localIcon) {
      return { primary: localIcon, fallback: null };
    }

    return { primary: null, fallback: null };
  };

  const renderSearchResults = (
    items = [],
    summaryElement,
    emptyMessage,
    totalCount = 0,
    page = 1,
    perPage = 20,
    viewMode = "grid",
  ) => {
    const container = document.getElementById("card-search-results");
    if (!container) return;
    container.innerHTML = "";
    if (!items.length) {
      if (summaryElement) {
        summaryElement.hidden = true;
        summaryElement.textContent = "";
      }
      if (emptyMessage) {
        emptyMessage.hidden = false;
        emptyMessage.textContent = "Nie znaleziono kart spełniających kryteria.";
      }
      return;
    }
    if (emptyMessage) emptyMessage.hidden = true;
    if (summaryElement) {
      summaryElement.hidden = false;
      const effectiveTotal = Number.isFinite(totalCount) && totalCount > 0
        ? totalCount
        : items.length;
      const normalizedPerPage = perPage && perPage > 0 ? perPage : items.length;
      const normalizedPage = page && page > 0 ? page : 1;
      const totalPages = Math.max(1, Math.ceil(effectiveTotal / normalizedPerPage));
      const startIndex = (normalizedPage - 1) * normalizedPerPage + 1;
      const endIndex = startIndex + items.length - 1;
      const safeStart = Math.max(1, startIndex);
      const safeEnd = Math.max(safeStart, endIndex);
      summaryElement.textContent = `Znaleziono ${effectiveTotal} wyników. Wyświetlam ${safeStart}–${safeEnd}. Strona ${normalizedPage} z ${totalPages}.`;
    }
    const isListView = viewMode === "list";
    for (const item of items) {
      const article = document.createElement("article");
      article.className = "card-search-item";
      const numberLabel = item.number_display || item.number || "";
      const cardName = (item.name || "").trim() || "Bez nazwy";
      const setName = (item.set_name || "").trim() || "Nieznany dodatek";
      const hasThumbnail = Boolean(item.image_small);
      const cardAlt = `Miniatura karty ${cardName}`;
      const quickAddLabel = `Dodaj kartę ${cardName} do kolekcji`;
      const priceValue = getCardPriceValue(item);
      const priceText = priceValue === null ? "" : formatCardPrice(priceValue);
      const rarityRaw = (item.rarity || "").trim();
      const rarityText = rarityRaw || "Brak danych";
      const raritySymbol = (item.rarity_symbol || "").trim();
      const hasRaritySymbol = Boolean(raritySymbol);
      const raritySymbolIsImage =
        hasRaritySymbol && (
          /^(data:|https?:|\/\/)/i.test(raritySymbol)
          || raritySymbol.startsWith("/")
          || /\.(svg|png|webp|jpe?g|gif)$/i.test(raritySymbol)
        );
      const setCodeRaw = (item.set_code || "").trim();
      const setCodeText = setCodeRaw || "—";
      const rarityIconFromMap = raritySymbolIsImage ? null : resolveRarityIconUrl(rarityRaw);
      const rarityIconUrl = raritySymbolIsImage
        ? raritySymbol
        : rarityIconFromMap;
      const hasRarityVisual = Boolean(rarityIconUrl);
      const rarityAlt = `Symbol rzadkości ${rarityText}`;
      const rarityFallback = rarityRaw ? rarityRaw.charAt(0).toUpperCase() : "?";
      const { primary: setIconUrl, fallback: setIconFallbackUrl } = resolveSetIconUrl(item, { preferLocal: true });
      const setIconAltBase = setName && setName !== "Nieznany dodatek" ? setName : setCodeText;
      const setIconAlt = setIconAltBase ? `Symbol dodatku ${setIconAltBase}` : "Symbol dodatku";
      const hasSetIconVisual = Boolean(setIconUrl);
      const setIconFallbackHiddenAttr = hasSetIconVisual ? " hidden" : "";
      const setIconFallbackUrlAttr = setIconFallbackUrl && setIconFallbackUrl !== setIconUrl
        ? ` data-card-set-icon-fallback-url="${escapeHtml(setIconFallbackUrl)}"`
        : "";
      const setIconImageMarkup = hasSetIconVisual
        ? `<img class="card-search-set-icon" src="${escapeHtml(setIconUrl)}" alt="${escapeHtml(setIconAlt)}" loading="lazy" decoding="async" data-card-set-icon${setIconFallbackUrlAttr} />`
        : "";
      const setIconMarkup = `
        <div class="card-search-badge card-search-badge--set">
          ${setIconImageMarkup}
          <span class="card-search-set-code card-search-set-fallback"${setIconFallbackHiddenAttr} data-card-set-code data-card-set-icon-fallback>${escapeHtml(setCodeText)}</span>
        </div>
      `;
      const cardLinkParams = new URLSearchParams();
      if (item.name) cardLinkParams.set("name", item.name);
      if (item.number) cardLinkParams.set("number", item.number);
      if (item.set_name) cardLinkParams.set("set_name", item.set_name);
      if (item.set_code) cardLinkParams.set("set_code", item.set_code);
      const cardLinkQuery = cardLinkParams.toString();
      const cardLinkSetSegment = encodeURIComponent(item.set_code || item.set_name || "");
      const cardLinkNumberSegment = encodeURIComponent(item.number || "");
      const cardLink = `/cards/${cardLinkSetSegment}/${cardLinkNumberSegment}${cardLinkQuery ? `?${cardLinkQuery}` : ""}`;
      const cardLinkLabel = `Zobacz kartę ${cardName}`;
      const rarityIconMarkup = `
        <div class="card-search-badge card-search-badge--rarity">
          <div class="card-search-rarity-icon">
            ${
              rarityIconUrl
                ? `<img src="${escapeHtml(rarityIconUrl)}" alt="${escapeHtml(rarityAlt)}" loading="lazy" decoding="async" data-card-rarity-icon />`
                : ""
            }
            <span class="card-search-rarity-icon-fallback"${hasRarityVisual ? " hidden" : ""} data-card-rarity-icon-fallback aria-hidden="true">${escapeHtml(rarityFallback)}</span>
          </div>
        </div>
      `;
      const setBadgesGridMarkup = `
        <div class="card-search-set-badges">
          ${setIconMarkup}
          ${rarityIconMarkup}
        </div>
      `;
      const numberDisplay = numberLabel || "—";
      const priceDisplay = priceText || "—";
      if (isListView) {
        const previewImage = item.image_large || item.image_small || "";
        const hasPreviewImage = Boolean(previewImage);
        const thumbAttributes = hasPreviewImage ? " data-has-preview=\"true\"" : "";
        const priceClasses = ["card-search-list-price"];
        if (!priceText) {
          priceClasses.push("card-search-list-price--empty");
        }
        const priceAttributes = priceText ? " data-card-price" : "";
        article.innerHTML = `
          <div class="card-search-list-row">
            <div class="card-search-list-thumb"${thumbAttributes}>
              <a class="card-search-thumbnail-link" href="${escapeHtml(cardLink)}" aria-label="${escapeHtml(cardLinkLabel)}">
                <svg class="card-search-list-icon" viewBox="0 0 48 48" role="img" aria-hidden="true">
                  <rect class="card-search-list-icon-frame" x="5" y="6" width="38" height="36" rx="6" />
                  <rect class="card-search-list-icon-stripe" x="11" y="14" width="26" height="6" rx="3" />
                  <rect class="card-search-list-icon-stripe" x="11" y="24" width="20" height="6" rx="3" />
                </svg>
              </a>
              ${
                hasPreviewImage
                  ? `<div class="card-search-list-preview" role="presentation">
                      <img src="${escapeHtml(previewImage)}" alt="${escapeHtml(cardAlt)}" loading="lazy" />
                    </div>`
                  : ""
              }
            </div>
            <div class="card-search-list-set" title="${escapeHtml(setName)}">
              ${setIconMarkup}
            </div>
            <h3 class="card-search-list-title card-search-list-name" title="${escapeHtml(cardName)}">
              <a class="card-search-title-link" href="${escapeHtml(cardLink)}">${escapeHtml(cardName)}</a>
            </h3>
            <div class="card-search-list-number">${escapeHtml(numberDisplay)}</div>
            <div class="card-search-list-rarity" title="${escapeHtml(rarityText)}">
              ${rarityIconMarkup}
            </div>
            <div class="${priceClasses.join(" ")}"${priceAttributes}>
              <span class="card-search-list-price-value">${escapeHtml(priceDisplay)}</span>
              <form class="card-search-form" data-card-form>
                <input type="hidden" name="card_name" value="${escapeHtml(item.name)}" />
                <input type="hidden" name="card_number" value="${escapeHtml(item.number)}" />
                <input type="hidden" name="card_set_name" value="${escapeHtml(item.set_name)}" />
                <input type="hidden" name="card_set_code" value="${escapeHtml(item.set_code || "")}" />
                <input type="hidden" name="card_rarity" value="${escapeHtml(item.rarity || "")}" />
                <input type="hidden" name="card_image_small" value="${escapeHtml(item.image_small || "")}" />
                <input type="hidden" name="card_image_large" value="${escapeHtml(item.image_large || "")}" />
                <input type="hidden" name="quantity" value="1" />
                <div class="form-footer">
                  <button
                    type="submit"
                    class="card-quick-add"
                    data-card-quick-add
                    aria-label="${escapeHtml(quickAddLabel)}"
                    title="Dodaj do kolekcji"
                  >
                    <span aria-hidden="true">+</span>
                  </button>
                </div>
              </form>
            </div>
          </div>
        `;
      } else {
        article.innerHTML = `
          <div class="card-search-media">
            <div class="card-search-thumbnail">
              <a class="card-search-thumbnail-link" href="${escapeHtml(cardLink)}" aria-label="${escapeHtml(cardLinkLabel)}">
                ${
                  hasThumbnail
                    ? `<img src="${escapeHtml(item.image_small)}" alt="${escapeHtml(cardAlt)}" loading="lazy" decoding="async" data-card-thumbnail />`
                    : ""
                }
                <div class="card-search-thumbnail-fallback"${hasThumbnail ? " hidden" : ""} data-card-thumbnail-fallback>
                  Brak miniatury
                </div>
              </a>
            </div>
          <div class="card-search-set">
            ${setBadgesGridMarkup}
          </div>
        </div>
        <div class="card-search-info">
          <h3>
            <a class="card-search-title-link" href="${escapeHtml(cardLink)}">${escapeHtml(cardName)}</a>
          </h3>
            <p class="card-search-info-meta">
              <span class="card-search-set-name">${escapeHtml(setName)}</span>
              ${
                numberLabel
                  ? `<span class="card-search-info-divider" aria-hidden="true">—</span>
                     <span class="card-search-info-number">${escapeHtml(numberLabel)}</span>`
                  : ""
              }
            </p>
            ${
              priceText
                ? `<p class="card-search-price" data-card-price>Cena: ${escapeHtml(priceText)}</p>`
                : ""
            }
          </div>
          <button
            type="button"
            class="card-quick-add"
            data-card-quick-add
            aria-label="${escapeHtml(quickAddLabel)}"
            title="Dodaj do kolekcji"
          >
            <span aria-hidden="true">+</span>
          </button>
          <form class="card-search-form" data-card-form>
            <input type="hidden" name="card_name" value="${escapeHtml(item.name)}" />
            <input type="hidden" name="card_number" value="${escapeHtml(item.number)}" />
            <input type="hidden" name="card_set_name" value="${escapeHtml(item.set_name)}" />
            <input type="hidden" name="card_set_code" value="${escapeHtml(item.set_code || "")}" />
            <input type="hidden" name="card_rarity" value="${escapeHtml(item.rarity || "")}" />
            <input type="hidden" name="card_image_small" value="${escapeHtml(item.image_small || "")}" />
            <input type="hidden" name="card_image_large" value="${escapeHtml(item.image_large || "")}" />
            <label>
              Ilość
              <input type="number" name="quantity" min="0" step="1" value="1" />
            </label>
            <label>
              Cena zakupu
              <input type="number" name="purchase_price" min="0" step="0.01" inputmode="decimal" placeholder="0.00" />
            </label>
            <label class="checkbox">
              <input type="checkbox" name="is_reverse" /> Reverse
            </label>
            <label class="checkbox">
              <input type="checkbox" name="is_holo" /> Holo
            </label>
            <div class="form-footer">
              <button type="submit" class="button primary">Dodaj do kolekcji</button>
            </div>
          </form>
        `;
      }
      const setIconElement = article.querySelector("[data-card-set-icon]");
      const setIconFallbackElement = article.querySelector("[data-card-set-icon-fallback]");
      if (setIconElement && setIconFallbackElement) {
        const handleSetIconError = () => {
          const fallbackUrl = setIconElement.dataset.cardSetIconFallbackUrl;
          if (fallbackUrl && setIconElement.dataset.cardSetIconFallbackTried !== "true") {
            setIconElement.dataset.cardSetIconFallbackTried = "true";
            setIconElement.src = fallbackUrl;
            return;
          }
          setIconElement.remove();
          setIconFallbackElement.hidden = false;
        };
        setIconElement.addEventListener("error", handleSetIconError);
      } else if (setIconFallbackElement) {
        setIconFallbackElement.hidden = false;
      }
      if (!isListView) {
        const thumbnail = article.querySelector("[data-card-thumbnail]");
        const thumbnailFallback = article.querySelector("[data-card-thumbnail-fallback]");
        if (thumbnail && thumbnailFallback) {
          const handleThumbnailError = () => {
            thumbnail.remove();
            thumbnailFallback.hidden = false;
          };
          thumbnail.addEventListener("error", handleThumbnailError, { once: true });
        }
        const rarityIcon = article.querySelector("[data-card-rarity-icon]");
        const rarityIconFallback = article.querySelector("[data-card-rarity-icon-fallback]");
        if (rarityIcon && rarityIconFallback) {
          const handleRarityIconError = () => {
            rarityIcon.remove();
            rarityIconFallback.hidden = false;
          };
          rarityIcon.addEventListener("error", handleRarityIconError, { once: true });
        }
      }
      container.appendChild(article);
    }
  };

  const setupAddCardPage = () => {
    const form = document.querySelector("[data-card-search-form]");
    if (!form) return;
    const alertBox = document.getElementById("add-card-alert");
    const summary = document.getElementById("card-search-summary");
    const emptyMessage = document.getElementById("card-search-empty");
    const viewButtons = Array.from(document.querySelectorAll("[data-card-view]") || []);
    const sortSelect = document.querySelector("[data-card-sort]");
    const results = document.getElementById("card-search-results");
    const pagination = document.getElementById("card-search-pagination");
    let latestItems = [];
    let latestTotalCount = 0;
    let latestQuery = "";
    let latestPage = 1;
    let latestPerPage = 20;
    let isFetching = false;

    const toPositiveInteger = (value, fallback) => {
      if (typeof value === "number" && Number.isFinite(value) && value > 0) {
        return Math.floor(value);
      }
      if (typeof value === "string" && value.trim() !== "") {
        const parsed = Number.parseInt(value, 10);
        if (Number.isFinite(parsed) && parsed > 0) {
          return parsed;
        }
      }
      return fallback;
    };

    const updateViewButtons = (mode) => {
      viewButtons.forEach((button) => {
        const isActive = button.dataset.cardView === mode;
        button.classList.toggle("is-active", isActive);
        button.setAttribute("aria-pressed", isActive ? "true" : "false");
      });
    };

    const applyViewMode = (mode, options = {}) => {
      const normalized = mode === "grid" ? "grid" : "list";
      applyCardResultsViewMode(normalized);
      updateViewButtons(normalized);
      if (options.persist !== false) {
        persistCardViewMode(normalized);
      }
    };

    const applySortOrder = (order, options = {}) => {
      const normalized = CARD_SORT_ALLOWED.has(order) ? order : "relevance";
      currentCardSortOrder = normalized;
      if (sortSelect && sortSelect.value !== normalized) {
        sortSelect.value = normalized;
      }
      if (options.persist !== false) {
        persistCardSortOrder(normalized);
      }
    };

    const renderPageIndexButtons = (totalPages) => {
      if (!pagination) return;
      pagination.innerHTML = "";
      if (!Number.isFinite(totalPages) || totalPages <= 1) {
        return;
      }

      const fragment = document.createDocumentFragment();

      const createButton = ({ text, action, page, disabled, ariaLabel }) => {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = text;
        if (action) {
          button.dataset.pageAction = action;
        }
        if (Number.isFinite(page) && page) {
          button.dataset.pageIndex = String(page);
        }
        if (ariaLabel) {
          button.setAttribute("aria-label", ariaLabel);
        }
        if (disabled) {
          button.disabled = true;
        }
        return button;
      };

      const prevButton = createButton({
        text: "<",
        action: "prev",
        disabled: latestPage <= 1,
        ariaLabel: "Poprzednia strona",
      });
      fragment.appendChild(prevButton);

      const maxPagesToRender = Math.min(totalPages, 5);
      let startPage = Math.max(1, latestPage - Math.floor(maxPagesToRender / 2));
      let endPage = startPage + maxPagesToRender - 1;
      if (endPage > totalPages) {
        endPage = totalPages;
        startPage = Math.max(1, endPage - maxPagesToRender + 1);
      }

      for (let page = startPage; page <= endPage; page += 1) {
        const isCurrent = page === latestPage;
        const button = createButton({
          text: String(page),
          page,
          disabled: isCurrent,
          ariaLabel: `Przejdź do strony ${page}`,
        });
        button.classList.toggle("is-active", isCurrent);
        if (isCurrent) {
          button.setAttribute("aria-current", "page");
        }
        fragment.appendChild(button);
      }

      const nextButton = createButton({
        text: ">",
        action: "next",
        disabled: latestPage >= totalPages,
        ariaLabel: "Następna strona",
      });
      fragment.appendChild(nextButton);

      pagination.appendChild(fragment);
    };

    const updatePaginationControls = () => {
      if (!pagination) return;
      const totalAvailable = latestTotalCount > 0 ? latestTotalCount : latestItems.length;
      if (!latestItems.length || !totalAvailable) {
        pagination.hidden = true;
        pagination.innerHTML = "";
        return;
      }
      const perPage = latestPerPage > 0 ? latestPerPage : latestItems.length;
      const totalPages = Math.max(1, Math.ceil(totalAvailable / perPage));
      pagination.hidden = totalPages <= 1 && latestPage <= 1;
      renderPageIndexButtons(totalPages);
    };

    const renderLatestResults = () => {
      const sortedItems = sortCardSearchItems(latestItems, currentCardSortOrder);
      renderSearchResults(
        sortedItems,
        summary,
        emptyMessage,
        latestTotalCount,
        latestPage,
        latestPerPage,
        currentCardViewMode,
      );
      applyViewMode(currentCardViewMode, { persist: false });
      updatePaginationControls();
    };

    const storedView = readStoredCardViewMode();
    const storedSort = readStoredCardSortOrder();
    currentCardViewMode = storedView ?? "grid";
    if (storedSort) {
      currentCardSortOrder = storedSort;
    }
    if (sortSelect) {
      sortSelect.value = currentCardSortOrder;
    }
    applyViewMode(currentCardViewMode, { persist: false });

    viewButtons.forEach((button) => {
      button.addEventListener("click", () => {
        applyViewMode(button.dataset.cardView || "list");
        renderLatestResults();
      });
    });

    if (sortSelect) {
      sortSelect.addEventListener("change", (event) => {
        applySortOrder(event.target.value);
        renderLatestResults();
      });
    }

    const fetchResults = async ({ query, page = 1, message } = {}) => {
      const queryValue = typeof query === "string" ? query.trim() : latestQuery;
      if (!queryValue) {
        return;
      }
      const targetPage = page && page > 0 ? page : 1;
      const params = new URLSearchParams({
        query: queryValue,
        page: String(targetPage),
        per_page: String(latestPerPage),
      });
      const requestSort = mapSortOrderToRequest(currentCardSortOrder);
      if (requestSort.sort) {
        params.set("sort", requestSort.sort);
      }
      if (requestSort.order) {
        params.set("order", requestSort.order);
      }

      if (message) {
        showAlert(alertBox, message);
      }

      if (isFetching) return;
      isFetching = true;

      try {
        const data = await apiFetch(`/cards/search?${params.toString()}`);
        latestQuery = queryValue;
        latestItems = Array.isArray(data?.items) ? [...data.items] : [];
        const totalCountValue = toPositiveInteger(
          data?.total_count,
          toPositiveInteger(data?.total, latestItems.length),
        );
        latestTotalCount = Math.max(latestItems.length, totalCountValue ?? 0);
        latestTotalCount = Math.min(100, latestTotalCount);
        let receivedPerPage = toPositiveInteger(data?.per_page, latestPerPage);
        receivedPerPage = Math.max(1, Math.min(receivedPerPage, 20));
        latestPerPage = receivedPerPage;
        latestPage = toPositiveInteger(data?.page, targetPage);
        renderLatestResults();
        showAlert(alertBox, "");
      } catch (error) {
        showAlert(alertBox, error.message || "Nie udało się pobrać wyników.", "error");
      } finally {
        isFetching = false;
      }
    };

    if (pagination) {
      pagination.addEventListener("click", async (event) => {
        if (isFetching) return;
        const target = event.target instanceof Element
          ? event.target.closest("[data-page-action],[data-page-index]")
          : null;
        if (!target || !(target instanceof HTMLElement)) return;
        if (target.hasAttribute("disabled")) return;

        if (target.dataset.pageAction === "prev") {
          const targetPage = Math.max(1, latestPage - 1);
          if (targetPage === latestPage) return;
          await fetchResults({ page: targetPage, message: "Ładuję poprzednią stronę…" });
          return;
        }

        if (target.dataset.pageAction === "next") {
          const targetPage = latestPage + 1;
          await fetchResults({ page: targetPage, message: "Ładuję kolejną stronę…" });
          return;
        }

        const page = toPositiveInteger(target.dataset.pageIndex, 0);
        if (!page || page === latestPage) return;
        await fetchResults({ page, message: `Ładuję stronę ${page}…` });
      });
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const queryInput = form.querySelector("input[name='query']");
      const query = queryInput ? queryInput.value.trim() : "";
      if (!query) {
        showAlert(alertBox, "Wpisz nazwę lub numer karty.", "error");
        queryInput?.focus();
        return;
      }
      latestPerPage = 20;
      latestPage = 1;
      await fetchResults({ query, page: 1, message: "Szukam kart…" });
    });

    const handleCardFormSubmission = async (target, trigger) => {
      const alertTarget = document.getElementById("add-card-alert");
      const quantity = Number.parseInt(target.elements.quantity?.value || "1", 10);
      const priceRaw = target.elements.purchase_price?.value?.trim() || "";
      const price = priceRaw ? Number.parseFloat(priceRaw.replace(",", ".")) : null;
      const payload = {
        quantity: Number.isFinite(quantity) && quantity >= 0 ? quantity : 0,
        purchase_price:
          priceRaw && Number.isFinite(price) && price >= 0 ? Number(price.toFixed(2)) : null,
        is_reverse: Boolean(target.elements.is_reverse?.checked),
        is_holo: Boolean(target.elements.is_holo?.checked),
        card: buildCardPayload(target),
      };
      if (!payload.card.name || !payload.card.number || !payload.card.set_name) {
        showAlert(alertTarget, "Brakuje danych karty.", "error");
        return;
      }
      showAlert(alertTarget, "Dodaję kartę do kolekcji…");
      try {
        await apiFetch("/cards/", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        showAlert(alertTarget, "Karta została dodana do kolekcji.", "success");
        target.reset();
        if (trigger && typeof trigger.focus === "function") {
          trigger.focus();
        } else {
          target.querySelector('button[type="submit"]')?.focus();
        }
        loadCollection();
      } catch (error) {
        showAlert(alertTarget, error.message || "Nie udało się dodać karty.", "error");
        if (trigger && typeof trigger.focus === "function") {
          trigger.focus();
        }
      }
    };

    if (results) {
      results.addEventListener("submit", async (event) => {
        const target = event.target;
        if (!(target instanceof HTMLFormElement)) return;
        event.preventDefault();
        const trigger = event.submitter || target.querySelector('button[type="submit"]');
        await handleCardFormSubmission(target, trigger);
      });

      results.addEventListener("click", async (event) => {
        const button = event.target instanceof Element
          ? event.target.closest("[data-card-quick-add]")
          : null;
        if (!button) return;
        const formTarget = button.closest("form[data-card-form]")
          || button.closest(".card-search-item")?.querySelector("form[data-card-form]");
        if (!(formTarget instanceof HTMLFormElement)) return;
        event.preventDefault();
        event.stopPropagation();
        await handleCardFormSubmission(formTarget, button);
      });
    }
  };

  const PRICE_HISTORY_RANGE_LABELS = Object.freeze({
    last_7: "ostatnie 7 dni",
    last_30: "ostatnie 30 dni",
    all: "pełny zakres",
  });

  const createPriceHistoryModule = () => {
    const section = document.getElementById("card-price-history-section");
    const chart = document.getElementById("card-price-chart");
    const chartLayer = chart?.querySelector("#card-price-chart-data");
    const emptyState = document.getElementById("card-price-chart-empty");
    const controls = Array.from(document.querySelectorAll("[data-price-range]"));

    if (!section || !chart || !chartLayer || !emptyState || !controls.length) {
      return { setData: () => {}, setRangeFetcher: () => {} };
    }

    const SVG_NS = "http://www.w3.org/2000/svg";
    const ranges = {
      last_7: [],
      last_30: [],
      all: [],
    };
    const RELATED_RANGES = Object.freeze({
      last_7: [],
      last_30: ["last_7"],
      all: ["last_7", "last_30"],
    });
    const fetchedRanges = new Set();
    let activeRange = "last_30";
    let isLoading = false;
    let rangeFetcher = null;

    const parseHistoryPoints = (items) => {
      if (!Array.isArray(items)) return [];
      const parsed = [];
      for (const item of items) {
        const price = normalizePriceInput(item?.price);
        if (price === null) continue;
        const dateValue = typeof item?.date === "string" ? item.date.trim() : "";
        if (!dateValue) continue;
        const parsedDate = new Date(dateValue);
        const isValidDate = !Number.isNaN(parsedDate.getTime());
        parsed.push({
          price,
          iso: dateValue,
          date: isValidDate ? parsedDate : null,
          label: isValidDate ? parsedDate.toLocaleDateString("pl-PL") : dateValue,
        });
      }
      parsed.sort((a, b) => {
        if (a.date && b.date) {
          return a.date - b.date;
        }
        return a.iso.localeCompare(b.iso);
      });
      return parsed;
    };

    const updateControls = (rangeKey) => {
      controls.forEach((button) => {
        const key = button.dataset.priceRange;
        const hasData = Boolean(key && ranges[key] && ranges[key].length);
        const attempted = key ? fetchedRanges.has(key) : false;
        const canFetch = typeof rangeFetcher === "function";
        const disableBecauseNoData = !hasData && attempted && !canFetch;
        const disableBecauseLoading = isLoading && key !== rangeKey;
        button.disabled = disableBecauseNoData || disableBecauseLoading;
        const isActive = key === rangeKey;
        button.classList.toggle("is-active", isActive);
        button.setAttribute("aria-pressed", isActive ? "true" : "false");
        if (button.dataset.loading === "true" && !isLoading) {
          delete button.dataset.loading;
        }
      });
    };

    const setSectionLoading = (loading) => {
      isLoading = Boolean(loading);
      if (isLoading) {
        section.dataset.loading = "true";
        section.setAttribute("aria-busy", "true");
      } else {
        delete section.dataset.loading;
        section.removeAttribute("aria-busy");
      }
      updateControls(activeRange);
    };

    const setChartAriaLabel = (rangeKey, points) => {
      if (!points.length) {
        chart.setAttribute("aria-label", "Brak danych historii cen");
        return;
      }
      const label = PRICE_HISTORY_RANGE_LABELS[rangeKey] || rangeKey || "";
      const firstPoint = points[0];
      const lastPoint = points[points.length - 1];
      const priceText = Number.isFinite(lastPoint.price)
        ? formatCardPrice(lastPoint.price)
        : "";
      const suffix = priceText ? `. Aktualna cena ${priceText}.` : ".";
      chart.setAttribute(
        "aria-label",
        `Historia cen (${label}): od ${firstPoint.label} do ${lastPoint.label}${suffix}`,
      );
    };

    const renderChart = (rangeKey) => {
      const points = ranges[rangeKey] || [];
      chartLayer.innerHTML = "";

      if (!points.length) {
        emptyState.hidden = false;
        chart.setAttribute("aria-hidden", "true");
        setChartAriaLabel(rangeKey, points);
        return;
      }

      emptyState.hidden = true;
      chart.setAttribute("aria-hidden", "false");

      const width = 100;
      const height = 48;
      const marginX = 6;
      const marginY = 8;
      const prices = points.map((point) => point.price);
      const minPrice = Math.min(...prices);
      const maxPrice = Math.max(...prices);
      const priceRange = maxPrice - minPrice || 1;
      const step = points.length > 1 ? (width - marginX * 2) / (points.length - 1) : 0;

      const areaParts = [];
      const lineParts = [];
      let lastX = width / 2;
      let lastY = height / 2;

      points.forEach((point, index) => {
        const x = points.length === 1 ? width / 2 : marginX + index * step;
        const normalized = (point.price - minPrice) / priceRange;
        const y = height - marginY - normalized * (height - marginY * 2);
        const command = index === 0 ? "M" : "L";
        lineParts.push(`${command}${x.toFixed(2)} ${y.toFixed(2)}`);
        areaParts.push(`${command}${x.toFixed(2)} ${y.toFixed(2)}`);
        lastX = x;
        lastY = y;
      });

      if (points.length > 1) {
        areaParts.push(`L${lastX.toFixed(2)} ${height - marginY}`);
        areaParts.push(`L${marginX.toFixed(2)} ${height - marginY}`);
      } else {
        areaParts.push(`L${lastX.toFixed(2)} ${height - marginY}`);
        areaParts.push(`L${lastX.toFixed(2)} ${height - marginY}`);
      }
      areaParts.push("Z");

      const areaPath = document.createElementNS(SVG_NS, "path");
      areaPath.setAttribute("class", "card-price-chart-area");
      areaPath.setAttribute("d", areaParts.join(" "));
      areaPath.setAttribute("fill", "url(#card-price-chart-gradient)");

      const linePath = document.createElementNS(SVG_NS, "path");
      linePath.setAttribute("class", "card-price-chart-line");
      linePath.setAttribute("d", lineParts.join(" "));

      const marker = document.createElementNS(SVG_NS, "circle");
      marker.setAttribute("class", "card-price-chart-marker");
      marker.setAttribute("cx", lastX.toFixed(2));
      marker.setAttribute("cy", lastY.toFixed(2));
      marker.setAttribute("r", "1.6");

      chartLayer.appendChild(areaPath);
      chartLayer.appendChild(linePath);
      chartLayer.appendChild(marker);
      chart.dataset.range = rangeKey;
      setChartAriaLabel(rangeKey, points);
    };

    const setData = (history, options = {}) => {
      const payload = history && typeof history === "object" ? history : {};
      const { activeRange: requestedRange, sourceRange, preserveActive = false } = options;

      if (sourceRange) {
        fetchedRanges.add(sourceRange);
        const related = RELATED_RANGES[sourceRange] || [];
        related.forEach((key) => fetchedRanges.add(key));
      }

      const updatedKeys = [];
      for (const key of ["last_7", "last_30", "all"]) {
        if (Object.prototype.hasOwnProperty.call(payload, key)) {
          const parsed = parseHistoryPoints(payload[key]);
          ranges[key] = parsed;
          updatedKeys.push(key);
        }
      }

      if (!updatedKeys.length && !requestedRange && !preserveActive) {
        return;
      }

      let nextRange = null;

      if (
        requestedRange &&
        (updatedKeys.includes(requestedRange) || (ranges[requestedRange] && ranges[requestedRange].length))
      ) {
        nextRange = requestedRange;
      } else if (preserveActive && ranges[activeRange]) {
        nextRange = activeRange;
      }

      if (!nextRange) {
        for (const key of ["last_30", "last_7", "all"]) {
          if (ranges[key] && ranges[key].length) {
            nextRange = key;
            break;
          }
        }
      }

      if (!nextRange) {
        for (const key of ["last_30", "last_7", "all"]) {
          if (updatedKeys.includes(key)) {
            nextRange = key;
            break;
          }
        }
      }

      if (!nextRange) {
        chartLayer.innerHTML = "";
        chart.setAttribute("aria-hidden", "true");
        emptyState.hidden = false;
        controls.forEach((button) => {
          button.disabled = true;
          button.classList.remove("is-active");
          button.setAttribute("aria-pressed", "false");
        });
        section.hidden = true;
        return;
      }

      section.hidden = false;
      activeRange = nextRange;
      updateControls(activeRange);
      renderChart(activeRange);
    };

    const fetchRangeData = async (rangeKey, triggerButton) => {
      if (typeof rangeFetcher !== "function") {
        return;
      }
      if (isLoading) {
        return;
      }

      const button =
        triggerButton ||
        controls.find((control) => control.dataset.priceRange === rangeKey) ||
        null;
      const wasDisabled = button ? button.disabled : false;

      if (button) {
        button.dataset.loading = "true";
        button.disabled = true;
      }

      setSectionLoading(true);

      try {
        const result = await rangeFetcher(rangeKey);

        let historyPayload = null;
        let sourceRange = rangeKey;

        if (result && typeof result === "object") {
          if (Object.prototype.hasOwnProperty.call(result, "history")) {
            historyPayload = result.history;
            if (result.sourceRange) {
              sourceRange = result.sourceRange;
            }
          } else if (Object.prototype.hasOwnProperty.call(result, "price_history")) {
            historyPayload = result.price_history;
          } else if (result.card && result.card.price_history) {
            historyPayload = result.card.price_history;
          } else {
            historyPayload = result;
          }
        } else {
          historyPayload = result;
        }

        if (historyPayload && typeof historyPayload === "object") {
          setData(historyPayload, {
            activeRange: rangeKey,
            sourceRange,
            preserveActive: true,
          });
        } else if (!ranges[rangeKey] || !ranges[rangeKey].length) {
          setData(
            { [rangeKey]: [] },
            { activeRange: rangeKey, sourceRange: rangeKey, preserveActive: true },
          );
        }
      } catch (error) {
        console.error("Failed to load price history range", error);
      } finally {
        if (button) {
          button.dataset.loading = "false";
          if (!wasDisabled) {
            button.disabled = false;
          }
        }
        setSectionLoading(false);
      }
    };

    controls.forEach((button) => {
      button.addEventListener("click", async () => {
        const rangeKey = button.dataset.priceRange;
        if (!rangeKey) {
          return;
        }

        if (!fetchedRanges.has(rangeKey) && typeof rangeFetcher === "function") {
          await fetchRangeData(rangeKey, button);
          if (activeRange === rangeKey) {
            return;
          }
        }

        if (activeRange === rangeKey) {
          return;
        }

        activeRange = rangeKey;
        updateControls(activeRange);
        renderChart(activeRange);
      });
    });

    return {
      setData,
      setRangeFetcher(handler) {
        rangeFetcher = typeof handler === "function" ? handler : null;
        updateControls(activeRange);
      },
    };
  };

  const renderCardDetail = (card, options = {}) => {
    if (!card) return;
    const { priceHistoryModule, priceHistoryRange } = options;

    const sanitizeText = (value) => (typeof value === "string" ? value.trim() : value);
    const setTextOrFallback = (element, value, fallback = "—") => {
      if (!element) return;
      const textValue = sanitizeText(value);
      if (textValue || textValue === 0) {
        element.textContent = String(textValue);
      } else {
        element.textContent = fallback;
      }
    };

    const title = document.getElementById("card-detail-title");
    if (title) {
      title.textContent = sanitizeText(card.name) || "Szczegóły karty";
    }

    const artistValue = sanitizeText(card.artist);
    const eraValue = sanitizeText(card.era);
    const era = document.getElementById("card-detail-era");
    if (era) {
      if (eraValue) {
        era.textContent = eraValue;
        era.hidden = false;
      } else {
        era.textContent = "";
        era.hidden = true;
      }
    }

    const artistElement = document.getElementById("card-detail-artist");
    if (artistElement) {
      if (artistValue) {
        artistElement.textContent = `Ilustrator: ${artistValue}`;
        artistElement.hidden = false;
      } else {
        artistElement.textContent = "";
        artistElement.hidden = true;
      }
    }

    const setName = document.getElementById("card-detail-set-name");
    if (setName) {
      setName.textContent = sanitizeText(card.set_name) || "Nieznany dodatek";
    }

    const setCodeElement = document.getElementById("card-detail-set-code");
    const setCodeValue = sanitizeText(card.set_code);
    const hasSetCodeValue = Boolean(setCodeValue);
    if (setCodeElement) {
      setCodeElement.textContent = (setCodeValue || "SET").toUpperCase();
      setCodeElement.hidden = true;
    }

    const { primary: setIconUrl, fallback: setIconFallbackUrl } = resolveSetIconUrl(card);
    const setIconImage = document.getElementById("card-detail-set-icon");
    if (setIconImage) {
      const showSetCodeFallback = () => {
        if (setCodeElement) {
          setCodeElement.hidden = !hasSetCodeValue;
        }
      };

      const hideSetCodeFallback = () => {
        if (setCodeElement) {
          setCodeElement.hidden = true;
        }
      };

      if (setIconUrl) {
        setIconImage.hidden = false;
        const setNameValue = sanitizeText(card.set_name);
        setIconImage.alt = setNameValue
          ? `Symbol dodatku ${setNameValue}`
          : "Symbol dodatku";
        setIconImage.src = setIconUrl;
        if (setIconFallbackUrl && setIconFallbackUrl !== setIconUrl) {
          setIconImage.dataset.cardSetIconFallbackUrl = setIconFallbackUrl;
          setIconImage.dataset.cardSetIconFallbackTried = "false";
        } else {
          delete setIconImage.dataset.cardSetIconFallbackUrl;
          delete setIconImage.dataset.cardSetIconFallbackTried;
        }
        hideSetCodeFallback();
        if (!setIconImage.dataset.cardSetIconHandlerAttached) {
          setIconImage.addEventListener("error", () => {
            const fallbackUrl = setIconImage.dataset.cardSetIconFallbackUrl;
            if (fallbackUrl && setIconImage.dataset.cardSetIconFallbackTried !== "true") {
              setIconImage.dataset.cardSetIconFallbackTried = "true";
              setIconImage.src = fallbackUrl;
              return;
            }
            setIconImage.hidden = true;
            setIconImage.removeAttribute("src");
            delete setIconImage.dataset.cardSetIconFallbackUrl;
            delete setIconImage.dataset.cardSetIconFallbackTried;
            showSetCodeFallback();
          });
          setIconImage.dataset.cardSetIconHandlerAttached = "true";
        }
      } else {
        setIconImage.hidden = true;
        setIconImage.removeAttribute("src");
        delete setIconImage.dataset.cardSetIconFallbackUrl;
        delete setIconImage.dataset.cardSetIconFallbackTried;
        showSetCodeFallback();
      }
    }

    const rarityValue = sanitizeText(card.rarity);
    const numberElement = document.getElementById("card-detail-number");
    setTextOrFallback(numberElement, card.number_display || card.number);
    const rarityElement = document.getElementById("card-detail-rarity");
    setTextOrFallback(rarityElement, rarityValue);
    const rarityIconElement = document.getElementById("card-detail-rarity-icon");
    const rarityFallbackElement = document.getElementById("card-detail-rarity-fallback");
    const raritySymbolValue = sanitizeText(card.rarity_symbol);
    const raritySymbolRemoteValue = sanitizeText(card.rarity_symbol_remote);
    const rarityFallbackLabel = (rarityValue || "?").charAt(0).toUpperCase() || "?";
    if (rarityFallbackElement) {
      rarityFallbackElement.textContent = rarityFallbackLabel;
    }
    if (rarityIconElement) {
      const iconCandidates = [];
      const addIconCandidate = (iconUrl) => {
        if (iconUrl && !iconCandidates.includes(iconUrl)) {
          iconCandidates.push(iconUrl);
        }
      };
      const resolvedRarityIcon = resolveRarityIconUrl(rarityValue);
      addIconCandidate(resolvedRarityIcon);
      addIconCandidate(raritySymbolValue);
      addIconCandidate(raritySymbolRemoteValue);
      const [primaryRarityIcon = "", fallbackRarityIcon = ""] = iconCandidates;
      const showRarityFallback = () => {
        if (rarityFallbackElement) {
          rarityFallbackElement.hidden = false;
        }
      };
      const hideRarityFallback = () => {
        if (rarityFallbackElement) {
          rarityFallbackElement.hidden = true;
        }
      };
      const resetRarityIcon = () => {
        rarityIconElement.hidden = true;
        rarityIconElement.removeAttribute("src");
        delete rarityIconElement.dataset.cardRarityIconFallbackUrl;
        delete rarityIconElement.dataset.cardRarityIconFallbackTried;
      };
      if (primaryRarityIcon) {
        rarityIconElement.hidden = false;
        rarityIconElement.alt = rarityValue
          ? `Symbol rzadkości ${rarityValue}`
          : "Symbol rzadkości";
        rarityIconElement.src = primaryRarityIcon;
        hideRarityFallback();
        if (fallbackRarityIcon && fallbackRarityIcon !== primaryRarityIcon) {
          rarityIconElement.dataset.cardRarityIconFallbackUrl = fallbackRarityIcon;
          rarityIconElement.dataset.cardRarityIconFallbackTried = "false";
        } else {
          delete rarityIconElement.dataset.cardRarityIconFallbackUrl;
          delete rarityIconElement.dataset.cardRarityIconFallbackTried;
        }
        if (!rarityIconElement.dataset.cardRarityIconHandlerAttached) {
          rarityIconElement.addEventListener("error", () => {
            const fallbackUrl = rarityIconElement.dataset.cardRarityIconFallbackUrl;
            if (fallbackUrl && rarityIconElement.dataset.cardRarityIconFallbackTried !== "true") {
              rarityIconElement.dataset.cardRarityIconFallbackTried = "true";
              rarityIconElement.src = fallbackUrl;
              return;
            }
            resetRarityIcon();
            showRarityFallback();
          });
          rarityIconElement.dataset.cardRarityIconHandlerAttached = "true";
        }
      } else {
        resetRarityIcon();
        showRarityFallback();
      }
    } else if (rarityFallbackElement) {
      rarityFallbackElement.hidden = false;
    }

    const totalElement = document.getElementById("card-detail-total");
    setTextOrFallback(totalElement, card.total);
    const releaseElement = document.getElementById("card-detail-release");
    setTextOrFallback(releaseElement, card.release_date);

    const descriptionSection = document.getElementById("card-detail-description-section");
    const descriptionContent = document.getElementById("card-detail-description");
    const descriptionMeta = document.getElementById("card-detail-description-meta");
    const descriptionMetaValue = sanitizeText(card.description_meta);
    const descriptionValue = sanitizeText(card.description);
    if (descriptionSection && descriptionContent) {
      if (descriptionValue) {
        descriptionContent.textContent = descriptionValue;
        descriptionSection.hidden = false;
      } else {
        descriptionContent.textContent = "";
        descriptionSection.hidden = true;
      }
    }
    if (descriptionMeta) {
      if (descriptionMetaValue) {
        descriptionMeta.textContent = descriptionMetaValue;
        descriptionMeta.hidden = false;
      } else {
        descriptionMeta.textContent = "";
        descriptionMeta.hidden = true;
      }
    }

    const priceContainer = document.getElementById("card-detail-price-container");
    const priceElement = document.getElementById("card-detail-price");
    const priceValue = getCardPriceValue(card);
    const priceText = priceValue === null ? "" : formatCardPrice(priceValue);
    if (priceElement) {
      if (priceText) {
        priceElement.textContent = `Cena: ${priceText}`;
        priceElement.hidden = false;
      } else {
        priceElement.textContent = "";
        priceElement.hidden = true;
      }
    }
    if (priceContainer) {
      priceContainer.hidden = !priceText;
    }

    const buyButton = document.getElementById("detail-buy-button");
    if (buyButton) {
      const sanitizeSearchComponent = (value) => {
        const text = sanitizeText(value);
        if (text === null || text === undefined) return "";
        const stringValue = String(text).trim();
        if (!stringValue) return "";
        return stringValue
          .normalize("NFKD")
          .replace(/[\u0300-\u036f]/g, "")
          .replace(/[^\p{L}\p{N}\s/-]+/gu, " ")
          .replace(/\s+/g, " ")
          .trim();
      };

      const buildFallbackShopUrl = () => {
        const parts = [];
        const uniqueParts = new Set();
        const addPart = (value) => {
          const sanitized = sanitizeSearchComponent(value);
          if (sanitized) {
            const key = sanitized.toLowerCase();
            if (!uniqueParts.has(key)) {
              uniqueParts.add(key);
              parts.push(sanitized);
            }
          }
        };

        addPart(card.name);
        addPart(card.set_code ? String(card.set_code).toUpperCase() : null);
        addPart(card.number_display || card.number);

        const query = parts.join(" ").trim();
        if (!query) return DEFAULT_SHOP_URL;
        const encodedQuery = encodeURIComponent(query);
        return `https://kartoteka.shop/pl/searchquery/${encodedQuery}/1/full/5?url=${encodedQuery}`;
      };

      const isGenericShopUrl = (url) => {
        if (!url) return true;
        const normalizedDefault = DEFAULT_SHOP_URL.replace(/\/+$/, "").toLowerCase();
        const normalizedUrl = String(url).trim().replace(/\/+$/, "").toLowerCase();
        if (!normalizedUrl) return true;
        return normalizedUrl === normalizedDefault;
      };

      const shopUrl = sanitizeText(card.shop_url);
      const resolvedShopUrl =
        shopUrl && !isGenericShopUrl(shopUrl) ? shopUrl : buildFallbackShopUrl();

      buyButton.href = resolvedShopUrl || DEFAULT_SHOP_URL;
    }

    const image = document.getElementById("card-detail-image");
    const placeholder = document.getElementById("card-detail-placeholder");
    if (image) {
      if (card.image_large || card.image_small) {
        image.src = card.image_large || card.image_small;
        image.hidden = false;
        if (placeholder) placeholder.hidden = true;
      } else {
        image.hidden = true;
        if (placeholder) placeholder.hidden = false;
      }
    }

    if (priceHistoryModule && typeof priceHistoryModule.setData === "function") {
      priceHistoryModule.setData(card.price_history || {}, {
        sourceRange: priceHistoryRange,
        activeRange: priceHistoryRange,
      });
    }
  };

  const renderRelatedCards = (items) => {
    const container = document.getElementById("related-cards-list");
    const empty = document.getElementById("related-empty");
    if (!container) return;
    container.innerHTML = "";
    if (!items || !items.length) {
      if (empty) empty.hidden = false;
      return;
    }
    if (empty) empty.hidden = true;
    for (const item of items) {
      const anchor = document.createElement("a");
      anchor.className = "related-card";
      const params = new URLSearchParams({
        name: item.name,
        number: item.number,
        set_name: item.set_name,
      });
      if (item.set_code) params.set("set_code", item.set_code);
      const cardName = (item.name || "").trim() || "Bez nazwy";
      const setName = (item.set_name || "").trim() || "Nieznany dodatek";
      const numberLabel = (item.number_display || item.number || "").trim();
      const metaParts = [setName];
      if (numberLabel) {
        metaParts.push(numberLabel);
      }
      const metaText = metaParts.filter(Boolean).join(" • ");
      const previewImage = (item.image_small || item.image_large || "").trim();
      const hasPreviewImage = Boolean(previewImage);
      const thumbnailAlt = `Miniatura karty ${cardName}`;
      anchor.href = `/cards/${encodeURIComponent(item.set_code || item.set_name || "")}/${encodeURIComponent(item.number)}?${params.toString()}`;
      anchor.innerHTML = `
        <figure class="related-card-media">
          <div class="related-card-thumbnail">
            ${
              hasPreviewImage
                ? `<img src="${escapeHtml(previewImage)}" alt="${escapeHtml(thumbnailAlt)}" loading="lazy" decoding="async" />`
                : ""
            }
            <div class="related-card-thumbnail-fallback"${hasPreviewImage ? " hidden" : ""}>
              <span class="related-card-thumbnail-emoji" aria-hidden="true">🖼️</span>
              <span class="related-card-thumbnail-text">Brak miniatury</span>
            </div>
          </div>
        </figure>
        <div class="related-card-info">
          <span class="related-card-name">${escapeHtml(cardName)}</span>
          <span class="related-card-meta">${escapeHtml(metaText)}</span>
        </div>
      `;
      container.appendChild(anchor);
    }
  };

  const setupCardDetailPage = () => {
    const container = document.getElementById("card-detail-page");
    if (!container) return;
    const alertBox = document.getElementById("card-detail-alert");
    const priceHistoryModule = createPriceHistoryModule();
    const params = new URLSearchParams();
    const name = container.dataset.name || "";
    const number = container.dataset.number || "";
    if (!name || !number) {
      showAlert(alertBox, "Brakuje danych karty.", "error");
      return;
    }
    params.set("name", name);
    params.set("number", number);
    const total = container.dataset.total || "";
    const setCode = container.dataset.setCode || "";
    const setName = container.dataset.setName || "";
    if (total) params.set("total", total);
    if (setCode) params.set("set_code", setCode);
    if (setName) params.set("set_name", setName);

    const baseParams = new URLSearchParams(params);
    const DEFAULT_PRICE_RANGE = "last_30";

    const formatDateParam = (date) => {
      if (!(date instanceof Date) || Number.isNaN(date.getTime())) {
        return "";
      }
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, "0");
      const day = String(date.getDate()).padStart(2, "0");
      return `${year}-${month}-${day}`;
    };

    const resolveRangeParams = (rangeKey) => {
      if (rangeKey === "all") {
        return {};
      }

      const now = new Date();
      const toDate = formatDateParam(now);
      const days = rangeKey === "last_7" ? 7 : 30;
      const fromDate = new Date(now.getTime());
      fromDate.setDate(fromDate.getDate() - days);
      return {
        date_from: formatDateParam(fromDate),
        date_to: toDate,
      };
    };

    const buildInfoQuery = (rangeKey) => {
      const range = rangeKey || DEFAULT_PRICE_RANGE;
      const query = new URLSearchParams(baseParams);
      query.set("range", range);
      const { date_from: dateFrom, date_to: dateTo } = resolveRangeParams(range);
      if (dateFrom) query.set("date_from", dateFrom);
      if (dateTo) query.set("date_to", dateTo);
      return { query, range };
    };

    const requestCardInfo = async (rangeKey) => {
      const { query, range } = buildInfoQuery(rangeKey);
      const data = await apiFetch(`/cards/info?${query.toString()}`);
      return { data, range };
    };

    if (priceHistoryModule && typeof priceHistoryModule.setRangeFetcher === "function") {
      priceHistoryModule.setRangeFetcher(async (rangeKey) => {
        try {
          const { data, range } = await requestCardInfo(rangeKey);
          const cardData = data?.card;
          if (cardData) {
            renderCardDetail(cardData, {
              priceHistoryModule,
              priceHistoryRange: range,
            });
          }
          showAlert(alertBox, "");
        } catch (error) {
          console.error("Card price history fetch failed", error);
          showAlert(alertBox, error.message || "Nie udało się pobrać danych karty.", "error");
        }
        return null;
      });
    }

    requestCardInfo(DEFAULT_PRICE_RANGE)
      .then(({ data, range }) => {
        renderCardDetail(data?.card, {
          priceHistoryModule,
          priceHistoryRange: range,
        });
        renderRelatedCards(data?.related || []);
        showAlert(alertBox, "");
      })
      .catch((error) => {
        showAlert(alertBox, error.message || "Nie udało się pobrać danych karty.", "error");
      });

    const addButton = document.getElementById("detail-add-button");
    if (addButton) {
      addButton.addEventListener("click", () => {
        const redirect = new URL("/cards/add", window.location.origin);
        redirect.searchParams.set("name", name);
        redirect.searchParams.set("number", number);
        if (setName) redirect.searchParams.set("set_name", setName);
        if (setCode) redirect.searchParams.set("set_code", setCode);
        if (total) redirect.searchParams.set("total", total);
        window.location.href = redirect.toString();
      });
    }
  };

  const setupSettingsPage = async () => {
    const page = document.getElementById("settings-page");
    if (!page) return;

    const profileForm = document.getElementById("settings-profile-form");
    const passwordForm = document.getElementById("settings-password-form");
    const profileAlert = profileForm?.querySelector(".alert");
    const passwordAlert = passwordForm?.querySelector(".alert");

    const user = currentUser || (await fetchCurrentUser());
    if (profileForm) {
      const emailInput = profileForm.querySelector('input[name="email"]');
      const avatarInput = profileForm.querySelector('input[name="avatar_url"]');
      const avatarChoices = Array.from(
        profileForm.querySelectorAll('input[name="avatar_choice"]'),
      );

      const syncAvatarChoices = (value) => {
        if (!avatarChoices.length) return;
        const target = (value || "").trim();
        let matched = null;
        for (const radio of avatarChoices) {
          const url = (radio.dataset.url || "").trim();
          if (target && url && url === target) {
            matched = radio;
            break;
          }
        }
        avatarChoices.forEach((radio) => {
          const isCustom = radio.dataset.custom === "true";
          if (matched) {
            radio.checked = radio === matched;
          } else {
            radio.checked = isCustom;
          }
        });
      };

      if (user) {
        if (emailInput && user.email) {
          emailInput.value = user.email;
        }
        if (avatarInput && user.avatar_url) {
          avatarInput.value = user.avatar_url;
        }
      }

      if (avatarInput && avatarChoices.length) {
        avatarInput.addEventListener("input", () => {
          syncAvatarChoices(avatarInput.value);
        });
        avatarChoices.forEach((radio) => {
          radio.addEventListener("change", () => {
            const isCustom = radio.dataset.custom === "true";
            if (isCustom) {
              avatarInput.focus();
              return;
            }
            avatarInput.value = radio.dataset.url || "";
            syncAvatarChoices(avatarInput.value);
          });
        });
        syncAvatarChoices(avatarInput.value);
      }

      profileForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const payload = formToJSON(profileForm);
        const body = {
          email: payload.email ? String(payload.email).trim() || null : null,
          avatar_url: payload.avatar_url ? String(payload.avatar_url).trim() || null : null,
        };
        showAlert(profileAlert, "Zapisuję dane profilu…");
        try {
          const updated = await apiFetch("/users/me", {
            method: "PATCH",
            body: JSON.stringify(body),
          });
          currentUser = updated;
          updateUserBadge(updated);
          showAlert(profileAlert, "Profil został zaktualizowany.", "success");
        } catch (error) {
          showAlert(profileAlert, error.message || "Nie udało się zapisać profilu.", "error");
        }
      });
    }

    if (passwordForm) {
      passwordForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const payload = formToJSON(passwordForm);
        const body = {
          current_password: payload.current_password || "",
          new_password: payload.new_password || "",
        };
        showAlert(passwordAlert, "Aktualizuję hasło…");
        try {
          await apiFetch("/users/me", {
            method: "PATCH",
            body: JSON.stringify(body),
          });
          showAlert(passwordAlert, "Hasło zostało zaktualizowane.", "success");
          passwordForm.reset();
        } catch (error) {
          showAlert(passwordAlert, error.message || "Nie udało się zaktualizować hasła.", "error");
        }
      });
    }
  };

  initializeTheme();

  const init = async () => {
    setupNavigation();
    setupAuthForms();
    setupCollectionPage();
    setupPortfolioPage();
    setupAddCardPage();
    setupCardDetailPage();

    await fetchCurrentUser();

    const needsCollection = Boolean(document.getElementById("collection-table"));
    const needsPortfolio = Boolean(document.getElementById("portfolio-cards"));
    if (needsCollection || needsPortfolio) {
      await loadCollection();
    }

    await setupSettingsPage();
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
