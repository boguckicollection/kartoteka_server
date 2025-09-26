const TOKEN_KEY = "kartoteka_token";
const THEME_KEY = "kartoteka_theme";
const LIGHT_THEME_COLOR = "#f9fafb";
const DARK_THEME_COLOR = "#05060f";
const DEFAULT_CHART_PALETTE = {
  line: "#6fd3ff",
  fill: "rgba(111, 211, 255, 0.22)",
  grid: "rgba(111, 211, 255, 0.16)",
  text: "rgba(226, 232, 240, 0.72)",
};

let cardDetailChart = null;

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
  refreshDetailChartTheme();
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

function readCssCustomProperty(name, fallback) {
  try {
    const styles = window.getComputedStyle(document.documentElement);
    const value = styles.getPropertyValue(name);
    return value ? value.trim() : fallback;
  } catch (error) {
    console.warn("Unable to read CSS variable", name, error);
    return fallback;
  }
}

function getChartPalette() {
  return {
    line: readCssCustomProperty("--chart-line", DEFAULT_CHART_PALETTE.line),
    fill: readCssCustomProperty("--chart-fill", DEFAULT_CHART_PALETTE.fill),
    grid: readCssCustomProperty("--chart-grid", DEFAULT_CHART_PALETTE.grid),
    text: readCssCustomProperty("--chart-text", DEFAULT_CHART_PALETTE.text),
  };
}

function applyChartPalette(chart, palette = getChartPalette()) {
  if (!chart || !palette) {
    return;
  }
  const dataset = chart.data?.datasets?.[0];
  if (dataset) {
    dataset.borderColor = palette.line;
    dataset.backgroundColor = palette.fill;
    dataset.pointBackgroundColor = palette.line;
    dataset.pointBorderColor = palette.fill;
    dataset.pointHoverBackgroundColor = palette.line;
    dataset.pointHoverBorderColor = palette.fill;
  }
  const scales = chart.options?.scales;
  if (scales?.x?.ticks) {
    scales.x.ticks.color = palette.text;
  }
  if (scales?.x?.grid) {
    scales.x.grid.color = palette.grid;
  }
  if (scales?.y?.ticks) {
    scales.y.ticks.color = palette.text;
  }
  if (scales?.y?.grid) {
    scales.y.grid.color = palette.grid;
  }
}

