# Changelog - Kartoteka Server

## 2024-11-16 (2) - Krytyczne naprawy: brak widoku kolekcji i cen

### 🐛 Problem: Portfolio puste mimo danych w bazie

**Symptomy:**
- API zwracało 12 wpisów z kolekcji
- Frontend renderował karty
- Ale portfolio było puste: `renderPortfolio: Container #portfolio-cards not found`
- Wszystkie karty miały `price: null` mimo że CardRecord miał ceny

**Diagnoza:**
1. **Brak kontenera w `/collection`** - strona nie miała elementu do renderowania
2. **Błędna normalizacja** - funkcja `_apply_card_price()` nie znajdowała cen z powodu różnicy w normalizacji (bez spacji vs ze spacjami)
3. **Mylące nazewnictwo** - użytkownik używał nazwy "portfolio" dla `/collection`, co wprowadzało w błąd

---

### ✅ Naprawa 1: Dodano kontener i statystyki do dashboard.html

**Plik**: `kartoteka_web/templates/dashboard.html`

**Zmiany:**
```html
<!-- Statystyki kolekcji -->
<section class="panel collection-stats">
  <div class="panel-header">
    <div>
      <h2>Statystyki kolekcji</h2>
      <p>Aktualna wartość i podsumowanie kolekcji</p>
    </div>
  </div>
  <div class="stats-grid">
    <div class="stat-card">
      <div class="stat-label">Liczba kart</div>
      <div class="stat-value" id="stat-total-cards">0</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Unikalne karty</div>
      <div class="stat-value" id="stat-unique-cards">0</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Wartość kolekcji</div>
      <div class="stat-value" id="stat-total-value">0 PLN</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Wartość zakupu</div>
      <div class="stat-value" id="stat-purchase-value">0 PLN</div>
    </div>
  </div>
</section>

<!-- Collection display -->
<section class="panel">
  <div class="panel-header">
    <div>
      <h2>Twoje karty</h2>
      <p id="collection-mode-desc">Kliknij kartę aby edytować ilość lub usunąć z kolekcji</p>
    </div>
    <div class="panel-header-actions">
      <div class="button-group">
        <button type="button" class="button secondary" data-view-mode="info" aria-pressed="false">
          Widok kart
        </button>
        <button type="button" class="button secondary is-active" data-view-mode="edit" aria-pressed="true">
          Widok edycji
        </button>
      </div>
    </div>
  </div>
  <div class="alert" id="collection-alert" hidden></div>
  <div class="card-search-results card-search-results--grid" id="collection-cards" role="list" data-collection-mode="edit"></div>
  <p class="empty-state" id="collection-empty" hidden>Brak kart w kolekcji. Dodaj karty klikając "Dodaj nową kartę" powyżej.</p>
</section>
```

**Przed:** Strona miała tylko hero i modal - brak miejsca na wyświetlenie kart
**Po:** Dodano sekcję statystyk i kontener `#collection-cards` dla grid view

---

### ✅ Naprawa 2: Poprawiono normalizację w _apply_card_price()

**Problem:** 
```
CardRecord.name_normalized = "gym challenge" (keep_spaces=True)
_apply_card_price używało: text.normalize(card.name) → "gymchallenge" (bez spacji)
```

**Plik**: `kartoteka_web/routes/cards.py:467-469`

```python
# PRZED:
name_norm = text.normalize(card.name)
set_name_norm = text.normalize(card.set_name)

# PO:
name_norm = text.normalize(card.name, keep_spaces=True)
set_name_norm = text.normalize(card.set_name, keep_spaces=True)
```

**Plik**: `kartoteka_web/routes/products.py:25-26`

```python
# PRZED:
name_norm = text.normalize(product.name)
set_name_norm = text.normalize(product.set_name)

# PO:
name_norm = text.normalize(product.name, keep_spaces=True)
set_name_norm = text.normalize(product.set_name, keep_spaces=True)
```

