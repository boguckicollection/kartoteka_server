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

  const showAlert = (element, message, variant = "info") => {
    if (!element) return;
    if (!message) {
      element.textContent = "";
      element.hidden = true;
      delete element.dataset.variant;
      return;
    }
    element.textContent = message;
    element.dataset.variant = variant;
    element.hidden = false;
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
      const hasSetIcon = Boolean(item.set_icon);
      const cardAlt = `Miniatura karty ${cardName}`;
      const setAlt = `Ikona dodatku ${setName}`;
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
      const rarityAlt = `Symbol rzadkości ${rarityText}`;
      const rarityFallback = rarityRaw ? rarityRaw.charAt(0).toUpperCase() : "?";
      if (isListView) {
        article.innerHTML = `
          <div class="card-search-info">
            <h3>${escapeHtml(cardName)}</h3>
            <div class="card-search-inline-fields">
              <span class="card-search-inline-field">
                <span class="card-search-inline-label">Numer</span>
                <span class="card-search-inline-value">${escapeHtml(numberLabel)}</span>
              </span>
              <span class="card-search-inline-field">
                <span class="card-search-inline-label">Dodatek</span>
                <span class="card-search-inline-value">${escapeHtml(setName)}</span>
              </span>
              <span class="card-search-inline-field">
                <span class="card-search-inline-label">Rzadkość</span>
                <span class="card-search-inline-value">${escapeHtml(rarityText)}</span>
              </span>
              ${
                priceText
                  ? `<span class="card-search-inline-field">
                      <span class="card-search-inline-label">Cena</span>
                      <span class="card-search-inline-value" data-card-price>${escapeHtml(priceText)}</span>
                    </span>`
                  : ""
              }
            </div>
          </div>
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
        `;
      } else {
        article.innerHTML = `
          <div class="card-search-media">
            <div class="card-search-thumbnail">
              ${
                hasThumbnail
                  ? `<img src="${escapeHtml(item.image_small)}" alt="${escapeHtml(cardAlt)}" loading="lazy" decoding="async" data-card-thumbnail />`
                  : ""
              }
              <div class="card-search-thumbnail-fallback"${hasThumbnail ? " hidden" : ""} data-card-thumbnail-fallback>
                Brak miniatury
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
            </div>
          <div class="card-search-set">
            <div class="card-search-set-icon">
              ${
                hasSetIcon
                  ? `<img src="${escapeHtml(item.set_icon)}" alt="${escapeHtml(setAlt)}" loading="lazy" decoding="async" data-card-set-icon />`
                  : ""
              }
              <span class="card-search-set-icon-fallback"${hasSetIcon ? " hidden" : ""} data-card-set-icon-fallback aria-hidden="true">?</span>
            </div>
            <div class="card-search-rarity-icon">
              ${
                raritySymbolIsImage
                  ? `<img src="${escapeHtml(raritySymbol)}" alt="${escapeHtml(rarityAlt)}" loading="lazy" decoding="async" data-card-rarity-icon />`
                  : hasRaritySymbol
                    ? `<span class="card-search-rarity-symbol" role="img" aria-label="${escapeHtml(rarityAlt)}" data-card-rarity-symbol data-symbol-class="${escapeHtml(raritySymbol)}"></span>`
                    : ""
              }
              <span class="card-search-rarity-icon-fallback"${hasRaritySymbol ? " hidden" : ""} data-card-rarity-icon-fallback aria-hidden="true">${escapeHtml(rarityFallback)}</span>
            </div>
          </div>
        </div>
        <div class="card-search-info">
          <h3>${escapeHtml(cardName)}</h3>
            <p>${escapeHtml(setName)}</p>
            <p class="card-search-meta">${escapeHtml(numberLabel)}</p>
            ${
              priceText
                ? `<p class="card-search-price" data-card-price>Cena: ${escapeHtml(priceText)}</p>`
                : ""
            }
          </div>
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
        const setIcon = article.querySelector("[data-card-set-icon]");
        const setIconFallback = article.querySelector("[data-card-set-icon-fallback]");
        if (setIcon && setIconFallback) {
          const handleSetIconError = () => {
            setIcon.remove();
            setIconFallback.hidden = false;
          };
          setIcon.addEventListener("error", handleSetIconError, { once: true });
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
        const raritySymbolElement = article.querySelector("[data-card-rarity-symbol]");
        if (raritySymbolElement) {
          const symbolClass = (raritySymbolElement.dataset.symbolClass || "").trim();
          if (symbolClass) {
            symbolClass
              .split(/\s+/)
              .map((token) => token.trim())
              .filter(Boolean)
              .forEach((token) => {
                raritySymbolElement.classList.add(token);
              });
          }
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
        await handleCardFormSubmission(formTarget, button);
      });
    }
  };

  const renderCardDetail = (card) => {
    if (!card) return;
    const title = document.getElementById("card-detail-title");
    if (title) {
      title.textContent = card.name || "Szczegóły karty";
    }
    const setName = document.getElementById("card-detail-set-name");
    if (setName) setName.textContent = card.set_name || "";
    const number = document.getElementById("card-detail-number");
    if (number) number.textContent = card.number_display || card.number || "";
    const rarity = document.getElementById("card-detail-rarity");
    if (rarity) rarity.textContent = card.rarity || "";
    const total = document.getElementById("card-detail-total");
    if (total) total.textContent = card.total || "";
    const release = document.getElementById("card-detail-release");
    if (release) release.textContent = card.release_date || "";

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
      anchor.href = `/cards/${encodeURIComponent(item.set_code || item.set_name || "")}/${encodeURIComponent(item.number)}?${params.toString()}`;
      anchor.innerHTML = `
        <span class="related-card-name">${escapeHtml(item.name)}</span>
        <span class="related-card-meta">${escapeHtml(item.set_name || "")}</span>
      `;
      container.appendChild(anchor);
    }
  };

  const setupCardDetailPage = () => {
    const container = document.getElementById("card-detail-page");
    if (!container) return;
    const alertBox = document.getElementById("card-detail-alert");
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

    apiFetch(`/cards/info?${params.toString()}`)
      .then((data) => {
        renderCardDetail(data?.card);
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
