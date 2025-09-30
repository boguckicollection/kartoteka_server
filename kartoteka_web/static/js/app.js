const TOKEN_KEY = "kartoteka_token";
const THEME_KEY = "kartoteka_theme";
const LIGHT_THEME_COLOR = "#f9fafb";
const DARK_THEME_COLOR = "#05060f";
let cachedCollectionEntries = [];

const getToken = () => window.localStorage.getItem(TOKEN_KEY);
const setToken = (token) => window.localStorage.setItem(TOKEN_KEY, token);
const clearToken = () => window.localStorage.removeItem(TOKEN_KEY);

function debounce(fn, delay = 250) {
  let timer;
  return (...args) => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => fn(...args), delay);
  };
}

function getStoredTheme() {
  try {
    return window.localStorage.getItem(THEME_KEY);
  } catch (error) {
    console.warn("Unable to read stored theme", error);
    return null;
  }
}

function applyTheme(theme) {
  const normalized = theme === "dark" ? "dark" : "light";
  const body = document.body;
  if (body) {
    body.dataset.theme = normalized;
  }
  const root = document.documentElement;
  if (root) {
    root.style.colorScheme = normalized;
  }
  const meta = document.querySelector("[data-theme-color]");
  if (meta) {
    const color = normalized === "dark" ? DARK_THEME_COLOR : LIGHT_THEME_COLOR;
    meta.setAttribute("content", color);
  }
  const toggle = document.querySelector("[data-theme-toggle]");
  if (toggle) {
    const icon = toggle.querySelector("span");
    const label = normalized === "dark" ? "Włącz jasny motyw" : "Włącz ciemny motyw";
    toggle.setAttribute("aria-label", label);
    if (icon) {
      icon.textContent = normalized === "dark" ? "☀️" : "🌙";
    }
  }
}

function determineTheme() {
  const stored = getStoredTheme();
  if (stored === "dark" || stored === "light") {
    return stored;
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function persistTheme(theme) {
  try {
    window.localStorage.setItem(THEME_KEY, theme);
  } catch (error) {
    console.warn("Unable to persist theme", error);
  }
}

function setupThemeToggle() {
  const initial = determineTheme();
  applyTheme(initial);
  const toggle = document.querySelector("[data-theme-toggle]");
  if (toggle) {
    toggle.addEventListener("click", () => {
      const current = document.body?.dataset.theme || initial;
      const next = current === "dark" ? "light" : "dark";
      persistTheme(next);
      applyTheme(next);
    });
  }
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  if (media && typeof media.addEventListener === "function") {
    media.addEventListener("change", (event) => {
      const stored = getStoredTheme();
      if (stored === "dark" || stored === "light") {
        return;
      }
      applyTheme(event.matches ? "dark" : "light");
    });
  }
}

const plnFormatter = new Intl.NumberFormat("pl-PL", {
  style: "currency",
  currency: "PLN",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function formatPln(value) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return null;
  }
  return plnFormatter.format(value);
}

function resolveTrendSymbol(direction) {
  if (direction === "up") {
    return "↑";
  }
  if (direction === "down") {
    return "↓";
  }
  return "→";
}

function updateUserBadge(user) {
  const payload =
    typeof user === "string"
      ? { username: user }
      : user && typeof user === "object"
        ? user
        : { username: "" };
  const username = payload.username ? String(payload.username).trim() : "";
  const avatarUrl = payload.avatar_url ? String(payload.avatar_url).trim() : "";
  const display = document.querySelector("[data-username-display]");
  const logoutButton = document.getElementById("logout-button");
  if (display) {
    display.textContent = username || "Gość";
    display.dataset.state = username ? "authenticated" : "anonymous";
  }
  const avatar = document.querySelector("[data-user-avatar]");
  if (avatar) {
    const initial = username ? username.charAt(0).toUpperCase() : "G";
    if (avatarUrl) {
      avatar.style.backgroundImage = `url(${avatarUrl})`;
      avatar.textContent = "";
    } else {
      avatar.style.backgroundImage = "";
      avatar.textContent = initial;
    }
    avatar.dataset.state = username ? "authenticated" : "anonymous";
  }
  const profileLink = document.querySelector("[data-user-profile-link]");
  if (profileLink) {
    profileLink.dataset.state = username ? "authenticated" : "anonymous";
    profileLink.setAttribute("aria-disabled", username ? "false" : "true");
  }
  const logout = logoutButton;
  if (logout) {
    logout.hidden = !username;
  }
  const loginButton = document.getElementById("login-button");
  if (loginButton) {
    loginButton.hidden = Boolean(username);
  }
}

function setupNavigation() {
  const nav = document.querySelector("[data-nav]");
  const toggle = document.querySelector("[data-nav-toggle]");
  if (nav && toggle) {
    if (!nav.dataset.open) {
      nav.dataset.open = "false";
    }
    const closeNav = () => {
      nav.dataset.open = "false";
      toggle.setAttribute("aria-expanded", "false");
    };
    toggle.addEventListener("click", () => {
      const isOpen = nav.dataset.open === "true";
      const nextState = String(!isOpen);
      nav.dataset.open = nextState;
      toggle.setAttribute("aria-expanded", nextState);
    });
    nav.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", () => closeNav());
    });
    document.addEventListener("click", (event) => {
      if (!nav.contains(event.target) && !toggle.contains(event.target)) {
        closeNav();
      }
    });
  }

  const logoutButton = document.getElementById("logout-button");
  if (logoutButton) {
    logoutButton.addEventListener("click", () => {
      clearToken();
      updateUserBadge({ username: "" });
      window.location.href = "/login";
    });
  }

  const initialUsername = document.body?.dataset.username ?? "";
  const initialAvatar = document.body?.dataset.avatar ?? "";
  updateUserBadge({ username: initialUsername, avatar_url: initialAvatar });
}

function setupHeaderVisibility() {
  const header = document.querySelector("header.app-header");
  if (!header) {
    return;
  }

  const setHeaderVisibility = (visible) => {
    header.dataset.headerVisible = visible ? "true" : "false";
  };

  setHeaderVisibility(true);

  let lastKnownScrollY = window.scrollY;
  let ticking = false;
  const threshold = 4;

  const updateVisibility = () => {
    const currentScrollY = Math.max(window.scrollY, 0);
    const atTop = currentScrollY <= 0;

    if (atTop) {
      setHeaderVisibility(true);
    } else if (currentScrollY > lastKnownScrollY + threshold) {
      setHeaderVisibility(false);
    } else if (currentScrollY < lastKnownScrollY - threshold) {
      setHeaderVisibility(true);
    }

    lastKnownScrollY = currentScrollY;
    ticking = false;
  };

  const requestTick = () => {
    if (!ticking) {
      window.requestAnimationFrame(updateVisibility);
      ticking = true;
    }
  };

  const resetVisibility = () => {
    lastKnownScrollY = window.scrollY;
    setHeaderVisibility(true);
    requestTick();
  };

  window.addEventListener("scroll", requestTick, { passive: true });
  window.addEventListener("resize", resetVisibility);
  window.addEventListener("orientationchange", resetVisibility);

  requestTick();
}