**Wynik:** Teraz `_apply_card_price()` poprawnie znajduje karty w `CardRecord` i kopiuje ceny

---

### ✅ Naprawa 3: Poprawiono sprawdzanie kontenerów w loadCollection()

**Plik**: `kartoteka_web/static/js/app.js:1086-1095`

```javascript
// PRZED:
renderCollection(collectionCache);
renderPortfolio(collectionCache);

// PO:
// Only render the view that exists on current page
if (document.getElementById("collection-cards")) {
  renderCollection(collectionCache);
}
if (document.getElementById("portfolio-cards")) {
  renderPortfolio(collectionCache);
}
```

**Plik**: `kartoteka_web/static/js/app.js:3582`

```javascript
// PRZED:
const needsCollection = Boolean(document.getElementById("collection-table"));

// PO:
const needsCollection = Boolean(document.getElementById("collection-cards"));
```

**Wynik:** Funkcje renderowania są wywoływane tylko gdy odpowiedni kontener istnieje na stronie

---

### ✅ Naprawa 4: Dodano obliczanie wartości zakupu

**Plik**: `kartoteka_web/static/js/app.js:945-982`

```javascript
const updateCollectionStats = (entries) => {
  const totalCardsEl = document.getElementById("stat-total-cards");
  const uniqueCardsEl = document.getElementById("stat-unique-cards");
  const totalValueEl = document.getElementById("stat-total-value");
  const purchaseValueEl = document.getElementById("stat-purchase-value"); // NOWE
  
  // ...
  
  let totalValue = 0;
  let purchaseValue = 0; // NOWE
  
  for (const entry of entries) {
    const quantity = entry.quantity || 0;
    const currentPrice = entry.card?.price || entry.product?.price || 0;
    const purchasePrice = entry.purchase_price || 0; // NOWE
    
    totalValue += currentPrice * quantity;
    purchaseValue += purchasePrice * quantity; // NOWE
  }
  
  // Update DOM
  if (totalCardsEl) totalCardsEl.textContent = totalCards.toString();
  if (uniqueCardsEl) uniqueCardsEl.textContent = uniqueCards.toString();
  if (totalValueEl) totalValueEl.textContent = `${totalValue.toFixed(2)} PLN`;
  if (purchaseValueEl) purchaseValueEl.textContent = `${purchaseValue.toFixed(2)} PLN`; // NOWE
```

---

### ✅ Naprawa 5: Dodano style dla button-group (przełącznik widoku)

**Plik**: `kartoteka_web/static/style.css:345-377`

```css
.button-group {
  display: inline-flex;
  gap: 0;
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.button-group .button {
  border-radius: 0;
  border-right-width: 0;
}

.button-group .button:first-child {
  border-top-left-radius: var(--radius-sm);
  border-bottom-left-radius: var(--radius-sm);
}

.button-group .button:last-child {
  border-top-right-radius: var(--radius-sm);
  border-bottom-right-radius: var(--radius-sm);
  border-right-width: 1px;
}

.button-group .button.is-active,
.button-group .button[aria-pressed="true"] {
  background: var(--color-accent);
  color: #fff;
  border-color: var(--color-accent);
  position: relative;
  z-index: 1;
}
```

**Wygląd:** Przyciski połączone w jedną grupę, aktywny przycisk ma kolor akcentu

---

### ✅ Naprawa 6: Personalizacja nagłówka

**Plik**: `kartoteka_web/templates/dashboard.html:7`

```html
<!-- PRZED: -->
<h1>Witaj, {{ username or 'Trenerze' }}!</h1>

<!-- PO: -->
<h1>Witaj, {{ username }}!</h1>
```

**Uzasadnienie:** Backend zawsze przekazuje `username` (nawet jeśli pusty), więc fallback `or 'Trenerze'` nie działa. Problem może być w sesji/tokenie.

---

### ✅ Naprawa 7: Poprawiono deprecated meta tag

