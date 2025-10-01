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
      const totalLabel = totalCount && totalCount > items.length ? ` z ${totalCount}` : "";
      summaryElement.textContent = `Znaleziono ${items.length}${totalLabel} wyników.`;
    }
    for (const item of items) {
      const article = document.createElement("article");
      article.className = "card-search-item";
      const numberLabel = item.number_display || item.number;
      article.innerHTML = `
        <div class="card-search-info">
          <h3>${escapeHtml(item.name)}</h3>
          <p>${escapeHtml(item.set_name || "")}</p>
          <p class="card-search-meta">${escapeHtml(numberLabel || "")}</p>
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
      container.appendChild(article);
    }
  };

  const setupAddCardPage = () => {
    const form = document.querySelector("[data-card-search-form]");
    if (!form) return;
    const alertBox = document.getElementById("add-card-alert");
    const summary = document.getElementById("card-search-summary");
    const emptyMessage = document.getElementById("card-search-empty");

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const queryInput = form.querySelector("input[name='query']");
      const query = queryInput ? queryInput.value.trim() : "";
      if (!query) {
        showAlert(alertBox, "Wpisz nazwę lub numer karty.", "error");
        queryInput?.focus();
        return;
      }
      showAlert(alertBox, "Szukam kart…");
      try {
        const params = new URLSearchParams({ query });
        const data = await apiFetch(`/cards/search?${params.toString()}`);
        renderSearchResults(data?.items || [], summary, emptyMessage, data?.total || 0);
        showAlert(alertBox, "");
      } catch (error) {
        showAlert(alertBox, error.message || "Nie udało się pobrać wyników.", "error");
      }
    });

    const results = document.getElementById("card-search-results");
    if (results) {
      results.addEventListener("submit", async (event) => {
        const target = event.target;
        if (!(target instanceof HTMLFormElement)) return;
        event.preventDefault();
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
          loadCollection();
        } catch (error) {
          showAlert(alertTarget, error.message || "Nie udało się dodać karty.", "error");
        }
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