async function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) {
    return;
  }
  try {
    await navigator.serviceWorker.register("/static/service-worker.js", { scope: "/" });
  } catch (error) {
    console.warn("Service worker registration failed", error);
  }
}

async function apiFetch(path, options = {}) {
  const headers = options.headers ? { ...options.headers } : {};
  if (!headers["Content-Type"] && options.body) {
    headers["Content-Type"] = "application/json";
  }
  const token = getToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const response = await fetch(path, { ...options, headers });
  if (response.status === 204) {
    return null;
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = data.detail || "Wystąpił błąd.";
    throw new Error(message);
  }
  return data;
}

const alertHideTimers = new WeakMap();
const TOAST_TRANSITION_MS = 300;

function hideToast(element) {
  element.dataset.visible = "false";
  window.setTimeout(() => {
    element.hidden = true;
    element.textContent = "";
    delete element.dataset.variant;
    element.removeAttribute("data-visible");
  }, TOAST_TRANSITION_MS);
}

function showAlert(element, message, type = "error") {
  if (!element) return;

  const pendingTimer = alertHideTimers.get(element);
  if (pendingTimer) {
    window.clearTimeout(pendingTimer);
    alertHideTimers.delete(element);
  }

  element.classList.remove("success", "error");

  if (!message) {
    if (element.id === "add-card-alert") {
      hideToast(element);
    } else {
      element.textContent = "";
      element.hidden = true;
      delete element.dataset.variant;
      element.removeAttribute("data-visible");
    }
    return;
  }

  element.textContent = message;
  element.hidden = false;
  element.dataset.variant = type;

  if (element.id === "add-card-alert") {
    element.dataset.visible = "true";
    if (type === "success") {
      const timeoutId = window.setTimeout(() => {
        hideToast(element);
        alertHideTimers.delete(element);
      }, 4000);
      alertHideTimers.set(element, timeoutId);
    }
  }
}

function formToJSON(form) {
  const data = new FormData(form);
  const result = {};
  for (const [key, value] of data.entries()) {
    if (value === "on") {
      result[key] = true;
    } else if (value === "") {
      result[key] = undefined;
    } else {
      result[key] = value;
    }
  }
  return result;
}

function slugifyIdentifier(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    || "unknown";
}

function extractCardTotal(card) {
  if (!card) return "";
  if (card.total) {
    return String(card.total);
  }
  const display = card.number_display || "";
  if (display.includes("/")) {
    const [, totalPart] = display.split("/", 2);
    return totalPart ? totalPart.trim() : "";
  }
  return "";
}

function buildCardDetailUrl(card) {
  if (!card) return "/dashboard";
  const number = encodeURIComponent(card.number || "");
  const setCode = (card.set_code || "").trim();
  const setName = card.set_name || "";
  const slug = setCode ? encodeURIComponent(setCode.toLowerCase()) : encodeURIComponent(slugifyIdentifier(setName));
  const params = new URLSearchParams();
  if (card.name) params.set("name", card.name);
  if (setName) params.set("set_name", setName);
  const total = extractCardTotal(card);
  if (total) params.set("total", total);
  const query = params.toString();
  return `/cards/${slug}/${number}${query ? `?${query}` : ""}`;
}

function buildAddCardUrl(card) {
  if (!card) return "/cards/add";
  const params = new URLSearchParams();
  if (card.name) params.set("name", card.name);
  if (card.number) params.set("number", card.number);
  if (card.set_name) params.set("set_name", card.set_name);
  if (card.set_code) params.set("set_code", card.set_code);
  const total = extractCardTotal(card);
  if (total) params.set("total", total);
  const query = params.toString();
  return `/cards/add${query ? `?${query}` : ""}`;
}

function resolveRaritySymbol(rarity) {
  if (!rarity) {
    return "";
  }
  const value = String(rarity).trim();
  if (!value) {
    return "";
  }
  const normalised = value.toLowerCase();
  if (normalised.includes("common")) {
    return "●";
  }
  if (normalised.includes("uncommon")) {
    return "◆";
  }
  if (
    normalised.includes("rare") ||
    normalised.includes("promo") ||
    normalised.includes("secret")
  ) {
    return "★";
  }
  return "";
}

function formatRarityLabel(rarity) {
  if (!rarity) {
    return "";
  }
  const symbol = resolveRaritySymbol(rarity);
  return symbol ? `${symbol} ${rarity}` : rarity;
}

function formatCardNumber(card) {
  if (!card) return "";
  if (card.number_display) {
    return card.number_display;
  }
  if (card.number && card.total) {
    return `${card.number}/${card.total}`;
  }
  return card.number || "";
}