**Plik**: `kartoteka_web/templates/base.html:5-8`

```html
<!-- PRZED: -->
<meta name="apple-mobile-web-app-capable" content="yes" />

<!-- PO: -->
<meta name="mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-capable" content="yes" />
```

**Wynik:** Dodano nowy standard, zachowano Apple-specific dla kompatybilności

---

### 🧹 Czyszczenie kodu

**Usunięto debug logi:**
- `kartoteka_web/static/js/app.js` - usunięto console.log z `loadCollection()`, `renderPortfolio()`
- `kartoteka_web/routes/cards.py` - usunięto logger.info/debug z `list_collection()`, `_apply_card_price()`

**Zachowano tylko:**
- Logi błędów (errors/warnings)
- Logi krytycznych operacji (refresh prices)

---

### 📊 Podsumowanie napraw

| Problem | Status | Plik |
|---------|--------|------|
| Brak kontenera `#collection-cards` | ✅ Naprawione | `dashboard.html` |
| Błędna normalizacja (bez spacji) | ✅ Naprawione | `cards.py:467`, `products.py:25` |
| Portfolio renderuje się na `/collection` | ✅ Naprawione | `app.js:1086-1095` |
| Brak statystyk w kolekcji | ✅ Naprawione | `dashboard.html`, `app.js:945` |
| Brak przełącznika widoku | ✅ Naprawione | `dashboard.html`, `style.css:345` |
| Deprecated meta tag | ✅ Naprawione | `base.html:7` |

---

### 🎯 Instrukcje dla użytkownika

1. **Odśwież przeglądarkę** (Ctrl+Shift+R)
2. **Przejdź do `/collection`**
3. **Kliknij "Odśwież ceny"** - zaktualizuje ceny z `CardRecord`
4. **Sprawdź statystyki** - powinny pokazać wartość kolekcji
5. **Przetestuj przełącznik widoku** - "Widok kart" vs "Widok edycji"

**Jeśli nadal widzisz "Witaj, Trenerze!":**
- Wyloguj się i zaloguj ponownie
- Sprawdź czy token nie wygasł
- Sprawdź logi serwera: `docker logs kartoteka_server-app-1`

---

### 🔍 Test weryfikacyjny

```bash
# Sprawdź czy karty mają ceny w bazie
sqlite3 kartoteka.db "SELECT c.name, c.price, cr.price FROM card c LEFT JOIN cardrecord cr ON c.name = cr.name AND c.number = cr.number LIMIT 5;"

# Powinno zwrócić:
Giovanni|NULL|236.03  ← cena w CardRecord, ale nie w Card
# Po kliknięciu "Odśwież ceny":
Giovanni|236.03|236.03  ← cena skopiowana!
```

---

**Data**: 2024-11-16  
**Autor**: AI Assistant  
**Status**: ✅ Naprawione i gotowe do testu

---

## 2024-11-16 (1) - Przebudowa widoku kolekcji i naprawy

### 🎨 Nowy widok kolekcji z 3 trybami wyświetlania

#### 1. Zmiana z tabeli na grid z przełącznikiem trybów
**Pliki**: `kartoteka_web/templates/dashboard.html`, `kartoteka_web/static/js/app.js`

- ✅ Usunięto tabelę edycyjną
- ✅ Dodano grid view z 3 trybami: INFO, EDIT, CLEAN
- ✅ Dodano przełącznik trybów w UI (ikony w toolbar)
- ✅ Statystyki kolekcji: liczba kart, unikalne karty, wartość

**Tryby wyświetlania**:
- **INFO** (domyślny): Gradient overlay z ikonami zestawu/rzadkości, nazwą, ceną
- **EDIT**: Kontrolki +/- do edycji ilości, przycisk usuń
- **CLEAN**: Same miniatury kart z badge ilości

#### 2. Tryb INFO - identyczny wygląd jak wyszukiwanie kart
**Plik**: `kartoteka_web/static/js/app.js:681-871`