function refreshDetailChartTheme() {
  if (!cardDetailChart) {
    return;
  }
  applyChartPalette(cardDetailChart);
  cardDetailChart.update("none");
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

function normalisePriceValue(value) {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }
  if (typeof value === "string") {
    let normalised = value.trim();
    if (!normalised) {
      return null;
    }
    normalised = normalised
      .replace(/\u00a0/g, "")
      .replace(/\s+/g, "")
      .replace(/(pln|zł)\.?/gi, "");
    const hasComma = normalised.includes(",");
    const hasDot = normalised.includes(".");
    if (hasComma && hasDot) {
      normalised = normalised.replace(/\./g, "");
    }
    normalised = normalised.replace(",", ".");
    const parsed = Number.parseFloat(normalised);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
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
    const direction = entry.change_direction || "flat";
    value.dataset.direction = direction;
    body.appendChild(value);

    const changeContainer = document.createElement("div");
    changeContainer.className = "portfolio-card-trend";
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
    const summaryValueElement = document.getElementById("summary-value");
    if (summaryValueElement) {
      summaryValueElement.dataset.direction = resolvedDirection;
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
  const datedPoints = numericPoints.filter((point) => point.date instanceof Date);
  let minTime = Number.POSITIVE_INFINITY;
  let maxTime = Number.NEGATIVE_INFINITY;
  datedPoints.forEach((point) => {
    if (!(point.date instanceof Date)) {
      return;
    }
    const time = point.date.getTime();
    if (time < minTime) {
      minTime = time;
    }
    if (time > maxTime) {
      maxTime = time;
    }
  });
  const hasValidTimeRange = Number.isFinite(minTime) && Number.isFinite(maxTime) && maxTime > minTime;
  if (!Number.isFinite(minTime)) {
    minTime = Number.NaN;
  }
  if (!Number.isFinite(maxTime)) {
    maxTime = Number.NaN;
  }

  const containerRect = chartContainer.getBoundingClientRect();
  const computedStyles = window.getComputedStyle(chartContainer);
  const parsePaddingValue = (value) => {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : 0;
  };
  const containerPadding = {
    top: parsePaddingValue(computedStyles.paddingTop),
    right: parsePaddingValue(computedStyles.paddingRight),
    bottom: parsePaddingValue(computedStyles.paddingBottom),
    left: parsePaddingValue(computedStyles.paddingLeft),
  };
  const rawWidth = containerRect.width || chartContainer.clientWidth || chartContainer.offsetWidth || 720;
  const rawHeight = containerRect.height || chartContainer.clientHeight || chartContainer.offsetHeight || 320;
  const innerWidth = Math.max(
    Math.round(rawWidth - containerPadding.left - containerPadding.right),
    320,
  );
  const innerHeight = Math.max(
    Math.round(rawHeight - containerPadding.top - containerPadding.bottom),
    220,
  );

  const viewBoxWidth = innerWidth;
  const viewBoxHeight = innerHeight;
  const padding = {
    top: Math.max(20, Math.round(innerHeight * 0.12)),
    right: Math.max(28, Math.round(innerWidth * 0.06)),
    bottom: Math.max(44, Math.round(innerHeight * 0.22)),
    left: Math.max(56, Math.round(innerWidth * 0.08)),
  };
  const chartWidth = viewBoxWidth - padding.left - padding.right;
  const chartHeight = viewBoxHeight - padding.top - padding.bottom;
  const chartLeft = padding.left;
  const chartRight = padding.left + chartWidth;
  const chartTop = padding.top;
  const chartBottom = padding.top + chartHeight;

  const coords = [];
  let linePath = "";
  numericPoints.forEach((point, idx) => {
    let ratio = numericPoints.length > 1 ? idx / (numericPoints.length - 1) : 0.5;
    if (point.date instanceof Date && Number.isFinite(minTime) && Number.isFinite(maxTime)) {
      if (hasValidTimeRange) {
        ratio = (point.date.getTime() - minTime) / (maxTime - minTime);
      } else {
        ratio = 0.5;
      }
    }
    const clampedRatio = Math.min(1, Math.max(0, ratio));
    const x = chartLeft + clampedRatio * chartWidth;
    const normalized = range > 0 ? (point.value - minValue) / range : 0.5;
    const y = chartBottom - normalized * chartHeight;
    const coord = { x, y, value: point.value, date: point.date };
    coords.push(coord);
    linePath += `${idx === 0 ? "M" : " L"}${x.toFixed(2)},${y.toFixed(2)}`;
  });

  const firstCoord = coords[0];
  const lastCoord = coords[coords.length - 1];
  const resolvedAreaStartX = lastCoord ? lastCoord.x.toFixed(2) : chartRight.toFixed(2);
  const resolvedAreaEndX = firstCoord ? firstCoord.x.toFixed(2) : chartLeft.toFixed(2);
  const areaPath = `${linePath} L ${resolvedAreaStartX} ${chartBottom.toFixed(2)} L ${resolvedAreaEndX} ${chartBottom.toFixed(2)} Z`;

  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${viewBoxWidth} ${viewBoxHeight}`);
  svg.setAttribute("preserveAspectRatio", "none");
  svg.classList.add("portfolio-chart-svg");

  const firstDatedPoint = numericPoints.find((point) => point.date instanceof Date)?.date ?? null;
  const lastDatedPoint = [...numericPoints]
    .reverse()
    .find((point) => point.date instanceof Date)?.date ?? null;
  const rangeLabel = formatDateRangeLabel(firstDatedPoint, lastDatedPoint);

  const chartId = chartContainer.id || "portfolio-chart";
  const titleId = `${chartId}-title`;
  const descId = `${chartId}-desc`;
  const svgTitle = document.createElementNS("http://www.w3.org/2000/svg", "title");
  svgTitle.id = titleId;
  svgTitle.textContent = "Historia wartości portfela";
  const svgDesc = document.createElementNS("http://www.w3.org/2000/svg", "desc");
  svgDesc.id = descId;
  const minLabel = formatPln(minValue) || `${minValue.toFixed(2)} zł`;
  const maxLabel = formatPln(maxValue) || `${maxValue.toFixed(2)} zł`;
  const latestLabel =
    typeof latestPortfolioValue === "number" && !Number.isNaN(latestPortfolioValue)
      ? formatPln(latestPortfolioValue)
      : "brak danych";
  svgDesc.textContent = `Zakres dat: ${rangeLabel || "brak danych"}. Zakres wartości: od ${minLabel} do ${maxLabel}. Ostatnia znana wartość: ${latestLabel}.`;
  svg.appendChild(svgTitle);
  svg.appendChild(svgDesc);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-labelledby", `${titleId} ${descId}`);

  const area = document.createElementNS("http://www.w3.org/2000/svg", "path");
  area.setAttribute("d", areaPath);
  area.classList.add("portfolio-chart-area");
  svg.appendChild(area);

  const gridGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
  gridGroup.classList.add("portfolio-chart-grid");

  const yTicksCount = 4;
  const yTicks = [];
  for (let i = 0; i <= yTicksCount; i += 1) {
    const ratio = i / yTicksCount;
    const value = range > 0 ? minValue + range * ratio : minValue;
    const y = chartBottom - ratio * chartHeight;
    yTicks.push({ ratio, value, y });
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", chartLeft.toFixed(2));
    line.setAttribute("x2", chartRight.toFixed(2));
    line.setAttribute("y1", y.toFixed(2));
    line.setAttribute("y2", y.toFixed(2));
    line.classList.add("portfolio-chart-grid-line", "portfolio-chart-grid-line--horizontal");
    gridGroup.appendChild(line);
  }

  const xTicks = [];
  if (datedPoints.length) {
    const uniqueDays = new Map();
    datedPoints.forEach((point) => {
      if (!(point.date instanceof Date)) return;
      const day = new Date(point.date.getFullYear(), point.date.getMonth(), point.date.getDate());
      const key = day.getTime();
      if (!uniqueDays.has(key)) {
        uniqueDays.set(key, day);
      }
    });
    const sortedDays = Array.from(uniqueDays.values()).sort((a, b) => a.getTime() - b.getTime());
    const maxTicks = 6;
    const step = sortedDays.length > maxTicks ? Math.ceil(sortedDays.length / maxTicks) : 1;
    for (let i = 0; i < sortedDays.length; i += step) {
      const day = sortedDays[i];
      const time = day.getTime();
      const ratio = hasValidTimeRange
        ? (time - minTime) / (maxTime - minTime)
        : 0.5;
      xTicks.push({
        position: Math.min(1, Math.max(0, ratio)),
        label: day.toLocaleDateString("pl-PL"),
      });
    }
    const lastDay = sortedDays[sortedDays.length - 1];
    if (lastDay) {
      const lastLabel = lastDay.toLocaleDateString("pl-PL");
      const existingLast = xTicks[xTicks.length - 1];
      if (!existingLast || existingLast.label !== lastLabel) {
        const ratio = hasValidTimeRange
          ? (lastDay.getTime() - minTime) / (maxTime - minTime)
          : 0.5;
        xTicks.push({ position: Math.min(1, Math.max(0, ratio)), label: lastLabel });
      }
    }
  } else {
    const fallbackTickCount = Math.min(numericPoints.length, 4);
    for (let i = 0; i < fallbackTickCount; i += 1) {
      const ratio = fallbackTickCount > 1 ? i / (fallbackTickCount - 1) : 0.5;
      const index = Math.min(
        numericPoints.length - 1,
        Math.max(0, Math.round(ratio * (numericPoints.length - 1)))
      );
      const point = numericPoints[index];
      const label = point?.date instanceof Date
        ? point.date.toLocaleDateString("pl-PL")
        : `#${index + 1}`;
      xTicks.push({ position: ratio, label });
    }
  }

  const verticalLinePositions = new Set();
  xTicks.forEach((tick) => {
    const x = chartLeft + tick.position * chartWidth;
    const rounded = Number(x.toFixed(2));
    if (Math.abs(rounded - chartLeft) < 0.01 || Math.abs(rounded - chartRight) < 0.01) {
      return;
    }
    const key = rounded.toFixed(2);
    if (verticalLinePositions.has(key)) {
      return;
    }
    verticalLinePositions.add(key);
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", rounded.toFixed(2));
    line.setAttribute("x2", rounded.toFixed(2));
    line.setAttribute("y1", chartTop.toFixed(2));
    line.setAttribute("y2", chartBottom.toFixed(2));
    line.classList.add("portfolio-chart-grid-line", "portfolio-chart-grid-line--vertical");
    gridGroup.appendChild(line);
  });

  svg.appendChild(gridGroup);

  const line = document.createElementNS("http://www.w3.org/2000/svg", "path");
  line.setAttribute("d", linePath);
  line.classList.add("portfolio-chart-line");
  svg.appendChild(line);

  const pointsGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
  pointsGroup.classList.add("portfolio-chart-points");

  const tooltip = document.createElement("div");
  tooltip.className = "portfolio-chart-tooltip";
  tooltip.setAttribute("role", "tooltip");
  tooltip.id = `${chartId}-tooltip`;
  tooltip.hidden = true;
  tooltip.dataset.visible = "false";
  const tooltipDate = document.createElement("span");
  tooltipDate.className = "portfolio-chart-tooltip-date";
  const tooltipValue = document.createElement("span");
  tooltipValue.className = "portfolio-chart-tooltip-value";
  tooltip.appendChild(tooltipDate);
  tooltip.appendChild(tooltipValue);

  const updateTooltipPosition = (coord) => {
    const svgRect = svg.getBoundingClientRect();
    const containerRect = chartContainer.getBoundingClientRect();
    const offsetX = svgRect.left - containerRect.left;
    const offsetY = svgRect.top - containerRect.top;
    const pxX = offsetX + (coord.x / viewBoxWidth) * svgRect.width;
    const pxY = offsetY + (coord.y / viewBoxHeight) * svgRect.height;
    tooltip.style.left = `${pxX}px`;
    tooltip.style.top = `${pxY}px`;
  };

  const showTooltip = (coord) => {
    const dateLabel = coord.date instanceof Date ? coord.date.toLocaleDateString("pl-PL") : "Brak daty";
    const valueLabel = formatPln(coord.value) || `${coord.value.toFixed(2)} zł`;
    tooltipDate.textContent = dateLabel;
    tooltipValue.textContent = valueLabel;
    tooltip.hidden = false;
    tooltip.dataset.visible = "true";
    updateTooltipPosition(coord);
  };

  const hideTooltip = () => {
    tooltip.hidden = true;
    tooltip.dataset.visible = "false";
  };

  coords.forEach((coord) => {
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("cx", coord.x.toFixed(2));
    circle.setAttribute("cy", coord.y.toFixed(2));
    circle.setAttribute("r", "1.8");
    circle.classList.add("portfolio-chart-point", "portfolio-chart-dot");
    const dateLabel = coord.date instanceof Date ? coord.date.toLocaleDateString("pl-PL") : "Brak daty";
    const valueLabel = formatPln(coord.value) || `${coord.value.toFixed(2)} zł`;
    circle.setAttribute("tabindex", "0");
    circle.setAttribute("focusable", "true");
    circle.setAttribute("role", "img");
    circle.setAttribute("aria-label", `${dateLabel}: ${valueLabel}`);
    circle.setAttribute("aria-describedby", tooltip.id);
    circle.addEventListener("mouseenter", () => showTooltip(coord));
    circle.addEventListener("mouseleave", hideTooltip);
    circle.addEventListener("focus", () => showTooltip(coord));
    circle.addEventListener("blur", hideTooltip);
    circle.addEventListener("mousemove", () => updateTooltipPosition(coord));
    pointsGroup.appendChild(circle);
  });

  svg.appendChild(pointsGroup);
  svg.addEventListener("mouseleave", hideTooltip);

  const yAxisGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
  yAxisGroup.classList.add("portfolio-chart-axis", "portfolio-chart-axis--y");
  const yAxisLine = document.createElementNS("http://www.w3.org/2000/svg", "line");
  yAxisLine.setAttribute("x1", chartLeft.toFixed(2));
  yAxisLine.setAttribute("x2", chartLeft.toFixed(2));
  yAxisLine.setAttribute("y1", chartTop.toFixed(2));
  yAxisLine.setAttribute("y2", chartBottom.toFixed(2));
  yAxisGroup.appendChild(yAxisLine);
  yTicks.forEach((tick) => {
    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("x", (chartLeft - 12).toFixed(2));
    label.setAttribute("y", tick.y.toFixed(2));
    label.setAttribute("text-anchor", "end");
    label.setAttribute("dominant-baseline", "middle");
    label.classList.add("portfolio-chart-axis-label", "portfolio-chart-axis-label--y");
    label.textContent = formatPln(tick.value) || `${tick.value.toFixed(2)} zł`;
    yAxisGroup.appendChild(label);
  });
  svg.appendChild(yAxisGroup);

  const xAxisGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
  xAxisGroup.classList.add("portfolio-chart-axis", "portfolio-chart-axis--x");
  const xAxisLine = document.createElementNS("http://www.w3.org/2000/svg", "line");
  xAxisLine.setAttribute("x1", chartLeft.toFixed(2));
  xAxisLine.setAttribute("x2", chartRight.toFixed(2));
  xAxisLine.setAttribute("y1", chartBottom.toFixed(2));
  xAxisLine.setAttribute("y2", chartBottom.toFixed(2));
  xAxisGroup.appendChild(xAxisLine);
  xTicks.forEach((tick) => {
    const x = chartLeft + tick.position * chartWidth;
    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("x", x.toFixed(2));
    label.setAttribute("y", (chartBottom + 18).toFixed(2));
    label.setAttribute("text-anchor", "middle");
    label.setAttribute("dominant-baseline", "hanging");
    label.classList.add("portfolio-chart-axis-label", "portfolio-chart-axis-label--x");
    label.textContent = tick.label;
    xAxisGroup.appendChild(label);
  });
  svg.appendChild(xAxisGroup);

  chartContainer.appendChild(svg);
  chartContainer.appendChild(tooltip);
  applyMeta({
    min: minValue,
    max: maxValue,
    rangeText: rangeLabel,
    latest: latestPortfolioValue,
  });
}

