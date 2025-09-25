const TOKEN_KEY = "kartoteka_token";
const THEME_KEY = "kartoteka_theme";
const LIGHT_THEME_COLOR = "#ffffff";
const DARK_THEME_COLOR = "#0c1224";

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

function formatChangeValue(value) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "0,00 zł";
  }
  const absolute = plnFormatter.format(Math.abs(value));
  if (value > 0) {
    return `+${absolute}`;
  }
  if (value < 0) {
    return `-${absolute}`;
  }
  return absolute;
}

function formatDateRangeLabel(startDate, endDate) {
  if (!(startDate instanceof Date) || Number.isNaN(startDate.getTime())) {
    return null;
  }
  if (!(endDate instanceof Date) || Number.isNaN(endDate.getTime())) {
    return startDate.toLocaleDateString("pl-PL");
  }
  const options = { day: "2-digit", month: "2-digit" };
  const startLabel = startDate.toLocaleDateString("pl-PL", options);
  const endLabel = endDate.toLocaleDateString("pl-PL", options);
  return startLabel === endLabel ? startLabel : `${startLabel} – ${endLabel}`;
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

function showAlert(element, message, type = "error") {
  if (!element) return;
  if (message) {
    element.textContent = message;
    element.hidden = false;
    if (type === "success") {
      element.classList.add("success");
    } else {
      element.classList.remove("success");
    }
  } else {
    element.textContent = "";
    element.hidden = true;
    element.classList.remove("success");
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
  if (!body) return;
  body.innerHTML = "";
  if (!entries.length) {
    const emptyRow = document.createElement("tr");
    emptyRow.innerHTML = `<td colspan="6" class="table-empty">Brak kart w kolekcji. Dodaj pierwszą kartę, aby rozpocząć.</td>`;
    body.appendChild(emptyRow);
    return;
  }
  for (const entry of entries) {
    const tr = document.createElement("tr");
    const priceValue =
      typeof entry.current_price === "number"
        ? entry.current_price.toFixed(2)
        : entry.current_price ?? "-";
    const detailUrl = buildCardDetailUrl(entry.card || {});
    tr.innerHTML = `
      <td data-label="Nazwa"><a class="table-link" href="${detailUrl}">${entry.card.name}</a></td>
      <td data-label="Numer">${entry.card.number}</td>
      <td data-label="Set">${entry.card.set_name}</td>
      <td data-label="Ilość">${entry.quantity}</td>
      <td data-label="Wartość">${priceValue}</td>
      <td data-label="Akcje">
        <div class="table-actions">
          <button class="secondary" data-action="refresh" data-id="${entry.id}">Odśwież cenę</button>
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
      if (card.set_icon) {
        const setImg = document.createElement("img");
        setImg.src = card.set_icon;
        setImg.alt = `Logo ${card.set_name}`;
        setImg.loading = "lazy";
        setInfo.appendChild(setImg);
      }
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

    const value = document.createElement("p");
    value.className = "portfolio-card-value";
    const priceValue =
      typeof entry.current_price === "number" ? entry.current_price : null;
    if (priceValue !== null) {
      const formatted = formatPln(priceValue);
      value.textContent = formatted
        ? `Wartość sztuki: ${formatted}`
        : "Wartość sztuki: -";
    } else {
      value.textContent = "Wartość sztuki: -";
    }
    body.appendChild(value);

    const changeContainer = document.createElement("div");
    changeContainer.className = "portfolio-card-trend";
    const direction = entry.change_direction || "flat";
    changeContainer.dataset.direction = direction;
    const changeValue =
      typeof entry.change_24h === "number" ? entry.change_24h : 0;
    const changeIcon = document.createElement("span");
    changeIcon.className = "portfolio-card-trend-icon";
    changeIcon.setAttribute("aria-hidden", "true");
    changeIcon.textContent = resolveTrendSymbol(direction);
    const changeText = document.createElement("span");
    changeText.className = "portfolio-card-trend-value";
    const changeFormatted = formatChangeValue(changeValue);
    changeText.textContent = changeFormatted;
    changeContainer.appendChild(changeIcon);
    changeContainer.appendChild(changeText);
    changeContainer.title = `Zmiana w 24h: ${changeFormatted}`;
    body.appendChild(changeContainer);

    if (entry.last_price_update) {
      const updated = document.createElement("p");
      updated.className = "portfolio-card-update";
      const date = new Date(entry.last_price_update);
      if (!Number.isNaN(date.getTime())) {
        updated.textContent = `Aktualizacja: ${date.toLocaleDateString()}`;
        body.appendChild(updated);
      }
    }

    link.appendChild(body);
    article.appendChild(link);
    fragment.appendChild(article);
  });
  container.appendChild(fragment);
}

function renderPortfolioPerformance(history) {
  const chartContainer = document.getElementById("portfolio-chart");
  const changeWrapper = document.getElementById("portfolio-change");
  const changeValue = document.getElementById("portfolio-change-value");
  const latestValueElement = document.getElementById("portfolio-chart-latest");
  const minValueElement = document.getElementById("portfolio-chart-min");
  const maxValueElement = document.getElementById("portfolio-chart-max");
  const rangeElement = document.getElementById("portfolio-chart-range");
  const totalValueElement = document.getElementById("portfolio-value");
  if (!chartContainer) {
    return;
  }
  chartContainer.innerHTML = "";
  const direction = history?.direction || "flat";
  const deltaValue = typeof history?.change_24h === "number" ? history.change_24h : 0;
  const latestPortfolioValue =
    typeof history?.latest_value === "number" ? history.latest_value : null;
  const applyMeta = ({
    latest = latestPortfolioValue,
    min = null,
    max = null,
    rangeText = null,
    directionKey = direction,
  } = {}) => {
    const resolvedDirection = directionKey || "flat";
    if (latestValueElement) {
      const formatted =
        typeof latest === "number" && !Number.isNaN(latest) ? formatPln(latest) : null;
      latestValueElement.textContent = formatted || "-";
      latestValueElement.dataset.direction = resolvedDirection;
    }
    if (minValueElement) {
      const formatted =
        typeof min === "number" && !Number.isNaN(min) ? formatPln(min) : null;
      minValueElement.textContent = formatted || "-";
    }
    if (maxValueElement) {
      const formatted =
        typeof max === "number" && !Number.isNaN(max) ? formatPln(max) : null;
      maxValueElement.textContent = formatted || "-";
    }
    if (rangeElement) {
      rangeElement.textContent = rangeText || "Brak danych";
    }
    if (totalValueElement) {
      const formatted =
        typeof latest === "number" && !Number.isNaN(latest) ? formatPln(latest) : null;
      if (formatted) {
        totalValueElement.textContent = formatted;
      }
      totalValueElement.dataset.direction = resolvedDirection;
    }
  };
  applyMeta();
  chartContainer.dataset.direction = direction;
  if (changeWrapper) {
    changeWrapper.dataset.direction = direction;
    const icon = changeWrapper.querySelector(".portfolio-change-icon");
    if (icon) {
      icon.textContent = resolveTrendSymbol(direction);
    }
  }
  if (changeValue) {
    changeValue.textContent = formatChangeValue(deltaValue);
  }

  const points = Array.isArray(history?.points) ? history.points : [];
  if (!points.length) {
    const emptyMessage = document.createElement("p");
    emptyMessage.className = "portfolio-chart-empty";
    emptyMessage.textContent = "Brak danych do wyświetlenia.";
    chartContainer.appendChild(emptyMessage);
    applyMeta({ min: null, max: null, rangeText: null, latest: latestPortfolioValue });
    return;
  }

  const numericPoints = points
    .map((point, index) => {
      const rawTimestamp = point.timestamp || point.date || point.recorded_at || "";
      const parsed = rawTimestamp ? Date.parse(rawTimestamp) : Number.NaN;
      const date = Number.isNaN(parsed) ? null : new Date(parsed);
      return {
        order: Number.isNaN(parsed) ? index : parsed,
        value: typeof point.value === "number" ? point.value : Number(point.value) || 0,
        date,
      };
    })
    .sort((a, b) => a.order - b.order);

  const values = numericPoints.map((point) => point.value);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const range = maxValue - minValue;
  const minY = 10;
  const maxY = 55;

  const coords = [];
  let linePath = "";
  numericPoints.forEach((point, idx) => {
    const ratio = numericPoints.length > 1 ? idx / (numericPoints.length - 1) : 0.5;
    const x = ratio * 100;
    const normalized = range > 0 ? (point.value - minValue) / range : 0.5;
    const y = maxY - normalized * (maxY - minY);
    coords.push({ x, y });
    linePath += `${idx === 0 ? "M" : " L"}${x.toFixed(2)},${y.toFixed(2)}`;
  });

  const areaPath = `${linePath} L 100 ${maxY} L 0 ${maxY} Z`;

  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 100 60");
  svg.setAttribute("preserveAspectRatio", "none");
  svg.classList.add("portfolio-chart-svg");

  const area = document.createElementNS("http://www.w3.org/2000/svg", "path");
  area.setAttribute("d", areaPath);
  area.classList.add("portfolio-chart-area");
  svg.appendChild(area);

  const line = document.createElementNS("http://www.w3.org/2000/svg", "path");
  line.setAttribute("d", linePath);
  line.classList.add("portfolio-chart-line");
  svg.appendChild(line);

  const lastCoord = coords[coords.length - 1];
  if (lastCoord) {
    const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    dot.setAttribute("cx", lastCoord.x.toFixed(2));
    dot.setAttribute("cy", lastCoord.y.toFixed(2));
    dot.setAttribute("r", "1.4");
    dot.classList.add("portfolio-chart-dot");
    svg.appendChild(dot);
  }

  chartContainer.appendChild(svg);

  const firstDatedPoint = numericPoints.find((point) => point.date instanceof Date)?.date;
  const lastDatedPoint = [...numericPoints]
    .reverse()
    .find((point) => point.date instanceof Date)?.date;
  applyMeta({
    min: minValue,
    max: maxValue,
    rangeText: formatDateRangeLabel(firstDatedPoint, lastDatedPoint),
    latest: latestPortfolioValue,
  });
}

function updateSummary(summary) {
  const count = document.getElementById("summary-count");
  const quantity = document.getElementById("summary-quantity");
  const value = document.getElementById("summary-value");
  if (count) count.textContent = summary.total_cards;
  if (quantity) quantity.textContent = summary.total_quantity;
  if (value) {
    const formatted = formatPln(summary.estimated_value);
    value.textContent = formatted || summary.estimated_value.toFixed(2);
  }

  const pCount = document.getElementById("portfolio-count");
  const pQuantity = document.getElementById("portfolio-quantity");
  const pValue = document.getElementById("portfolio-value");
  if (pCount) pCount.textContent = summary.total_cards;
  if (pQuantity) pQuantity.textContent = summary.total_quantity;
  if (pValue) {
    const formatted = formatPln(summary.estimated_value);
    if (formatted) {
      pValue.textContent = formatted;
    } else {
      pValue.textContent = summary.estimated_value.toFixed(2);
    }
  }
}

async function loadCollection() {
  try {
    const entries = await apiFetch("/cards/");
    renderCollection(entries);
  } catch (error) {
    console.error(error);
  }
}

async function loadPortfolioHistory(targetAlert) {
  const chartContainer = document.getElementById("portfolio-chart");
  if (chartContainer) {
    const loading = document.createElement("p");
    loading.className = "portfolio-chart-loading";
    loading.textContent = "Ładuję dane wykresu…";
    chartContainer.innerHTML = "";
    chartContainer.appendChild(loading);
  }
  try {
    const history = await apiFetch("/cards/portfolio/history");
    renderPortfolioPerformance(history);
  } catch (error) {
    if (chartContainer) {
      chartContainer.innerHTML = "";
      const message = document.createElement("p");
      message.className = "portfolio-chart-error";
      message.textContent = error.message;
      chartContainer.appendChild(message);
    }
    if (targetAlert) {
      showAlert(targetAlert, error.message);
    }
  }
}

async function loadSummary(targetAlert) {
  try {
    const summary = await apiFetch("/cards/summary");
    updateSummary(summary);
    showAlert(targetAlert, "");
  } catch (error) {
    if (targetAlert) {
      showAlert(targetAlert, error.message);
    }
  }
}

async function loadPortfolioCards(targetAlert) {
  try {
    const entries = await apiFetch("/cards/");
    renderPortfolio(entries);
  } catch (error) {
    if (targetAlert) {
      showAlert(targetAlert, error.message);
    }
  }
}

function setupCardSearch(form) {
  if (!form) return null;
  const nameInput = form.querySelector('input[name="name"]');
  const numberInput = form.querySelector('input[name="number"]');
  const setInput = form.querySelector('input[name="set_name"]');
  const setCodeInput = form.querySelector('input[name="set_code"]');
  const rarityInput = form.querySelector('input[name="rarity"]');
  const resultsSection = document.getElementById("card-search-results-section");
  const resultsContainer = document.getElementById("card-search-results");
  const summary = document.getElementById("card-search-summary");
  const statusMessage = document.getElementById("card-search-empty");
  const pagination = document.getElementById("card-search-pagination");
  const pageInfo = document.getElementById("card-search-page-info");
  const prevButton = pagination?.querySelector('[data-page-action="prev"]') ?? null;
  const nextButton = pagination?.querySelector('[data-page-action="next"]') ?? null;
  const sortSelect = document.getElementById("card-search-sort");

  if (!nameInput || !resultsSection || !resultsContainer) {
    return null;
  }

  const eventTarget = form;
  let selectedCard = null;
  let selectedKey = "";
  let requestId = 0;
  let cardSearchApi = null;

  const state = {
    baseResults: [],
    sortMode: sortSelect?.value || "relevance",
    currentPage: 1,
    pageSize: 20,
  };

  const clearNumberMetadata = () => {
    if (numberInput) {
      delete numberInput.dataset.total;
    }
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

  const parseNumberParts = (value) => {
    const trimmed = String(value || "").trim();
    if (!trimmed) {
      return { number: "", total: "" };
    }
    if (trimmed.includes("/")) {
      const [num, total] = trimmed.split("/", 2);
      return { number: num.trim(), total: (total || "").trim() };
    }
    return { number: trimmed, total: "" };
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
    const base = [...state.baseResults];
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
      sortSelect.disabled = state.baseResults.length <= 1;
    }
  };

  const updatePaginationControls = (total) => {
    if (!pagination || !pageInfo) {
      return;
    }
    if (!total) {
      pagination.hidden = true;
      pageInfo.textContent = "";
      if (prevButton) prevButton.disabled = true;
      if (nextButton) nextButton.disabled = true;
      return;
    }
    const totalPages = Math.max(1, Math.ceil(total / state.pageSize));
    if (state.currentPage > totalPages) {
      state.currentPage = totalPages;
    }
    pagination.hidden = false;
    pageInfo.textContent = `Strona ${state.currentPage} z ${totalPages}`;
    if (prevButton) {
      prevButton.disabled = state.currentPage <= 1;
    }
    if (nextButton) {
      nextButton.disabled = state.currentPage >= totalPages;
    }
  };

  const createResultItem = (card) => {
    const item = document.createElement("article");
    item.className = "card-search-item";
    item.dataset.resultKey = buildResultKey(card);
    item.setAttribute("role", "listitem");

    const cardName = card?.name?.trim() || "Nieznana karta";

    const addButton = document.createElement("button");
    addButton.type = "button";
    addButton.className = "card-search-add";
    addButton.innerHTML = "<span aria-hidden=\"true\">+</span>";
    const addLabelParts = [`Dodaj kartę ${cardName} do kolekcji`];
    if (card.set_name) {
      addLabelParts.push(`z zestawu ${card.set_name}`);
    }
    const addLabel = addLabelParts.join(" ");
    addButton.setAttribute("aria-label", addLabel);
    addButton.title = addLabel;
    addButton.addEventListener("click", async (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (addButton.dataset.loading === "true") return;
      addButton.dataset.loading = "true";
      addButton.disabled = true;
      try {
        applySuggestion(card);
        await addCard(form, cardSearchApi, card);
      } catch (error) {
        console.error(error);
      } finally {
        addButton.disabled = false;
        delete addButton.dataset.loading;
      }
    });
    item.appendChild(addButton);

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
    if (card.set_icon) {
      const setImg = document.createElement("img");
      setImg.src = card.set_icon;
      setImg.alt = card.set_name ? `Logo ${card.set_name}` : "Logo dodatku";
      setImg.loading = "lazy";
      setMeta.appendChild(setImg);
    }
    const setText = document.createElement("span");
    setText.textContent = card.set_name || "Brak informacji o secie";
    setMeta.appendChild(setText);
    info.appendChild(setMeta);

    link.appendChild(info);
    item.appendChild(link);

    return item;
  };

  const renderResults = () => {
    const sorted = getSortedResults();
    const total = sorted.length;
    const totalPages = total ? Math.ceil(total / state.pageSize) : 1;
    if (state.currentPage > totalPages) {
      state.currentPage = totalPages;
    }
    if (state.currentPage < 1) {
      state.currentPage = 1;
    }
    const startIndex = total ? (state.currentPage - 1) * state.pageSize : 0;
    const pageItems = total ? sorted.slice(startIndex, startIndex + state.pageSize) : [];

    resultsContainer.innerHTML = "";
    if (!pageItems.length) {
      resultsContainer.hidden = true;
    } else {
      const fragment = document.createDocumentFragment();
      pageItems.forEach((card) => {
        fragment.appendChild(createResultItem(card));
      });
      resultsContainer.hidden = false;
      resultsContainer.appendChild(fragment);
    }

    updatePaginationControls(total);
    updateSelectionHighlight();
  };

  const clearSelection = () => {
    selectedCard = null;
    selectedKey = "";
    if (rarityInput) {
      rarityInput.value = "";
    }
    clearNumberMetadata();
    updateSelectionHighlight();
    eventTarget.dispatchEvent(new Event("cardsearch:clear"));
  };

  const applySuggestion = (card) => {
    selectedCard = card;
    selectedKey = buildResultKey(card);
    nameInput.value = card.name || "";
    if (numberInput) {
      const display =
        card.number_display ||
        (card.number && card.total ? `${card.number}/${card.total}` : card.number) ||
        "";
      numberInput.value = display;
      if (card.total) {
        numberInput.dataset.total = card.total;
      } else {
        clearNumberMetadata();
      }
    }
    if (setInput) {
      setInput.value = card.set_name || "";
    }
    if (setCodeInput) {
      setCodeInput.value = card.set_code || "";
    }
    if (rarityInput) {
      rarityInput.value = card.rarity || "";
    }
    updateSelectionHighlight();
    eventTarget.dispatchEvent(new CustomEvent("cardsearch:select", { detail: { card } }));
  };

  const fetchSuggestions = async () => {
    const name = nameInput.value.trim();
    if (!name) {
      state.baseResults = [];
      state.currentPage = 1;
      updateSummary(0);
      updateStatus("");
      resultsContainer.innerHTML = "";
      resultsContainer.hidden = true;
      if (resultsSection) {
        resultsSection.hidden = true;
      }
      updatePaginationControls(0);
      updateSortDisabled();
      return [];
    }

    const { number, total } = parseNumberParts(numberInput ? numberInput.value : "");
    const setName = setInput?.value.trim() ?? "";

    const params = new URLSearchParams({ name, limit: "100" });
    if (number) {
      params.set("number", number);
    }
    if (total) {
      params.set("total", total);
    }
    if (setName) {
      params.set("set_name", setName);
    }

    const currentRequest = ++requestId;
    state.currentPage = 1;
    state.sortMode = sortSelect?.value || state.sortMode || "relevance";
    if (resultsSection) {
      resultsSection.hidden = false;
    }
    updateSummary(0);
    updateStatus("Wyszukiwanie kart...", "loading");
    resultsContainer.innerHTML = "";
    resultsContainer.hidden = true;
    updatePaginationControls(0);
    updateSortDisabled();

    try {
      const results = await apiFetch(`/cards/search?${params.toString()}`);
      if (currentRequest !== requestId) {
        return [];
      }

      state.baseResults = Array.isArray(results) ? results : [];
      renderResults();
      updateSortDisabled();
      updateSummary(state.baseResults.length);
      if (!state.baseResults.length) {
        updateStatus("Nie znaleziono kart dla podanych kryteriów.");
      } else {
        updateStatus("");
      }
      eventTarget.dispatchEvent(
        new CustomEvent("cardsearch:results", { detail: { count: state.baseResults.length } })
      );
      return state.baseResults;
    } catch (error) {
      if (currentRequest !== requestId) {
        return [];
      }
      state.baseResults = [];
      renderResults();
      updateSummary(0);
      updateStatus(error.message || "Nie udało się pobrać wyników.", "error");
      updateSortDisabled();
      eventTarget.dispatchEvent(new CustomEvent("cardsearch:results", { detail: { count: 0 } }));
      throw error;
    }
  };

  const search = () => {
    clearSelection();
    return fetchSuggestions();
  };

  const handleInputChange = () => {
    clearSelection();
  };

  nameInput.addEventListener("input", handleInputChange);
  numberInput?.addEventListener("input", handleInputChange);
  setInput?.addEventListener("input", handleInputChange);

  sortSelect?.addEventListener("change", () => {
    state.sortMode = sortSelect.value || "relevance";
    state.currentPage = 1;
    renderResults();
  });

  prevButton?.addEventListener("click", () => {
    state.currentPage = Math.max(1, state.currentPage - 1);
    renderResults();
  });

  nextButton?.addEventListener("click", () => {
    state.currentPage += 1;
    renderResults();
  });

  updateSortDisabled();
  updatePaginationControls(0);

  const api = {
    getSelectedCard: () => selectedCard,
    clearSelection: () => {
      clearSelection();
    },
    reset: () => {
      clearSelection();
      state.baseResults = [];
      state.currentPage = 1;
      updateSummary(0);
      updateStatus("");
      resultsContainer.innerHTML = "";
      resultsContainer.hidden = true;
      if (resultsSection) {
        resultsSection.hidden = true;
      }
      updatePaginationControls(0);
      updateSortDisabled();
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
    const updates = [];
    if (document.getElementById("collection-table")) {
      updates.push(loadCollection());
    }
    if (document.getElementById("summary-count")) {
      updates.push(loadSummary());
    }
    if (updates.length) {
      await Promise.all(updates);
    }
    showAlert(alertBox, "Karta została dodana do kolekcji.", "success");
  } catch (error) {
    showAlert(alertBox, error.message);
  }
}

async function refreshEntry(id) {
  await apiFetch(`/cards/${id}/refresh`, { method: "POST" });
  await Promise.all([loadCollection(), loadSummary()]);
}

async function deleteEntry(id) {
  await apiFetch(`/cards/${id}`, { method: "DELETE" });
  await Promise.all([loadCollection(), loadSummary()]);
}

let cardDetailChart = null;
let cardDetailHistory = [];
let cardDetailRange = "1m";

function normaliseHistoryPoints(history) {
  return (history || [])
    .map((point) => {
      const price = Number(point.price);
      const time = point.recorded_at ? new Date(point.recorded_at) : null;
      if (!Number.isFinite(price) || !time || Number.isNaN(time.getTime())) {
        return null;
      }
      return { price, time };
    })
    .filter(Boolean)
    .sort((a, b) => a.time - b.time);
}

function filterHistoryByRange(history, range) {
  if (!Array.isArray(history) || !history.length) return [];
  let windowMs = 30 * 24 * 60 * 60 * 1000;
  if (range === "1d") {
    windowMs = 24 * 60 * 60 * 1000;
  } else if (range === "1w") {
    windowMs = 7 * 24 * 60 * 60 * 1000;
  }
  const cutoff = Date.now() - windowMs;
  return history.filter((point) => point.time.getTime() >= cutoff);
}

function updateDetailChart(points) {
  const chartCanvas = document.getElementById("card-price-chart");
  const emptyState = document.getElementById("card-chart-empty");
  if (!chartCanvas) return;
  const labels = points.map((point) => point.time.toLocaleDateString());
  const values = points.map((point) => point.price);
  if (!cardDetailChart) {
    cardDetailChart = new Chart(chartCanvas, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Cena (PLN)",
            data: values,
            fill: true,
            tension: 0.3,
            borderColor: "#333366",
            backgroundColor: "rgba(51, 51, 102, 0.18)",
            pointRadius: 3,
            pointHoverRadius: 5,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: {
            ticks: { color: "rgba(31, 31, 61, 0.6)" },
            grid: { display: false },
          },
          y: {
            ticks: { color: "rgba(31, 31, 61, 0.6)" },
            grid: { color: "rgba(51, 51, 102, 0.08)" },
          },
        },
      },
    });
  } else {
    cardDetailChart.data.labels = labels;
    cardDetailChart.data.datasets[0].data = values;
    cardDetailChart.update();
  }
  if (emptyState) {
    emptyState.hidden = points.length > 0;
  }
}

function setRangeButtons(range) {
  document.querySelectorAll(".chart-range [data-range]").forEach((button) => {
    if (button.dataset.range === range) {
      button.classList.add("active");
    } else {
      button.classList.remove("active");
    }
  });
}

function updateDetailRange(range) {
  cardDetailRange = range;
  setRangeButtons(range);
  const filtered = filterHistoryByRange(cardDetailHistory, range);
  updateDetailChart(filtered);
}

function renderRelatedCardsList(cards) {
  const container = document.getElementById("related-cards-list");
  const empty = document.getElementById("related-empty");
  if (!container) return;
  container.innerHTML = "";
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
      if (card.set_icon) {
        const setImg = document.createElement("img");
        setImg.src = card.set_icon;
        setImg.alt = `Logo ${card.set_name}`;
        setImg.loading = "lazy";
        setWrapper.appendChild(setImg);
      }
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
    const card = detail.card || {};
    const history = normaliseHistoryPoints(detail.history);
    cardDetailHistory = history;
    cardDetailRange = "1m";
    setRangeButtons(cardDetailRange);
    updateDetailChart(filterHistoryByRange(cardDetailHistory, cardDetailRange));
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
    const imageSource = card.image_large || card.image_small;
    if (image) {
      if (imageSource) {
        image.src = imageSource;
        image.hidden = false;
        if (placeholder) placeholder.hidden = true;
      } else {
        image.hidden = true;
        if (placeholder) placeholder.hidden = false;
      }
    }

    const setIcon = document.getElementById("card-detail-set-icon");
    if (setIcon) {
      if (card.set_icon) {
        setIcon.src = card.set_icon;
        setIcon.hidden = false;
      } else {
        setIcon.hidden = true;
      }
    }

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
      rarityField.textContent = card.rarity || "—";
    }

    const priceField = document.getElementById("card-detail-price");
    if (priceField) {
      const numericPrice =
        typeof card.price_pln === "number"
          ? card.price_pln
          : Number.parseFloat(card.price_pln);
      const formattedPrice = formatPln(numericPrice);
      priceField.textContent = formattedPrice || "—";
    }

    const updatedField = document.getElementById("card-detail-updated");
    if (updatedField) {
      if (card.last_price_update) {
        const updatedDate = new Date(card.last_price_update);
        updatedField.textContent = Number.isNaN(updatedDate.getTime())
          ? "—"
          : updatedDate.toLocaleString("pl-PL", {
              dateStyle: "medium",
              timeStyle: "short",
            });
      } else {
        updatedField.textContent = "—";
      }
    }

    const addButton = document.getElementById("detail-add-button");
    if (addButton) {
      addButton.href = buildAddCardUrl(card);
    }

    const buyButton = document.getElementById("detail-buy-button");
    if (buyButton) {
      const query = [card.name, card.set_name].filter(Boolean).join(" ");
      buyButton.href = `https://kartoteka.shop/search?q=${encodeURIComponent(query)}`;
    }

    showAlert(alertBox, "");
  } catch (error) {
    cardDetailHistory = [];
    updateDetailChart([]);
    renderRelatedCardsList([]);
    showAlert(alertBox, error.message);
  }
}

function bindCardDetail() {
  const container = document.getElementById("card-detail-page");
  if (!container) return;
  document.querySelectorAll(".chart-range [data-range]").forEach((button) => {
    button.addEventListener("click", () => {
      updateDetailRange(button.dataset.range || "1m");
    });
  });
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

  const nameInput = form.querySelector('input[name="name"]');
  const numberInput = form.querySelector('input[name="number"]');
  const setInput = form.querySelector('input[name="set_name"]');
  const setCodeInput = form.querySelector('input[name="set_code"]');

  if (nameInput) nameInput.value = name;
  if (numberInput) numberInput.value = total && number ? `${number}/${total}` : number;
  if (setInput) setInput.value = setName;
  if (setCodeInput) setCodeInput.value = setCode;

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
      if (action === "refresh") {
        refreshEntry(id);
      } else if (action === "delete") {
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
  const searchButton = document.getElementById("card-search-trigger");
  const addButton = document.getElementById("card-add-button");
  const alertBox = document.getElementById("add-card-alert");
  const cardSearch = setupCardSearch(form);
  const updateAddButtonState = () => {
    if (!addButton) return;
    const selected = cardSearch?.getSelectedCard?.();
    addButton.disabled = !selected;
  };

  updateAddButtonState();

  form.addEventListener("cardsearch:select", () => {
    updateAddButtonState();
    showAlert(alertBox, "");
  });

  form.addEventListener("cardsearch:clear", () => {
    updateAddButtonState();
  });

  if (searchButton) {
    searchButton.addEventListener("click", async (event) => {
      event.preventDefault();
      const nameInput = form.querySelector('input[name="name"]');
      if (!nameInput || !nameInput.value.trim()) {
        showAlert(alertBox, "Podaj nazwę karty, aby rozpocząć wyszukiwanie.");
        return;
      }
      showAlert(alertBox, "");
      try {
        await cardSearch?.search?.();
      } catch (error) {
        showAlert(alertBox, error.message || "Nie udało się wyszukać kart.");
      }
    });
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    addCard(form, cardSearch);
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

  const applyUserData = (user) => {
    if (!user) return;
    const emailInput = profileForm?.querySelector('input[name="email"]');
    const avatarInput = profileForm?.querySelector('input[name="avatar_url"]');
    if (emailInput) {
      emailInput.value = user.email || "";
    }
    if (avatarInput) {
      avatarInput.value = user.avatar_url || "";
    }
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
    refreshBtn.addEventListener("click", () => {
      loadSummary(alertBox);
      loadPortfolioCards(alertBox);
      loadPortfolioHistory(alertBox);
    });
  }
  loadSummary(alertBox);
  loadPortfolioCards(alertBox);
  loadPortfolioHistory(alertBox);
}

async function ensureAuthenticated() {
  const token = getToken();
  if (!token) {
    const alertBox = document.querySelector(".alert");
    if (alertBox) {
      showAlert(alertBox, "Wymagane logowanie.");
    }
    window.location.href = "/login";
    return false;
  }

  try {
    const user = await apiFetch("/users/me");
    if (document.body) {
      document.body.dataset.username = user?.username ?? "";
      document.body.dataset.avatar = user?.avatar_url ?? "";
    }
    updateUserBadge({ username: user?.username ?? "", avatar_url: user?.avatar_url ?? "" });
    return true;
  } catch (error) {
    clearToken();
    const alertBox = document.querySelector(".alert");
    if (alertBox) {
      showAlert(alertBox, "Sesja wygasła. Zaloguj się ponownie.");
    }
    updateUserBadge({ username: "" });
    if (document.body) {
      document.body.dataset.username = "";
      document.body.dataset.avatar = "";
    }
    window.location.href = "/login";
    return false;
  }
}

window.addEventListener("DOMContentLoaded", async () => {
  setupThemeToggle();
  setupNavigation();
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

  if (needsDashboard || needsPortfolio || needsDetail || needsAddCard || needsSettings) {
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
  }
});

window.addEventListener("load", () => {
  registerServiceWorker();
});