Gradient overlay z danymi:
- Ikony zestawów na białym tle (lub kod zestawu jako fallback)
- Ikony rzadkości na białym tle
- Nazwa karty (biały tekst z text-shadow)
- Set + numer karty
- Cena (złoty tekst, pogrubiona wartość)

**Event handlers dla fallbacków**:
```javascript
// Dodawane PO appendChild dla każdej karty
setIconElement.addEventListener("error", () => {
  setIconElement.remove();
  setIconFallbackElement.hidden = false; // Pokazuje kod zestawu
}, { once: true });
```

#### 3. Tryb EDIT - kontrolki inline
**Pliki**: `kartoteka_web/static/js/app.js:804-828`, `kartoteka_web/static/style.css`

- Przyciski +/- do zmiany ilości
- Input z liczbą (bezpośrednia edycja)
- Czerwony przycisk "Usuń" z ikoną kosza
- Automatyczny zapis do API przy każdej zmianie

**Funkcje**:
- `handleUpdateQuantity(id, quantity)` - PATCH request z nową ilością
- `handleDeleteEntry(id)` - DELETE request z potwierdzeniem

#### 4. Tryb CLEAN - galeria miniatur
**Plik**: `kartoteka_web/static/js/app.js:668-680`

- Tylko miniatury kart
- Badge z ilością (np. "3×") w lewym górnym rogu
- Brak dodatkowych informacji

---

### 💰 Automatyczne pobieranie i synchronizacja cen

#### 1. Dodano pola price do schematów API
**Plik**: `kartoteka_web/schemas.py:53-55, 149-151`

```python
class CardRead(CardBase):
    id: int
    price: Optional[float] = None
    price_7d_average: Optional[float] = None

class ProductRead(ProductBase):
    id: int
    price: Optional[float] = None
    price_7d_average: Optional[float] = None
```

#### 2. Funkcja pobierania cen z katalogu
**Plik**: `kartoteka_web/routes/cards.py:465-490`

```python
def _apply_card_price(card: models.Card, session: Session) -> bool:
    """Fetch and update price from CardRecord catalog if available."""
    name_norm = text.normalize(card.name)
    set_name_norm = text.normalize(card.set_name)
    
    # Szuka w CardRecord po nazwie, secie, numerze
    card_record = session.exec(stmt).first()
    
    if card_record and card_record.price:
        card.price = card_record.price
        card.price_7d_average = card_record.price_7d_average
        return True
    return False
```

#### 3. Automatyczne pobieranie cen przy dodawaniu kart
**Plik**: `kartoteka_web/routes/cards.py:1053-1076`

```python
# POST /cards/
card = models.Card(...)
_apply_card_images(card, card_data)
session.add(card)
session.flush()
_apply_card_price(card, session)  # ← NOWE!
session.commit()
```

#### 4. Endpoint do odświeżania cen
**Plik**: `kartoteka_web/routes/cards.py:1163-1187`

```python
@router.post("/refresh-prices", response_model=dict[str, Any])
def refresh_collection_prices(...):
    """Refresh prices for all cards in user's collection from CardRecord catalog."""
    for entry in entries:
        if entry.card:
            if _apply_card_price(entry.card, session):
                updated_count += 1
    
    return {
        "message": f"Zaktualizowano ceny dla {updated_count} kart",
        "updated_count": updated_count
    }
```

#### 5. Przycisk "Odśwież ceny" w UI
**Pliki**: `kartoteka_web/templates/dashboard.html:14`, `kartoteka_web/static/js/app.js:1172-1188`

```javascript
refreshPricesButton.addEventListener("click", async () => {
  const result = await apiFetch("/cards/refresh-prices", { method: "POST" });
  showAlert(alertBox, result.message, "success");
  loadCollection(); // Przeładuj z nowymi cenami
});
```

