const TOKEN_KEY = "kartoteka_token";

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

function updateUserBadge(username) {
  const display = document.querySelector("[data-username-display]");
  const logoutButton = document.getElementById("logout-button");
  const trimmed = username ? String(username).trim() : "";
  if (display) {
    display.textContent = trimmed || "Gość";
    display.dataset.state = trimmed ? "authenticated" : "anonymous";
  }
  if (logoutButton) {
    logoutButton.hidden = !trimmed;
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
      updateUserBadge("");
      window.location.href = "/";
    });
  }

  const initialUsername = document.body?.dataset.username ?? "";
  updateUserBadge(initialUsername);
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
      typeof entry.current_price === "number" ? entry.current_price.toFixed(2) : null;
    const totalValue =
      typeof entry.current_price === "number"
        ? (entry.current_price * entry.quantity || 0).toFixed(2)
        : null;
    if (priceValue && totalValue) {
      value.textContent = `Wartość sztuki: ${priceValue} PLN • Łącznie: ${totalValue} PLN`;
    } else if (priceValue) {
      value.textContent = `Wartość sztuki: ${priceValue} PLN`;
    } else {
      value.textContent = "Wartość sztuki: -";
    }
    body.appendChild(value);

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

function updateSummary(summary) {
  const count = document.getElementById("summary-count");
  const quantity = document.getElementById("summary-quantity");
  const value = document.getElementById("summary-value");
  if (count) count.textContent = summary.total_cards;
  if (quantity) quantity.textContent = summary.total_quantity;
  if (value) value.textContent = summary.estimated_value.toFixed(2);

  const pCount = document.getElementById("portfolio-count");
  const pQuantity = document.getElementById("portfolio-quantity");
  const pValue = document.getElementById("portfolio-value");
  if (pCount) pCount.textContent = summary.total_cards;
  if (pQuantity) pQuantity.textContent = summary.total_quantity;
  if (pValue) pValue.textContent = summary.estimated_value.toFixed(2);
}

