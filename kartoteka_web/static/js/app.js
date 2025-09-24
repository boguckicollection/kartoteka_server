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
    tr.innerHTML = `
      <td data-label="Nazwa">${entry.card.name}</td>
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

function setupCardSearch(form) {
  const nameInput = form.querySelector('input[name="name"]');
  const numberInput = form.querySelector('input[name="number"]');
  const setInput = form.querySelector('input[name="set_name"]');
  const setCodeInput = form.querySelector('input[name="set_code"]');
  const rarityInput = form.querySelector('input[name="rarity"]');
  const suggestionsBox = document.getElementById("card-suggestions");

  if (!nameInput || !numberInput || !suggestionsBox) {
    return null;
  }

  let selectedCard = null;
  let requestId = 0;

  const hideSuggestions = () => {
    suggestionsBox.innerHTML = "";
    suggestionsBox.hidden = true;
  };

  const formatNumberDisplay = (card) => {
    if (card.number_display) {
      return card.number_display;
    }
    if (card.number && card.total) {
      return `${card.number}/${card.total}`;
    }
    return card.number ?? "";
  };

  const applySuggestion = (card) => {
    selectedCard = card;
    nameInput.value = card.name || "";
    numberInput.value = card.number || "";
    if (card.total) {
      numberInput.dataset.total = card.total;
    } else {
      delete numberInput.dataset.total;
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
  };

  const renderSuggestions = (cards) => {
    suggestionsBox.innerHTML = "";
    if (!Array.isArray(cards) || !cards.length) {
      suggestionsBox.hidden = true;
      return;
    }
    const fragment = document.createDocumentFragment();
    cards.forEach((card) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "card-suggestion";

      if (card.image_small) {
        const img = document.createElement("img");
        img.src = card.image_small;
        img.alt = `Podgląd ${card.name}`;
        img.loading = "lazy";
        img.className = "card-suggestion-thumbnail";
        button.appendChild(img);
      } else {
        const placeholder = document.createElement("span");
        placeholder.className = "card-suggestion-placeholder";
        placeholder.textContent = "🃏";
        placeholder.setAttribute("aria-hidden", "true");
        button.appendChild(placeholder);
      }

      const info = document.createElement("div");
      info.className = "card-suggestion-info";
      const title = document.createElement("strong");
      title.textContent = card.name || "";
      info.appendChild(title);

      const meta = document.createElement("div");
      meta.className = "card-suggestion-meta";
      const numberText = formatNumberDisplay(card);
      if (numberText) {
        const numberSpan = document.createElement("span");
        numberSpan.textContent = numberText;
        meta.appendChild(numberSpan);
      }
      if (card.set_name) {
        const setSpan = document.createElement("span");
        setSpan.textContent = card.set_name;
        meta.appendChild(setSpan);
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

      button.appendChild(info);
      button.addEventListener("click", () => applySuggestion(card));
      fragment.appendChild(button);
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

  const fetchSuggestions = debounce(async () => {
    const name = nameInput.value.trim();
    const { number, total } = parseNumberParts(numberInput.value);
    const setName = setInput?.value.trim() ?? "";
    if (!name || !number) {
      hideSuggestions();
      return;
    }

    const params = new URLSearchParams({ name, number });
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
        return;
      }
      renderSuggestions(results);
    } catch (error) {
      if (currentRequest !== requestId) {
        return;
      }
      console.error(error);
      hideSuggestions();
    }
  }, 300);

  const handlePrimaryInput = () => {
    selectedCard = null;
    if (rarityInput) {
      rarityInput.value = "";
    }
    fetchSuggestions();
  };

  nameInput.addEventListener("input", handlePrimaryInput);
  numberInput.addEventListener("input", handlePrimaryInput);
  if (setInput) {
    setInput.addEventListener("input", () => fetchSuggestions());
  }

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
      selectedCard = null;
      hideSuggestions();
      if (rarityInput) {
        rarityInput.value = "";
      }
    },
  };
}

async function addCard(form, cardSearch) {
  const alertBox = document.getElementById("add-card-alert");
  showAlert(alertBox, "");
  const selectedCard = cardSearch?.getSelectedCard?.();
  const data = formToJSON(form);
  if (selectedCard) {
    if (!data.name) data.name = selectedCard.name;
    if (!data.number) data.number = selectedCard.number;
    if (!data.set_name) data.set_name = selectedCard.set_name;
    if (!data.set_code) data.set_code = selectedCard.set_code;
    if (data.rarity === undefined && selectedCard.rarity) {
      data.rarity = selectedCard.rarity;
    }
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
  try {
    await apiFetch("/cards/", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    form.reset();
    cardSearch?.reset?.();
    await Promise.all([loadCollection(), loadSummary(alertBox)]);
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

function bindDashboard() {
  const addForm = document.getElementById("add-card-form");
  if (addForm) {
    const cardSearch = setupCardSearch(addForm);
    addForm.addEventListener("submit", (event) => {
      event.preventDefault();
      addCard(addForm, cardSearch);
    });
  }
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

function bindPortfolio() {
  const alertBox = document.getElementById("portfolio-alert");
  const refreshBtn = document.getElementById("refresh-portfolio");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", () => loadSummary(alertBox));
  }
  loadSummary(alertBox);
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

  if (needsDashboard || needsPortfolio) {
    if (await ensureAuthenticated()) {
      if (needsDashboard) {
        bindDashboard();
      }
      if (needsPortfolio) {
        bindPortfolio();
      }
    }
  }
});

window.addEventListener("load", () => {
  registerServiceWorker();
});