function updateSummary(summary) {
  const count = document.getElementById("summary-count");
  const quantity = document.getElementById("summary-quantity");
  const value = document.getElementById("summary-value");
  const rawDirection = summary && typeof summary.direction === "string" ? summary.direction : "";
  const direction = rawDirection === "up" || rawDirection === "down" ? rawDirection : "flat";
  if (count) count.textContent = summary.total_cards;
  if (quantity) quantity.textContent = summary.total_quantity;
  if (value) {
    const formatted = formatPln(summary.estimated_value);
    value.textContent = formatted || summary.estimated_value.toFixed(2);
    value.dataset.direction = direction;
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
    pValue.dataset.direction = direction;
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
  const queryInput = form.querySelector('input[name="query"]');
  const rarityInput = form.querySelector('input[name="rarity"]');
  const resultsSection = document.getElementById("card-search-results-section");
  const resultsContainer = document.getElementById("card-search-results");
  const summary = document.getElementById("card-search-summary");
  const statusMessage = document.getElementById("card-search-empty");
  const pagination = document.getElementById("card-search-pagination");
  const pageInfo = document.getElementById("card-search-page-info");
  const prevButton = pagination?.querySelector('[data-page-action="prev"]') ?? null;
  const nextButton = pagination?.querySelector('[data-page-action="next"]') ?? null;
  const pageList = pagination?.querySelector('[data-page-list]') ?? null;
  const sortSelect = document.getElementById("card-search-sort");

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
    currentPage: 1,
    pageSize: 20,
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

  const getTotalPages = (total = state.total) => {
    const safeTotal = Number.isFinite(total) ? Math.max(0, total) : Math.max(0, state.total);
    return safeTotal > 0 ? Math.ceil(safeTotal / state.pageSize) : 1;
  };

  const renderPageButtons = (totalPages) => {
    if (!pageList) {
      return;
    }
    pageList.innerHTML = "";
    if (totalPages <= 0) {
      return;
    }
    const fragment = document.createDocumentFragment();
    for (let page = 1; page <= totalPages; page += 1) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "card-search-page-number";
      button.dataset.page = String(page);
      button.textContent = String(page);
      if (page === state.currentPage) {
        button.classList.add("is-active");
        button.setAttribute("aria-current", "page");
        button.disabled = true;
      }
      fragment.appendChild(button);
    }
    pageList.appendChild(fragment);
  };

  const updatePaginationControls = (total = state.total) => {
    if (!pagination || !pageInfo) {
      return;
    }
    const safeTotal = Number.isFinite(total) ? Math.max(0, total) : Math.max(0, state.total);
    if (!safeTotal) {
      pagination.hidden = true;
      pageInfo.textContent = "";
      if (prevButton) prevButton.disabled = true;
      if (nextButton) nextButton.disabled = true;
      if (pageList) {
        pageList.innerHTML = "";
      }
      return;
    }
    const totalPages = getTotalPages(safeTotal);
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
    renderPageButtons(totalPages);
  };

  const goToPage = (page) => {
    const totalPages = getTotalPages();
    const nextPage = Math.min(Math.max(1, page), totalPages);
    if (nextPage === state.currentPage) {
      renderResults();
      return Promise.resolve(state.items);
    }
    state.currentPage = nextPage;
    return loadResults(nextPage).catch((error) => {
      console.error(error);
      return [];
    });
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

    updatePaginationControls(state.total);
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
  };

  const loadResults = async (page = 1) => {
    const query = queryInput.value.trim();
    if (!query) {
      state.items = [];
      state.total = 0;
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

    const params = new URLSearchParams({
      query,
      page: String(Math.max(1, page)),
      page_size: String(state.pageSize),
    });

    const currentRequest = ++requestId;
    state.currentPage = Math.max(1, page);
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
      const payload = await apiFetch(`/cards/search?${params.toString()}`);
      if (currentRequest !== requestId) {
        return [];
      }

      const responseItems = Array.isArray(payload?.items) ? payload.items : [];
      const responseTotal = Number.isFinite(payload?.total)
        ? Math.max(0, Number(payload.total))
        : responseItems.length;
      const responsePageSize = Number.isFinite(payload?.page_size)
        ? Math.max(1, Number(payload.page_size))
        : state.pageSize;
      const responsePage = Number.isFinite(payload?.page)
        ? Math.max(1, Number(payload.page))
        : state.currentPage;

      state.pageSize = responsePageSize;
      state.currentPage = responsePage;
      state.items = responseItems;
      state.total = responseTotal;

      renderResults();
      updateSortDisabled();
      updateSummary(state.total);
      if (!state.total) {
        updateStatus("Nie znaleziono kart dla podanych kryteriów.");
      } else if (!state.items.length) {
        updateStatus("Brak wyników na tej stronie.", "info");
      } else {
        updateStatus("");
      }
      eventTarget.dispatchEvent(
        new CustomEvent("cardsearch:results", { detail: { count: state.total } })
      );
      return state.items;
    } catch (error) {
      if (currentRequest !== requestId) {
        return [];
      }
      state.items = [];
      state.total = 0;
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
    return loadResults(1);
  };

  const handleInputChange = () => {
    clearSelection();
  };

  queryInput.addEventListener("input", handleInputChange);

  sortSelect?.addEventListener("change", () => {
    state.sortMode = sortSelect.value || "relevance";
    state.currentPage = 1;
    renderResults();
  });

  pagination?.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }
    const button = target.closest("[data-page-action]");
    if (!(button instanceof HTMLElement)) {
      return;
    }
    const action = button.dataset.pageAction;
    if (!action) {
      return;
    }
    event.preventDefault();
    if (action === "prev") {
      void goToPage(state.currentPage - 1);
    } else if (action === "next") {
      void goToPage(state.currentPage + 1);
    }
  });

  pageList?.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }
    const button = target.closest(".card-search-page-number");
    if (!(button instanceof HTMLElement)) {
      return;
    }
    const page = Number.parseInt(button.dataset.page || "", 10);
    if (!Number.isFinite(page)) {
      return;
    }
    event.preventDefault();
    void goToPage(page);
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
      state.items = [];
      state.total = 0;
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
  const ensureRangeMeta = (points, appliedRange) => {
    const output = Array.isArray(points) ? points.slice() : [];
    output.appliedRange = appliedRange;
    return output;
  };

  if (!Array.isArray(history) || !history.length) {
    return ensureRangeMeta([], "all");
  }

  if (range === "all") {
    return ensureRangeMeta(history, "all");
  }

  let windowMs = 30 * 24 * 60 * 60 * 1000;
  if (range === "1d") {
    windowMs = 24 * 60 * 60 * 1000;
  } else if (range === "1w") {
    windowMs = 7 * 24 * 60 * 60 * 1000;
  }

  const cutoff = Date.now() - windowMs;
  const filtered = history.filter((point) => point.time.getTime() >= cutoff);
  if (!filtered.length) {
    return ensureRangeMeta(history, "all");
  }
  return ensureRangeMeta(filtered, range);
}