async function handleLogin(form) {
  const alertBox = document.getElementById("login-alert");
  showAlert(alertBox, "");
  try {
    const payload = formToJSON(form);
    const data = await apiFetch("/users/login", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    setToken(data.access_token);
    window.location.href = "/dashboard";
  } catch (error) {
    showAlert(alertBox, error.message);
  }
}

async function handleRegister(form) {
  const alertBox = document.getElementById("register-alert");
  showAlert(alertBox, "");
  try {
    const payload = formToJSON(form);
    await apiFetch("/users/register", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    showAlert(alertBox, "Konto utworzone. Możesz się zalogować.", "success");
    form.reset();
  } catch (error) {
    showAlert(alertBox, error.message);
  }
}

function renderCollection(entries) {
  const body = document.getElementById("collection-table");
  cachedCollectionEntries = Array.isArray(entries) ? entries : [];
  if (!body) return;
  body.innerHTML = "";
  if (!entries.length) {
    const emptyRow = document.createElement("tr");
    emptyRow.innerHTML = `<td colspan="5" class="table-empty">Brak kart w kolekcji. Dodaj pierwszą kartę, aby rozpocząć.</td>`;
    body.appendChild(emptyRow);
    return;
  }
  for (const entry of entries) {
    const tr = document.createElement("tr");
    const purchaseValue =
      typeof entry.purchase_price === "number"
        ? entry.purchase_price.toFixed(2)
        : entry.purchase_price ?? "-";
    const detailUrl = buildCardDetailUrl(entry.card || {});
    tr.innerHTML = `
      <td data-label="Nazwa"><a class="table-link" href="${detailUrl}">${entry.card.name}</a></td>
      <td data-label="Numer">${entry.card.number}</td>
      <td data-label="Set">${entry.card.set_name}</td>
      <td data-label="Ilość">${entry.quantity}</td>
      <td data-label="Cena zakupu">${purchaseValue}</td>
      <td data-label="Akcje">
        <div class="table-actions">
          <button class="ghost danger" data-action="delete" data-id="${entry.id}">Usuń</button>
        </div>
      </td>
    `;
    body.appendChild(tr);
  }
}

function renderPortfolio(entries) {
  const container = document.getElementById("portfolio-cards");
  const empty = document.getElementById("portfolio-empty");
  if (!container) return;
  container.innerHTML = "";
  if (!Array.isArray(entries) || !entries.length) {
    if (empty) empty.hidden = false;
    return;
  }
  if (empty) empty.hidden = true;
  const fragment = document.createDocumentFragment();
  entries.forEach((entry) => {
    const card = entry.card || {};
    const article = document.createElement("article");
    article.className = "portfolio-card";
    const link = document.createElement("a");
    link.href = buildCardDetailUrl(card);
    link.className = "portfolio-card-link";

    const media = document.createElement("div");
    media.className = "portfolio-card-media";
    const imageSource = card.image_small || card.image_large;
    if (imageSource) {
      const img = document.createElement("img");
      img.src = imageSource;
      img.alt = `Podgląd ${card.name || "karty"}`;
      img.loading = "lazy";
      img.className = "portfolio-card-image";
      media.appendChild(img);
    } else {
      const placeholder = document.createElement("div");
      placeholder.className = "portfolio-card-placeholder";
      placeholder.textContent = "🃏";
      placeholder.setAttribute("aria-hidden", "true");
      media.appendChild(placeholder);
    }
    link.appendChild(media);

    const body = document.createElement("div");
    body.className = "portfolio-card-body";

    if (card.set_name) {
      const setInfo = document.createElement("div");
      setInfo.className = "portfolio-card-set";
      const setName = document.createElement("span");
      setName.textContent = card.set_name;
      setInfo.appendChild(setName);
      body.appendChild(setInfo);
    }

    const title = document.createElement("h3");
    title.className = "portfolio-card-title";
    title.textContent = card.name || "";
    body.appendChild(title);

    const meta = document.createElement("p");
    meta.className = "portfolio-card-meta";
    const numberText = formatCardNumber(card);
    const rarity = card.rarity ? String(card.rarity) : "";
    const quantity = entry.quantity ? `x${entry.quantity}` : "";
    meta.textContent = [numberText, rarity, quantity].filter(Boolean).join(" • ");
    body.appendChild(meta);

    const purchase = document.createElement("p");
    purchase.className = "portfolio-card-value";
    if (typeof entry.purchase_price === "number") {
      purchase.textContent = `Cena zakupu: ${entry.purchase_price.toFixed(2)} PLN`;
    } else {
      purchase.textContent = "Cena zakupu: -";
    }
    body.appendChild(purchase);

    link.appendChild(body);
    article.appendChild(link);
    fragment.appendChild(article);
  });
  container.appendChild(fragment);
}

function renderPortfolioPerformance() {
  const chartContainer = document.getElementById("portfolio-chart");
  if (chartContainer) {
    chartContainer.innerHTML = "";
    const message = document.createElement("p");
    message.className = "portfolio-chart-empty";
    message.textContent = "Historia wartości jest niedostępna w uproszczonym trybie.";
    chartContainer.appendChild(message);
  }

  const changeWrapper = document.getElementById("portfolio-change");
  if (changeWrapper) {
    changeWrapper.dataset.direction = "flat";
    const icon = changeWrapper.querySelector(".portfolio-change-icon");
    if (icon) {
      icon.textContent = resolveTrendSymbol("flat");
    }
  }

  const changeValue = document.getElementById("portfolio-change-value");
  if (changeValue) {
    changeValue.textContent = plnFormatter.format(0);
  }

  const latestValueElement = document.getElementById("portfolio-chart-latest");
  if (latestValueElement) {
    latestValueElement.textContent = "—";
    latestValueElement.dataset.direction = "flat";
  }

  const minValueElement = document.getElementById("portfolio-chart-min");
  if (minValueElement) {
    minValueElement.textContent = "—";
  }

  const maxValueElement = document.getElementById("portfolio-chart-max");
  if (maxValueElement) {
    maxValueElement.textContent = "—";
  }

  const rangeElement = document.getElementById("portfolio-chart-range");
  if (rangeElement) {
    rangeElement.textContent = "Brak danych";
  }

  const totalValueElement = document.getElementById("portfolio-value");
  if (totalValueElement) {
    totalValueElement.dataset.direction = "flat";
  }

  const summaryValueElement = document.getElementById("summary-value");
  if (summaryValueElement) {
    summaryValueElement.dataset.direction = "flat";
  }
}

function updateSummary(entries) {
  const collection = Array.isArray(entries) ? entries : [];
  const totalCards = collection.length;
  const totalQuantity = collection.reduce((acc, entry) => acc + (Number(entry.quantity) || 0), 0);
  const totalPurchase = collection.reduce((acc, entry) => {
    if (typeof entry.purchase_price === "number") {
      return acc + entry.purchase_price * (Number(entry.quantity) || 1);
    }
    return acc;
  }, 0);

  const count = document.getElementById("summary-count");
  const quantity = document.getElementById("summary-quantity");
  const value = document.getElementById("summary-value");
  if (count) count.textContent = totalCards;
  if (quantity) quantity.textContent = totalQuantity;
  if (value) {
    const formatted = formatPln(totalPurchase);
    value.textContent = formatted || totalPurchase.toFixed(2);
    value.dataset.direction = "flat";
  }

  const pCount = document.getElementById("portfolio-count");
  const pQuantity = document.getElementById("portfolio-quantity");
  const pValue = document.getElementById("portfolio-value");
  if (pCount) pCount.textContent = totalCards;
  if (pQuantity) pQuantity.textContent = totalQuantity;
  if (pValue) {
    const formatted = formatPln(totalPurchase);
    pValue.textContent = formatted || totalPurchase.toFixed(2);
    pValue.dataset.direction = "flat";
  }
}

async function loadCollection() {
  try {
    const entries = await apiFetch("/cards/");
    renderCollection(entries);
    renderPortfolio(entries);
    updateSummary(entries);
  } catch (error) {
    console.error(error);
  }
}

async function loadPortfolioHistory(targetAlert) {
  renderPortfolioPerformance();
  if (targetAlert) {
    showAlert(targetAlert, "");
  }
}

async function loadSummary(targetAlert) {
  updateSummary(cachedCollectionEntries);
  if (targetAlert) {
    showAlert(targetAlert, "");
  }
}

async function loadPortfolioCards(targetAlert) {
  renderPortfolio(cachedCollectionEntries);
  if (targetAlert) {
    showAlert(targetAlert, "");
  }
}

function setupCardSearch(form) {
  if (!form) return null;
  const queryInput = form.querySelector('input[name="query"]');
  const rarityInput = form.querySelector('input[name="rarity"]');
  const resultsSection = document.getElementById("card-search-results-section");
  const resultsContainer = document.getElementById("card-search-results");
  const summary = document.getElementById("card-search-summary");
  const statusMessage = document.getElementById("card-search-empty");
  const sortSelect = document.getElementById("card-search-sort");
  const hintElement = document.getElementById("card-search-hint");

  if (!queryInput || !resultsSection || !resultsContainer) {
    return null;
  }

  const eventTarget = form;
  let selectedCard = null;
  let selectedKey = "";
  let requestId = 0;
  let cardSearchApi = null;

  const state = {
    items: [],
    total: 0,
    sortMode: sortSelect?.value || "relevance",
    suggestedQuery: "",
    lastQuery: "",
  };

  const buildResultKey = (card) => {
    const setCode = card?.set_code ?? "";
    const setName = card?.set_name ?? "";
    const number = card?.number ?? "";
    const name = card?.name ?? "";
    return [setCode, setName, number, name].join("|");
  };

  const formatResultsCount = (count) => {
    if (count === 1) {
      return "Znaleziono 1 kartę";
    }
    const mod10 = count % 10;
    const mod100 = count % 100;
    if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) {
      return `Znaleziono ${count} karty`;
    }
    return `Znaleziono ${count} kart`;
  };

  const updateSummary = (count) => {
    if (!summary) return;
    if (count > 0) {
      summary.textContent = formatResultsCount(count);
      summary.hidden = false;
    } else {
      summary.textContent = "";
      summary.hidden = true;
    }
  };

  const updateStatus = (message = "", stateAttr = "") => {
    if (!statusMessage) return;
    if (message) {
      statusMessage.textContent = message;
      statusMessage.hidden = false;
      if (stateAttr) {
        statusMessage.dataset.state = stateAttr;
      } else {
        delete statusMessage.dataset.state;
      }
    } else {
      statusMessage.textContent = "";
      statusMessage.hidden = true;
      delete statusMessage.dataset.state;
    }
  };

  const updateSearchHint = () => {
    if (!hintElement || !queryInput) {
      return;
    }
    const suggestion = (state.suggestedQuery || "").trim();
    const query = queryInput.value.trim();
    const hasQueryMatch = Boolean(query && state.lastQuery && query === state.lastQuery);
    const isSameText =
      suggestion && query
        ? suggestion.localeCompare(query, undefined, { sensitivity: "accent" }) === 0
        : false;
    const shouldShow = Boolean(suggestion && hasQueryMatch && !selectedCard && !isSameText);
    if (shouldShow) {
      hintElement.textContent = `Może chodziło Ci o: ${suggestion}`;
      hintElement.hidden = false;
      queryInput.setAttribute("data-hint-active", "true");
    } else {
      hintElement.textContent = "";
      hintElement.hidden = true;
      queryInput.removeAttribute("data-hint-active");
    }
  };

  const compareText = (left, right) =>
    String(left || "").localeCompare(String(right || ""), undefined, { sensitivity: "base" });

  const parseCardNumberValue = (card) => {
    const raw = String(card?.number || card?.number_display || "");
    const match = raw.match(/\d+/);
    if (!match) {
      return Number.NaN;
    }
    const value = Number.parseInt(match[0], 10);
    return Number.isNaN(value) ? Number.NaN : value;
  };

  const compareNumberAsc = (a, b) => {
    const valueA = parseCardNumberValue(a);
    const valueB = parseCardNumberValue(b);
    const aIsNaN = Number.isNaN(valueA);
    const bIsNaN = Number.isNaN(valueB);
    if (!aIsNaN && !bIsNaN && valueA !== valueB) {
      return valueA - valueB;
    }
    if (aIsNaN && !bIsNaN) {
      return 1;
    }
    if (!aIsNaN && bIsNaN) {
      return -1;
    }
    return compareText(a?.number || a?.number_display, b?.number || b?.number_display);
  };

  const comparators = {
    name_asc: (a, b) => compareText(a?.name, b?.name),
    name_desc: (a, b) => compareText(b?.name, a?.name),
    number_asc: compareNumberAsc,
    number_desc: (a, b) => compareNumberAsc(b, a),
    set_asc: (a, b) => compareText(a?.set_name, b?.set_name),
    set_desc: (a, b) => compareText(b?.set_name, a?.set_name),
  };

  const getSortedResults = () => {
    const base = [...state.items];
    const comparator = state.sortMode ? comparators[state.sortMode] : null;
    if (comparator) {
      base.sort(comparator);
    }
    return base;
  };

  const updateSelectionHighlight = () => {
    const items = resultsContainer.querySelectorAll("[data-result-key]");
    items.forEach((item) => {
      if (!(item instanceof HTMLElement)) {
        return;
      }
      if (selectedKey && item.dataset.resultKey === selectedKey) {
        item.classList.add("is-selected");
      } else {
        item.classList.remove("is-selected");
      }
    });
  };

  const updateSortDisabled = () => {
    if (sortSelect) {
      sortSelect.disabled = state.total <= 1;
    }
  };

  const createResultItem = (card) => {
    const item = document.createElement("article");
    item.className = "card-search-item";
    item.dataset.resultKey = buildResultKey(card);
    item.setAttribute("role", "listitem");

    const cardName = card?.name?.trim() || "Nieznana karta";

    const link = document.createElement("a");
    link.className = "card-search-link";
    link.href = buildCardDetailUrl(card);
    link.setAttribute("aria-label", `Przejdź do szczegółów karty ${cardName}`);

    const media = document.createElement("div");
    media.className = "card-search-thumb-wrapper";
    if (card.image_small || card.image_large) {
      const img = document.createElement("img");
      img.className = "card-search-thumb";
      img.src = card.image_small || card.image_large;
      img.alt = card.name ? `Podgląd ${card.name}` : "Podgląd karty";
      img.loading = "lazy";
      media.appendChild(img);
    } else {
      const placeholder = document.createElement("div");
      placeholder.className = "card-search-thumb placeholder";
      placeholder.textContent = "🃏";
      placeholder.setAttribute("aria-hidden", "true");
      media.appendChild(placeholder);
    }

    const addButton = document.createElement("button");
    addButton.type = "button";
    addButton.className = "card-search-add-button";
    addButton.textContent = "+";
    addButton.title = `Dodaj ${cardName} do kolekcji`;
    addButton.setAttribute("aria-label", `Dodaj kartę ${cardName} do kolekcji`);
    addButton.addEventListener("click", async (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (addButton.disabled) {
        return;
      }
      addButton.disabled = true;
      addButton.dataset.loading = "true";
      try {
        await addCard(form, cardSearchApi, card);
      } finally {
        addButton.disabled = false;
        delete addButton.dataset.loading;
      }
    });
    media.appendChild(addButton);
    link.appendChild(media);

    const info = document.createElement("div");
    info.className = "card-search-info";

    const title = document.createElement("h3");
    title.className = "card-search-title";
    title.textContent = cardName;
    info.appendChild(title);

    const numberMeta = document.createElement("p");
    numberMeta.className = "card-search-number";
    numberMeta.textContent = formatCardNumber(card) || card.number || "Brak numeru";
    info.appendChild(numberMeta);

    const setMeta = document.createElement("p");
    setMeta.className = "card-search-set";
    const setText = document.createElement("span");
    setText.textContent = card.set_name || "Brak informacji o secie";
    setMeta.appendChild(setText);
    info.appendChild(setMeta);

    link.appendChild(info);
    item.appendChild(link);

    item.addEventListener("click", (event) => {
      const target = event.target;
      if (target instanceof HTMLElement && target.closest(".card-search-add-button")) {
        return;
      }
      applySuggestion(card);
    });

    return item;
  };

  const renderResults = () => {
    const sorted = getSortedResults();
    resultsContainer.innerHTML = "";
    if (!sorted.length) {
      resultsContainer.hidden = true;
    } else {
      const fragment = document.createDocumentFragment();
      sorted.forEach((card) => {
        fragment.appendChild(createResultItem(card));
      });
      resultsContainer.hidden = false;
      resultsContainer.appendChild(fragment);
    }

    updateSelectionHighlight();
  };

  const clearSelection = () => {
    selectedCard = null;
    selectedKey = "";
    if (rarityInput) {
      rarityInput.value = "";
    }
    updateSelectionHighlight();
    eventTarget.dispatchEvent(new Event("cardsearch:clear"));
    updateSearchHint();
  };

  const applySuggestion = (card) => {
    selectedCard = card;
    selectedKey = buildResultKey(card);
    const numberLabel = formatCardNumber(card) || card.number || "";
    const queryParts = [card.name || "", numberLabel].filter(Boolean);
    queryInput.value = queryParts.join(" ").trim();
    if (rarityInput) {
      rarityInput.value = card.rarity || "";
    }
    updateSelectionHighlight();
    eventTarget.dispatchEvent(new CustomEvent("cardsearch:select", { detail: { card } }));
    updateSearchHint();
  };

  const loadResults = async () => {
    const query = queryInput.value.trim();
    if (!query) {
      state.items = [];
      state.total = 0;
      state.lastQuery = "";
      state.suggestedQuery = "";
      updateSummary(0);
      updateStatus("");
      resultsContainer.innerHTML = "";
      resultsContainer.hidden = true;
      if (resultsSection) {
        resultsSection.hidden = true;
      }
      updateSortDisabled();
      updateSearchHint();
      return [];
    }

    clearSelection();

    const params = new URLSearchParams({
      query,
    });

    const currentRequest = ++requestId;
    state.sortMode = sortSelect?.value || state.sortMode || "relevance";
    if (resultsSection) {
      resultsSection.hidden = false;
    }
    updateSummary(0);
    updateStatus("Wyszukiwanie kart...", "loading");
    resultsContainer.innerHTML = "";
    resultsContainer.hidden = true;
    updateSortDisabled();

    try {
      const payload = await apiFetch(`/cards/search?${params.toString()}`);
      if (currentRequest !== requestId) {
        return [];
      }

      const responseItems = Array.isArray(payload?.items) ? payload.items : [];
      const responseTotal = Number.isFinite(payload?.total)
        ? Math.max(0, Number(payload.total))
        : responseItems.length;
      state.items = responseItems;
      state.total = responseTotal;
      state.lastQuery = query;
      const payloadSuggestion =
        typeof payload?.suggested_query === "string" ? payload.suggested_query.trim() : "";
      if (payloadSuggestion) {
        state.suggestedQuery = payloadSuggestion;
      } else {
        const fallback = responseItems.find(
          (item) => typeof item?.name === "string" && item.name.trim()
        );
        state.suggestedQuery = fallback?.name?.trim() || "";
      }

      renderResults();
      updateSortDisabled();
      updateSummary(state.total);
      if (!state.total) {
        updateStatus("Nie znaleziono kart dla podanych kryteriów.");
      } else {
        updateStatus("");
      }
      eventTarget.dispatchEvent(
        new CustomEvent("cardsearch:results", { detail: { count: state.total } })
      );
      updateSearchHint();
      return state.items;
    } catch (error) {
      if (currentRequest !== requestId) {
        return [];
      }
      state.items = [];
      state.total = 0;
      state.lastQuery = "";
      state.suggestedQuery = "";
      renderResults();
      updateSummary(0);
      updateStatus(error.message || "Nie udało się pobrać wyników.", "error");
      updateSortDisabled();
      eventTarget.dispatchEvent(new CustomEvent("cardsearch:results", { detail: { count: 0 } }));
      updateSearchHint();
      throw error;
    }
  };

  const search = () => {
    clearSelection();
    return loadResults();
  };

  const handleInputChange = () => {
    clearSelection();
    state.lastQuery = "";
    updateSearchHint();
  };

  queryInput.addEventListener("input", handleInputChange);

  sortSelect?.addEventListener("change", () => {
    state.sortMode = sortSelect.value || "relevance";
    renderResults();
  });

  updateSortDisabled();

  const api = {
    getSelectedCard: () => selectedCard,
    clearSelection: () => {
      clearSelection();
    },
    reset: () => {
      clearSelection();
      state.items = [];
      state.total = 0;
      state.lastQuery = "";
      state.suggestedQuery = "";
      updateSummary(0);
      updateStatus("");
      resultsContainer.innerHTML = "";
      resultsContainer.hidden = true;
      if (resultsSection) {
        resultsSection.hidden = true;
      }
      updateSortDisabled();
      updateSearchHint();
    },
    search,
  };
  cardSearchApi = api;
  return api;
}

async function addCard(form, cardSearch, selectedCardOverride = null) {
  const alertBox = document.getElementById("add-card-alert");
  showAlert(alertBox, "");
  const selectedCard = selectedCardOverride ?? cardSearch?.getSelectedCard?.();
  if (!selectedCard) {
    showAlert(alertBox, "Najpierw wyszukaj kartę i wybierz ją z listy wyników.");
    return;
  }
  const data = formToJSON(form);
  if (!data.name) data.name = selectedCard.name;
  if (!data.number) data.number = selectedCard.number;
  if (!data.set_name) data.set_name = selectedCard.set_name;
  if (!data.set_code) data.set_code = selectedCard.set_code;
  if (data.rarity === undefined && selectedCard.rarity) {
    data.rarity = selectedCard.rarity;
  }
  const numberValue = String(data.number ?? "");
  const numberParts = numberValue.includes("/")
    ? numberValue.split("/", 1)[0]
    : numberValue;
  const payload = {
    quantity: Number(data.quantity) || 1,
    purchase_price: data.purchase_price ? Number(data.purchase_price) : undefined,
    is_reverse: Boolean(data.is_reverse),
    is_holo: Boolean(data.is_holo),
    card: {
      name: data.name,
      number: numberParts.trim(),
      set_name: data.set_name,
      set_code: data.set_code || null,
    },
  };
  if (data.rarity !== undefined) {
    payload.card.rarity = data.rarity || undefined;
  }
  if (selectedCard.image_small) {
    payload.card.image_small = selectedCard.image_small;
  }
  if (selectedCard.image_large) {
    payload.card.image_large = selectedCard.image_large;
  }
  try {
    await apiFetch("/cards/", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    const shouldResetSearch = !selectedCardOverride;
    if (shouldResetSearch) {
      form.reset();
      cardSearch?.reset?.();
    } else {
      cardSearch?.clearSelection?.();
    }
    const hasCollection = document.getElementById("collection-table");
    const hasSummary = document.getElementById("summary-count");
    if (hasCollection) {
      await loadCollection();
      if (!hasSummary && document.getElementById("summary-count")) {
        await loadSummary();
      }
    } else if (hasSummary) {
      await loadSummary();
    }
    showAlert(alertBox, "Karta została dodana do kolekcji.", "success");
  } catch (error) {
    showAlert(alertBox, error.message);
  }
}

async function deleteEntry(id) {
  await apiFetch(`/cards/${id}`, { method: "DELETE" });
  await loadCollection();
  await loadSummary();
}

function renderRelatedCardsList(cards) {
  const container = document.getElementById("related-cards-list");
  const empty = document.getElementById("related-empty");
  if (!container) return;
  container.innerHTML = "";
  if (empty) {
    empty.textContent = "Nie znaleziono innych kart z tą postacią.";
  }
  if (!Array.isArray(cards) || !cards.length) {
    if (empty) empty.hidden = false;
    return;
  }
  if (empty) empty.hidden = true;
  const fragment = document.createDocumentFragment();
  cards.forEach((card) => {
    const article = document.createElement("article");
    article.className = "related-card";
    const link = document.createElement("a");
    link.href = buildCardDetailUrl(card);

    if (card.image_small || card.image_large) {
      const img = document.createElement("img");
      img.className = "related-card-image";
      img.src = card.image_small || card.image_large;
      img.alt = `Podgląd ${card.name}`;
      img.loading = "lazy";
      link.appendChild(img);
    } else {
      const placeholder = document.createElement("div");
      placeholder.className = "related-card-image related-card-placeholder";
      placeholder.textContent = "🃏";
      placeholder.setAttribute("aria-hidden", "true");
      link.appendChild(placeholder);
    }

    const body = document.createElement("div");
    body.className = "related-card-body";

    if (card.set_name) {
      const setWrapper = document.createElement("div");
      setWrapper.className = "related-card-set";
      const setName = document.createElement("span");
      setName.textContent = card.set_name;
      setWrapper.appendChild(setName);
      body.appendChild(setWrapper);
    }

    const title = document.createElement("h3");
    title.className = "related-card-title";
    title.textContent = card.name || "";
    body.appendChild(title);

    const meta = document.createElement("p");
    meta.className = "related-card-meta";
    const numberText = formatCardNumber(card);
    const rarity = card.rarity ? String(card.rarity) : "";
    meta.textContent = [numberText ? `Nr ${numberText}` : "", rarity].filter(Boolean).join(" • ");
    body.appendChild(meta);

    link.appendChild(body);
    article.appendChild(link);
    fragment.appendChild(article);
  });
  container.appendChild(fragment);
}

function updateCardDetailImage(image, placeholder, card) {
  if (!image) {
    return;
  }
  const showPlaceholder = () => {
    image.hidden = true;
    image.setAttribute("hidden", "");
    if (placeholder) {
      placeholder.hidden = false;
    }
  };
  const showImage = () => {
    image.hidden = false;
    image.removeAttribute("hidden");
    if (placeholder) {
      placeholder.hidden = true;
    }
  };
  const imageSource = card?.image_large || card?.image_small || "";
  const cardName = card?.name ? String(card.name).trim() : "";
  const altText = cardName ? `Podgląd karty ${cardName}` : "Podgląd karty";
  image.alt = altText;
  if (!imageSource) {
    image.removeAttribute("src");
    image.onload = null;
    image.onerror = null;
    showPlaceholder();
    return;
  }

  const handleLoad = () => {
    showImage();
  };
  const handleError = () => {
    image.removeAttribute("src");
    showPlaceholder();
  };

  image.onload = handleLoad;
  image.onerror = handleError;

  if (image.src !== imageSource) {
    showPlaceholder();
    image.src = imageSource;
  }

  if (image.complete && image.naturalWidth > 0) {
    handleLoad();
  } else {
    showPlaceholder();
  }
}

async function addDetailCardToCollection(card, button) {
  const alertBox = document.getElementById("card-detail-alert");
  showAlert(alertBox, "");
  if (!card || !card.name || !card.number || !card.set_name) {
    showAlert(alertBox, "Brakuje danych karty. Spróbuj ponownie później.");
    return;
  }
  try {
    if (button) {
      button.dataset.loading = "true";
      button.disabled = true;
    }
    const payload = {
      quantity: 1,
      card: {
        name: card.name,
        number: card.number,
        set_name: card.set_name,
        set_code: card.set_code || null,
      },
    };
    if (card.rarity) {
      payload.card.rarity = card.rarity;
    }
    if (card.image_small) {
      payload.card.image_small = card.image_small;
    }
    if (card.image_large) {
      payload.card.image_large = card.image_large;
    }
    await apiFetch("/cards/", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    const hasCollection = document.getElementById("collection-table");
    const hasSummary = document.getElementById("summary-count");
    if (hasCollection) {
      await loadCollection();
      if (!hasSummary && document.getElementById("summary-count")) {
        await loadSummary();
      }
    } else if (hasSummary) {
      await loadSummary();
    }
    showAlert(alertBox, "Karta została dodana do kolekcji.", "success");
  } catch (error) {
    showAlert(alertBox, error.message);
  } finally {
    if (button) {
      button.disabled = false;
      delete button.dataset.loading;
    }
  }
}

async function loadCardDetail(container) {
  const alertBox = document.getElementById("card-detail-alert");
  showAlert(alertBox, "");
  const params = new URLSearchParams();
  const name = container.dataset.name?.trim();
  const number = container.dataset.number?.trim();
  const setCode = container.dataset.setCode?.trim();
  const setName = container.dataset.setName?.trim();
  const total = container.dataset.total?.trim();
  if (name) params.set("name", name);
  if (number) params.set("number", number);
  if (setCode) params.set("set_code", setCode);
  if (setName) params.set("set_name", setName);
  if (total) params.set("total", total);

  try {
    const detail = await apiFetch(`/cards/info?${params.toString()}`);
    const card = { ...(detail.card || {}) };
    if (!card.name && container.dataset.name) {
      card.name = container.dataset.name.trim();
    }
    if (!card.number && container.dataset.number) {
      card.number = container.dataset.number.trim();
    }
    if (!card.set_name && container.dataset.setName) {
      card.set_name = container.dataset.setName.trim();
    }
    if (!card.set_code && container.dataset.setCode) {
      card.set_code = container.dataset.setCode.trim();
    }
    if (!card.total && container.dataset.total) {
      card.total = container.dataset.total.trim();
    }
    renderRelatedCardsList(detail.related || []);

    const fallbackTitle = container.dataset.name?.trim() || "Szczegóły karty";
    const title = document.getElementById("card-detail-title");
    if (title) {
      title.textContent = card.name || fallbackTitle;
    }
    document.title = `${card.name || fallbackTitle} - Kartoteka`;

    const era = document.getElementById("card-detail-era");
    if (era) {
      if (card.series) {
        era.textContent = card.series;
        era.hidden = false;
      } else {
        era.hidden = true;
      }
    }

    const image = document.getElementById("card-detail-image");
    const placeholder = document.getElementById("card-detail-placeholder");
    updateCardDetailImage(image, placeholder, card);

    const setNameTarget = document.getElementById("card-detail-set-name");
    if (setNameTarget) {
      setNameTarget.textContent = card.set_name || container.dataset.setName || "";
    }

    const artist = document.getElementById("card-detail-artist");
    if (artist) {
      if (card.artist) {
        artist.textContent = `Ilustrator: ${card.artist}`;
        artist.hidden = false;
      } else {
        artist.textContent = "";
        artist.hidden = true;
      }
    }

    const numberField = document.getElementById("card-detail-number");
    if (numberField) {
      numberField.textContent = formatCardNumber(card) || "—";
    }

    const rarityField = document.getElementById("card-detail-rarity");
    if (rarityField) {
      const rarityLabel = formatRarityLabel(card.rarity);
      rarityField.textContent = rarityLabel || "—";
    }

    const totalField = document.getElementById("card-detail-total");
    if (totalField) {
      const totalValue = card.total || container.dataset.total || "";
      totalField.textContent = totalValue || "—";
    }

    const releaseField = document.getElementById("card-detail-release");
    if (releaseField) {
      let label = card.release_date || "";
      if (label) {
        const parsed = new Date(label);
        if (!Number.isNaN(parsed.getTime())) {
          label = parsed.toLocaleDateString("pl-PL");
        }
      }
      releaseField.textContent = label || "—";
    }

    const addButton = document.getElementById("detail-add-button");
    if (addButton) {
      const canAdd = Boolean(card.name && card.number && card.set_name);
      addButton.disabled = !canAdd;
      addButton.onclick = (event) => {
        event.preventDefault();
        if (!canAdd || addButton.dataset.loading === "true") {
          return;
        }
        void addDetailCardToCollection(card, addButton);
      };
    }

    const buyButton = document.getElementById("detail-buy-button");
    if (buyButton) {
      const query = [card.name, card.set_name].filter(Boolean).join(" ");
      buyButton.href = `https://kartoteka.shop/search?q=${encodeURIComponent(query)}`;
    }

    showAlert(alertBox, "");
  } catch (error) {
    renderRelatedCardsList([]);
    const fallbackTitle =
      container.dataset.name?.trim() ||
      (container.dataset.number?.trim()
        ? `Karta ${container.dataset.number.trim()}`
        : "Szczegóły karty");
    const titleElement = document.getElementById("card-detail-title");
    if (titleElement) {
      titleElement.textContent = fallbackTitle;
    }
    document.title = `${fallbackTitle} - Kartoteka`;

    const addButton = document.getElementById("detail-add-button");
    if (addButton) {
      addButton.disabled = true;
      addButton.dataset.loading = "false";
    }

    showAlert(alertBox, error.message || "Nie udało się załadować danych karty.");
  }
}

function bindCardDetail() {
  const container = document.getElementById("card-detail-page");
  if (!container) return;
  loadCardDetail(container);
}

function applyAddCardPrefill(form, cardSearch) {
  const params = new URLSearchParams(window.location.search);
  if (!params.has("name")) {
    return;
  }
  const name = params.get("name") || "";
  const number = params.get("number") || "";
  const setName = params.get("set_name") || "";
  const setCode = params.get("set_code") || "";
  const total = params.get("total") || "";

  const queryInput = form.querySelector('input[name="query"]');
  if (queryInput) {
    const identifier = [
      name,
      total && number ? `${number}/${total}` : number,
      setName,
    ]
      .filter((part) => part && part.trim())
      .join(" ")
      .trim();
    if (identifier) {
      queryInput.value = identifier;
    } else if (name) {
      queryInput.value = name;
    }
  }

  cardSearch?.reset?.();
  if (cardSearch?.search) {
    cardSearch.search().catch((error) => {
      console.error(error);
    });
  }
  window.history.replaceState({}, document.title, window.location.pathname);
}

function bindDashboard() {
  const refreshBtn = document.getElementById("refresh-collection");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", () => {
      loadCollection();
      loadSummary();
    });
  }
  const table = document.getElementById("collection-table");
  if (table) {
    table.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      const action = target.dataset.action;
      const id = target.dataset.id;
      if (!action || !id) return;
      if (action === "delete") {
        deleteEntry(id);
      }
    });
  }
  loadCollection();
  loadSummary();
}