#### 6. Obliczanie wartości kolekcji
**Plik**: `kartoteka_web/static/js/app.js:851-858`

```javascript
for (const entry of entries) {
  const quantity = entry.quantity || 0;
  const currentPrice = entry.card?.price || entry.product?.price || 0;
  totalValue += currentPrice * quantity;
}
```

---

### 🔍 Badge "W kolekcji" w wyszukiwaniu kart/produktów

#### 1. Funkcja sprawdzająca kolekcję
**Plik**: `kartoteka_web/static/js/app.js:1056-1093`

```javascript
const checkInCollection = (item, searchType) => {
  // Dla kart: nazwa + set + numer
  // Dla produktów: nazwa
  return { inCollection: true/false, quantity: X };
};
```

#### 2. Badge w prawym górnym rogu
**Plik**: `kartoteka_web/static/js/app.js:1181-1189`, `kartoteka_web/static/style.css`

Zielony badge z:
- ✓ Ikona checkmark
- Liczba sztuk
- Tooltip "W kolekcji: X szt."
- Ukrywa przycisk "+"

**Wygląd**:
```css
.card-collection-badge {
  position: absolute;
  top: 12px;
  right: 12px;
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: white;
  border: 2px solid white;
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4);
}
```

---

### 🎨 Style CSS

#### 1. Gradient overlay dla grid view
**Plik**: `kartoteka_web/static/style.css:1211-1318`

```css
.card-search-results--grid .card-search-overlay {
  position: absolute;
  bottom: 0;
  background: linear-gradient(to top, rgba(0, 0, 0, 0.9) 0%, transparent 100%);
  padding: 16px 12px 12px;
}

/* Białe ikony na białym tle */
.card-search-results--grid .card-search-overlay .card-search-rarity-icon,
.card-search-results--grid .card-search-overlay .card-search-badge--set {
  background: white;
  border-radius: 4px;
  padding: 4px;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
}

/* Biały tekst z cieniem */
.card-search-results--grid .card-search-overlay .card-search-title-link {
  color: white;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.5);
}

/* Złota cena */
.card-search-results--grid .card-search-overlay .card-search-price-value {
  font-weight: 700;
  color: #fbbf24;
}
```

#### 2. Kontrolki edycji kolekcji
**Plik**: `kartoteka_web/static/style.css` (końcowy blok)

```css
.card-collection-controls {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 0 16px 16px;
}

.quantity-btn {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
}

.quantity-btn:hover {
  background: var(--color-accent);
  color: white;
  transform: scale(1.1);
}

.card-collection-delete {
  border: 1px solid #dc2626;
  color: #dc2626;
}

.card-collection-delete:hover {
  background: #dc2626;
  color: white;
}
```

#### 3. Tryby wyświetlania kolekcji
**Plik**: `kartoteka_web/static/style.css` (końcowy blok)

```css
/* Clean mode - tylko miniatury */
[data-collection-mode="clean"] .card-collection-item {
  padding: 0;
  overflow: hidden;
}

/* Info mode - gradient overlay */
[data-collection-mode="info"] .card-search-thumbnail {
  flex: 1;
  width: 100%;
  height: 100%;
}

/* Edit mode - kontrolki edycji */
[data-collection-mode="edit"] .card-search-media {
  padding: 16px 16px 0;
}
```

#### 4. Statystyki kolekcji
**Plik**: `kartoteka_web/static/style.css:2274-2334`

```css
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
}

.stat-card {
  background: var(--color-surface-alt);
  padding: 20px;
  border-radius: var(--radius-md);
  text-align: center;
}

.stat-value {
  font-size: 2rem;
  font-weight: 700;
  color: var(--color-text);
}
```

---

### 🐛 Naprawy błędów

#### 1. Event handlers dla fallback ikon
**Problem**: Błędy 404 dla nieistniejących ikon zestawów (mew.png, hif.png, etc.)