async function loadCollection() {
  try {
    const entries = await apiFetch("/cards/");
    renderCollection(entries);
  } catch (error) {
    console.error(error);
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
  const suggestionsBox = document.getElementById("card-suggestions");

  if (!nameInput || !suggestionsBox) {
    return null;
  }

  const eventTarget = form;
  let selectedCard = null;
  let requestId = 0;

  const clearNumberMetadata = () => {
    if (numberInput) {
      delete numberInput.dataset.total;
    }
  };

  const hideSuggestions = () => {
    suggestionsBox.innerHTML = "";
    suggestionsBox.hidden = true;
  };

  const showSuggestionsMessage = (message) => {
    suggestionsBox.innerHTML = "";
    const info = document.createElement("p");
    info.className = "card-suggestions-empty";
    info.textContent = message;
    suggestionsBox.appendChild(info);
    suggestionsBox.hidden = false;
  };

  const clearSelection = () => {
    selectedCard = null;
    if (rarityInput) {
      rarityInput.value = "";
    }
    clearNumberMetadata();
    eventTarget.dispatchEvent(new Event("cardsearch:clear"));
  };

  const applySuggestion = (card) => {
    selectedCard = card;
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
    hideSuggestions();
    eventTarget.dispatchEvent(new CustomEvent("cardsearch:select", { detail: { card } }));
  };

  const renderSuggestions = (cards) => {
    suggestionsBox.innerHTML = "";
    if (!Array.isArray(cards) || !cards.length) {
      showSuggestionsMessage("Nie znaleziono kart dla podanych kryteriów.");
      return;
    }
    const fragment = document.createDocumentFragment();
    cards.forEach((card) => {
      const item = document.createElement("article");
      item.className = "card-suggestion";

      const link = document.createElement("a");
      link.className = "card-suggestion-link";
      link.href = buildCardDetailUrl(card);

      if (card.image_small) {
        const img = document.createElement("img");
        img.src = card.image_small;
        img.alt = `Podgląd ${card.name}`;
        img.loading = "lazy";
        img.className = "card-suggestion-thumbnail";
        link.appendChild(img);
      } else {
        const placeholder = document.createElement("span");
        placeholder.className = "card-suggestion-placeholder";
        placeholder.textContent = "🃏";
        placeholder.setAttribute("aria-hidden", "true");
        link.appendChild(placeholder);
      }

      const info = document.createElement("div");
      info.className = "card-suggestion-info";
      const title = document.createElement("strong");
      title.textContent = card.name || "";
      info.appendChild(title);

      const meta = document.createElement("div");
      meta.className = "card-suggestion-meta";
      const numberText = formatCardNumber(card);
      if (numberText) {
        const numberSpan = document.createElement("span");
        numberSpan.textContent = numberText;
        meta.appendChild(numberSpan);
      }
      if (card.set_name) {
        const setWrapper = document.createElement("span");
        setWrapper.className = "card-suggestion-set";
        if (card.set_icon) {
          const setImg = document.createElement("img");
          setImg.src = card.set_icon;
          setImg.alt = `Logo ${card.set_name}`;
          setImg.loading = "lazy";
          setImg.className = "card-suggestion-set-icon";
          setWrapper.appendChild(setImg);
        }
        const setLabel = document.createElement("span");
        setLabel.textContent = card.set_name;
        setWrapper.appendChild(setLabel);
        meta.appendChild(setWrapper);
      }
      if (meta.childElementCount) {
        info.appendChild(meta);
      }
      if (card.rarity) {
        const raritySpan = document.createElement("span");
        raritySpan.className = "card-suggestion-rarity";
        raritySpan.textContent = card.rarity;
        info.appendChild(raritySpan);
      }

      link.appendChild(info);
      item.appendChild(link);

      const addButton = document.createElement("button");
      addButton.type = "button";
      addButton.className = "card-suggestion-add";
      addButton.textContent = "Wybierz";
      addButton.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        applySuggestion(card);
      });
      item.appendChild(addButton);

      fragment.appendChild(item);
    });
    suggestionsBox.appendChild(fragment);
    suggestionsBox.hidden = false;
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

  const fetchSuggestions = async () => {
    const name = nameInput.value.trim();
    if (!name) {
      hideSuggestions();
      return [];
    }
    const { number, total } = parseNumberParts(numberInput ? numberInput.value : "");
    const setName = setInput?.value.trim() ?? "";

    const params = new URLSearchParams({ name });
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
    try {
      const results = await apiFetch(`/cards/search?${params.toString()}`);
      if (currentRequest !== requestId) {
        return [];
      }
      renderSuggestions(results);
      eventTarget.dispatchEvent(
        new CustomEvent("cardsearch:results", { detail: { count: results.length } })
      );
      return results;
    } catch (error) {
      if (currentRequest !== requestId) {
        return [];
      }
      console.error(error);
      showSuggestionsMessage(error.message || "Nie udało się pobrać wyników.");
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

  document.addEventListener("click", (event) => {
    if (
      !suggestionsBox.contains(event.target) &&
      event.target !== nameInput &&
      event.target !== numberInput &&
      event.target !== setInput
    ) {
      hideSuggestions();
    }
  });

  return {
    getSelectedCard: () => selectedCard,
    reset: () => {
      clearSelection();
      hideSuggestions();
    },
    search,
  };
}

async function addCard(form, cardSearch) {
  const alertBox = document.getElementById("add-card-alert");
  showAlert(alertBox, "");
  const selectedCard = cardSearch?.getSelectedCard?.();
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
    form.reset();
    cardSearch?.reset?.();
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

    const title = document.getElementById("card-detail-title");
    if (title) {
      title.textContent = card.name || "Szczegóły karty";
    }
    document.title = `${card.name || "Szczegóły karty"} - Kartoteka`;

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
      setNameTarget.textContent = card.set_name || "";
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
      priceField.textContent =
        typeof card.price_pln === "number" && !Number.isNaN(card.price_pln)
          ? card.price_pln.toFixed(2)
          : "—";
    }

    const updatedField = document.getElementById("card-detail-updated");
    if (updatedField) {
      if (card.last_price_update) {
        const updatedDate = new Date(card.last_price_update);
        updatedField.textContent = Number.isNaN(updatedDate.getTime())
          ? "—"
          : updatedDate.toLocaleString();
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

function bindPortfolio() {
  const alertBox = document.getElementById("portfolio-alert");
  const refreshBtn = document.getElementById("refresh-portfolio");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", () => {
      loadSummary(alertBox);
      loadPortfolioCards(alertBox);
    });
  }
  loadSummary(alertBox);
  loadPortfolioCards(alertBox);
}

async function ensureAuthenticated() {
  const token = getToken();
  if (!token) {
    const alertBox = document.querySelector(".alert");
    if (alertBox) {
      showAlert(alertBox, "Wymagane logowanie.");
    }
    window.location.href = "/";
    return false;
  }

  try {
    const user = await apiFetch("/users/me");
    if (document.body) {
      document.body.dataset.username = user?.username ?? "";
    }
    updateUserBadge(user?.username ?? "");
    return true;
  } catch (error) {
    clearToken();
    const alertBox = document.querySelector(".alert");
    if (alertBox) {
      showAlert(alertBox, "Sesja wygasła. Zaloguj się ponownie.");
    }
    updateUserBadge("");
    window.location.href = "/";
    return false;
  }
}

window.addEventListener("DOMContentLoaded", async () => {
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

  if (needsDashboard || needsPortfolio || needsDetail || needsAddCard) {
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
    }
  }
});

window.addEventListener("load", () => {
  registerServiceWorker();
});