function bindAddCardPage() {
  const page = document.getElementById("add-card-page");
  if (!page) return;
  const form = document.getElementById("add-card-form");
  if (!form) return;
  const alertBox = document.getElementById("add-card-alert");
  const cardSearch = setupCardSearch(form);

  const executeSearch = async () => {
    const queryInput = form.querySelector('input[name="query"]');
    if (!queryInput || !queryInput.value.trim()) {
      showAlert(alertBox, "Wpisz nazwę lub numer karty, aby rozpocząć wyszukiwanie.");
      queryInput?.focus();
      return;
    }
    showAlert(alertBox, "");
    try {
      await cardSearch?.search?.();
    } catch (error) {
      showAlert(alertBox, error.message || "Nie udało się wyszukać kart.");
    }
  };

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    executeSearch();
  });

  applyAddCardPrefill(form, cardSearch);
}

async function bindSettingsPage() {
  const page = document.getElementById("settings-page");
  if (!page) return;

  const profileForm = document.getElementById("settings-profile-form");
  const passwordForm = document.getElementById("settings-password-form");
  const profileAlert = profileForm?.querySelector(".alert");
  const passwordAlert = passwordForm?.querySelector(".alert");
  const emailInput = profileForm?.querySelector('input[name="email"]');
  const avatarInput = profileForm?.querySelector('input[name="avatar_url"]');
  const avatarChoices = profileForm
    ? Array.from(profileForm.querySelectorAll('input[name="avatar_choice"]'))
    : [];

  const syncAvatarChoices = (value) => {
    if (!avatarChoices.length) return;
    const target = typeof value === "string" ? value.trim() : "";
    let matchedRadio = null;
    for (const radio of avatarChoices) {
      const radioUrl = (radio.dataset.url || "").trim();
      const isCustom = radio.dataset.custom === "true";
      if (!isCustom && target && radioUrl === target) {
        matchedRadio = radio;
        break;
      }
    }
    avatarChoices.forEach((radio) => {
      const isCustom = radio.dataset.custom === "true";
      if (matchedRadio) {
        radio.checked = radio === matchedRadio;
      } else {
        radio.checked = isCustom;
      }
    });
  };

  if (avatarInput && avatarChoices.length) {
    avatarInput.addEventListener("input", () => {
      syncAvatarChoices(avatarInput.value);
    });
    avatarChoices.forEach((radio) => {
      radio.addEventListener("change", () => {
        const isCustom = radio.dataset.custom === "true";
        const url = (radio.dataset.url || "").trim();
        if (!avatarInput) return;
        if (isCustom) {
          if (!avatarInput.value) {
            avatarInput.value = "";
          }
          avatarInput.focus();
        } else {
          avatarInput.value = url;
          avatarInput.dispatchEvent(new Event("input", { bubbles: true }));
        }
      });
    });
  }

  const applyUserData = (user) => {
    if (!user) return;
    if (emailInput) {
      emailInput.value = user.email || "";
    }
    if (avatarInput) {
      avatarInput.value = user.avatar_url || "";
    }
    syncAvatarChoices(user.avatar_url || "");
    if (document.body) {
      document.body.dataset.username = user.username ?? "";
      document.body.dataset.avatar = user.avatar_url ?? "";
    }
    updateUserBadge({ username: user.username ?? "", avatar_url: user.avatar_url ?? "" });
  };

  try {
    const user = await apiFetch("/users/me");
    applyUserData(user);
  } catch (error) {
    if (profileAlert) {
      showAlert(profileAlert, error.message || "Nie udało się pobrać danych konta.");
    }
  }

  if (profileForm) {
    profileForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      showAlert(profileAlert, "");
      const payload = formToJSON(profileForm);
      const body = {
        email: typeof payload.email === "string" ? payload.email.trim() : undefined,
        avatar_url:
          typeof payload.avatar_url === "string" ? payload.avatar_url.trim() : undefined,
      };
      try {
        const user = await apiFetch("/users/me", {
          method: "PATCH",
          body: JSON.stringify(body),
        });
        applyUserData(user);
        showAlert(profileAlert, "Dane profilu zostały zapisane.", "success");
      } catch (error) {
        showAlert(profileAlert, error.message || "Nie udało się zapisać zmian.");
      }
    });
  }

  if (passwordForm) {
    passwordForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      showAlert(passwordAlert, "");
      const payload = formToJSON(passwordForm);
      const currentPassword = typeof payload.current_password === "string" ? payload.current_password : "";
      const newPassword = typeof payload.new_password === "string" ? payload.new_password : "";
      if (!currentPassword || !newPassword) {
        showAlert(passwordAlert, "Uzupełnij oba pola hasła.");
        return;
      }
      try {
        await apiFetch("/users/me", {
          method: "PATCH",
          body: JSON.stringify({
            current_password: currentPassword,
            new_password: newPassword,
          }),
        });
        passwordForm.reset();
        showAlert(passwordAlert, "Hasło zostało zmienione.", "success");
      } catch (error) {
        showAlert(passwordAlert, error.message || "Nie udało się zmienić hasła.");
      }
    });
  }
}