function updateDetailChart(points) {
  const chartCanvas = document.getElementById("card-price-chart");
  const emptyState = document.getElementById("card-chart-empty");
  if (!chartCanvas) return;
  const labels = points.map((point) => point.time.toLocaleDateString());
  const values = points.map((point) => point.price);
  const palette = getChartPalette();
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
            borderColor: palette.line,
            backgroundColor: palette.fill,
            pointBackgroundColor: palette.line,
            pointBorderColor: palette.fill,
            pointHoverBackgroundColor: palette.line,
            pointHoverBorderColor: palette.fill,
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
            ticks: { color: palette.text },
            grid: { display: false, color: palette.grid },
          },
          y: {
            ticks: { color: palette.text },
            grid: { color: palette.grid },
          },
        },
      },
    });
    applyChartPalette(cardDetailChart, palette);
  } else {
    cardDetailChart.data.labels = labels;
    cardDetailChart.data.datasets[0].data = values;
    applyChartPalette(cardDetailChart, palette);
    cardDetailChart.update();
  }
  if (emptyState) {
    emptyState.hidden = Array.isArray(cardDetailHistory) && cardDetailHistory.length > 0;
  }
}

function setRangeButtons(range) {
  let hasMatch = false;
  document.querySelectorAll(".chart-range [data-range]").forEach((button) => {
    if (button.dataset.range === range) {
      button.classList.add("active");
      hasMatch = true;
    } else {
      button.classList.remove("active");
    }
  });
  if (!hasMatch) {
    const fallback = document.querySelector('.chart-range [data-range="all"]');
    if (fallback) {
      fallback.classList.add("active");
    }
  }
}

function updateDetailRange(range) {
  const filtered = filterHistoryByRange(cardDetailHistory, range);
  const appliedRange = filtered.appliedRange || range;
  cardDetailRange = appliedRange;
  setRangeButtons(appliedRange);
  updateDetailChart(filtered);
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
    const history = normaliseHistoryPoints(detail.history);
    cardDetailHistory = history;
    const initialRange = filterHistoryByRange(cardDetailHistory, "1m");
    cardDetailRange = initialRange.appliedRange || "1m";
    setRangeButtons(cardDetailRange);
    updateDetailChart(initialRange);
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
      const rarityLabel = formatRarityLabel(card.rarity);
      rarityField.textContent = rarityLabel || "—";
    }

    const priceField = document.getElementById("card-detail-price");
    if (priceField) {
      const numericPrice = normalisePriceValue(card.price_pln);
      const formattedPrice =
        numericPrice !== null ? formatPln(numericPrice) : null;
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
    cardDetailHistory = [];
    updateDetailChart([]);
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