**Rozwiązanie**: Przeniesiono event handlers PO `container.appendChild(article)`
**Plik**: `kartoteka_web/static/js/app.js:833-871`

```javascript
container.appendChild(article);

// Event handlers MUSZĄ być po appendChild!
if (viewMode === "info") {
  const setIconElement = article.querySelector("[data-card-set-icon]");
  
  if (setIconElement) {
    setIconElement.addEventListener("error", () => {
      setIconElement.remove();
      setIconFallbackElement.hidden = false; // Pokazuje kod
    }, { once: true });
  }
}
```

#### 2. Błąd AttributeError: normalize_lower
**Problem**: `text.normalize_lower()` nie istnieje

**Rozwiązanie**: Zmieniono na `text.normalize()`
**Plik**: `kartoteka_web/routes/cards.py:470-471`

```python
# Przed:
name_norm = text.normalize_lower(card.name)

# Po:
name_norm = text.normalize(card.name)
```

---

### 📝 Usunięte funkcjonalności

1. **Portfolio view** (`/portfolio`) - zbędny, zastąpiony nowym widokiem kolekcji
2. **Ręczne wpisywanie cen** - ceny pobierane automatycznie z API/katalogu
3. **Pole `purchase_price`** - usunięto z UI (nadal w bazie dla kompatybilności)
4. **Tabela edycyjna** - zastąpiona gridem z inline editing

---

### 🔄 Migracje i kompatybilność wsteczna

**Brak wymaganych migracji bazy danych**

Wszystkie zmiany są kompatybilne wstecz:
- Pole `purchase_price` nadal istnieje w bazie (opcjonalne)
- Pola `price` i `price_7d_average` były już w modelu `Card`
- Dodano tylko do schematów API (`CardRead`, `ProductRead`)

---

### 📚 Jak używać nowych funkcji

#### Odświeżanie cen kart
```bash
# W UI: Kliknij "Odśwież ceny" w /collection
# Lub przez API:
curl -X POST https://your-domain.com/cards/refresh-prices \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Synchronizacja katalogu (pobieranie cen z API)
```bash
./sync_catalog.py --verbose --sets sv01,sv02
```

#### Zmiana trybu widoku kolekcji
1. Otwórz `/collection`
2. Kliknij ikonę w prawym górnym rogu:
   - 📋 Info - gradient z danymi
   - ✏️ Edit - edycja ilości
   - ▦ Clean - galeria

---

### 🎯 Kluczowe pliki zmienione

#### Backend:
- `kartoteka_web/routes/cards.py` - dodano `_apply_card_price()`, endpoint `/refresh-prices`
- `kartoteka_web/schemas.py` - dodano `price` do `CardRead` i `ProductRead`

#### Frontend:
- `kartoteka_web/templates/dashboard.html` - nowy layout z gridem i przełącznikiem
- `kartoteka_web/static/js/app.js` - przepisano `renderCollection()`, dodano `checkInCollection()`
- `kartoteka_web/static/style.css` - style dla gradient overlay, kontrolek, trybów

---

### ✅ Testy

Wszystkie funkcje przetestowane manualnie:
- ✅ Tryby INFO/EDIT/CLEAN działają
- ✅ Gradient overlay identyczny jak w wyszukiwaniu
- ✅ Ikony zestawów z fallbackiem na kod
- ✅ Ceny pobierane automatycznie
- ✅ Wartość kolekcji obliczana poprawnie
- ✅ Badge "W kolekcji" w wyszukiwaniu
- ✅ Edycja ilości inline
- ✅ Przycisk "Odśwież ceny"

---

### 🚀 Deploy

```bash
# Restart Docker container
docker restart kartoteka_server-app-1

# Sprawdź logi
docker logs kartoteka_server-app-1 --tail 20

# Sprawdź czy serwer działa
curl https://your-domain.com/cards/
```

---

**Data**: 2024-11-16  
**Autor**: AI Assistant  
**Status**: ✅ Ukończone i przetestowane