function bindPortfolio() {
  const alertBox = document.getElementById("portfolio-alert");
  const refreshBtn = document.getElementById("refresh-portfolio");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", async () => {
      await loadCollection();
      loadSummary(alertBox);
      loadPortfolioCards(alertBox);
      loadPortfolioHistory(alertBox);
    });
  }
  loadCollection().then(() => {
    loadSummary(alertBox);
    loadPortfolioCards(alertBox);
    loadPortfolioHistory(alertBox);
  });
}

async function hydrateUserContext() {
  const token = getToken();
  const result = { user: null, tokenPresent: Boolean(token), error: null };
  if (!token) {
    updateUserBadge({ username: "" });
    if (document.body) {
      document.body.dataset.username = "";
      document.body.dataset.avatar = "";
    }
    return result;
  }

  try {
    const user = await apiFetch("/users/me");
    if (document.body) {
      document.body.dataset.username = user?.username ?? "";
      document.body.dataset.avatar = user?.avatar_url ?? "";
    }
    updateUserBadge({ username: user?.username ?? "", avatar_url: user?.avatar_url ?? "" });
    result.user = user;
    return result;
  } catch (error) {
    result.error = error;
    clearToken();
    updateUserBadge({ username: "" });
    if (document.body) {
      document.body.dataset.username = "";
      document.body.dataset.avatar = "";
    }
    return result;
  }
}

async function ensureAuthenticated() {
  const { user, tokenPresent, error } = await hydrateUserContext();
  if (user) {
    return true;
  }

  const alertBox = document.querySelector(".alert");
  if (alertBox) {
    const message = tokenPresent
      ? "Sesja wygasła. Zaloguj się ponownie."
      : "Wymagane logowanie.";
    showAlert(alertBox, message);
  }
  if (tokenPresent && error) {
    console.warn("Nie udało się pobrać danych użytkownika", error);
  }
  window.location.href = "/login";
  return false;
}

window.addEventListener("DOMContentLoaded", async () => {
  setupThemeToggle();
  setupNavigation();
  setupHeaderVisibility();
  const loginForm = document.getElementById("login-form");
  if (loginForm) {
    loginForm.addEventListener("submit", (event) => {
      event.preventDefault();
      handleLogin(loginForm);
    });
  }

  const registerForm = document.getElementById("register-form");
  if (registerForm) {
    registerForm.addEventListener("submit", (event) => {
      event.preventDefault();
      handleRegister(registerForm);
    });
  }

  const needsDashboard = Boolean(document.getElementById("collection-table"));
  const needsPortfolio = Boolean(document.getElementById("portfolio-overview"));
  const needsDetail = Boolean(document.getElementById("card-detail-page"));
  const needsAddCard = Boolean(document.getElementById("add-card-page"));
  const needsSettings = Boolean(document.getElementById("settings-page"));

  const requiresAuth = needsDashboard || needsPortfolio || needsAddCard || needsSettings;
  if (requiresAuth) {
    if (await ensureAuthenticated()) {
      if (needsDashboard) {
        bindDashboard();
      }
      if (needsAddCard) {
        bindAddCardPage();
      }
      if (needsPortfolio) {
        bindPortfolio();
      }
      if (needsDetail) {
        bindCardDetail();
      }
      if (needsSettings) {
        bindSettingsPage();
      }
    }
  } else if (needsDetail) {
    const { error, tokenPresent } = await hydrateUserContext();
    if (tokenPresent && error) {
      const alertBox = document.querySelector(".alert");
      if (alertBox) {
        showAlert(alertBox, "Sesja wygasła. Zaloguj się ponownie.");
      }
    }
    bindCardDetail();
  }
});

window.addEventListener("load", () => {
  registerServiceWorker();
});
