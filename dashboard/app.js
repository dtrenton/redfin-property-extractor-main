const CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSXqJIzYh_rVeZmiQyf8YweSAtG3aUhi4_MdrAYVn8hTsLJZjvWvBYD46o3BWetRHCGkfPTI65-Hvb8/pub?gid=0&single=true&output=csv";

const sheetHeaders = [
  "address",
  "listing_status",
  "price",
  "sq_ft",
  "price_per_sqft",
  "beds",
  "baths",
  "year_built",
  "days_on_redfin",
  "dom_status",
  "views",
  "favorites",
  "views_per_day",
  "favorites_per_day",
  "interest_velocity",
  "favorite_conversion_rate",
  "buyer_interest_signal",
  "listed_count_1y",
  "listing_removed_count_1y",
  "price_change_count_1y",
  "garage",
  "garage_type",
  "basement",
  "flooring",
  "fence",
  "urgency_score",
  "strategy_category",
  "garage_fit",
  "final_decision",
  "date_added",
  "listing_url",
  "image_folder",
  "construction_materials",
  "foundation_details",
  "roof",
  "water_source",
  "heating",
  "cooling",
  "garage_spaces",
  "garage_amenities",
  "finished_basement_pct",
  "acres",
  "price_before_reduction",
  "price_reduction_date",
  "price_reduction_amount",
  "price_reduction_pct",
];

const detailSections = [
  {
    title: "Market Activity",
    fields: [
      "views_per_day",
      "favorites_per_day",
      "favorite_conversion_rate",
      "buyer_interest_signal",
      "listed_count_1y",
      "listing_removed_count_1y",
      "price_change_count_1y",
    ],
  },
  {
    title: "Structure & Utilities",
    fields: [
      "construction_materials",
      "foundation_details",
      "roof",
      "water_source",
      "heating",
      "cooling",
    ],
  },
  {
    title: "Garage & Basement",
    fields: [
      "garage_fit",
      "garage_spaces",
      "garage_amenities",
      "finished_basement_pct",
    ],
  },
  {
    title: "Pricing History",
    fields: [
      "price_before_reduction",
      "price_reduction_date",
      "price_reduction_amount",
      "price_reduction_pct",
    ],
  },
  {
    title: "Risk / Leverage / Urgency",
    fields: [
      "strategy_category",
      "final_decision",
      "urgency_score",
      "buyer_leverage_score",
      "property_risk_score",
      "property_risk_flags",
      "buyer_leverage_flags",
      "urgency_flags",
      "strategy_fit_flags",
      "notes",
    ],
  },
  {
    title: "Source & Files",
    fields: [
      "source_pdf",
      "image_folder",
      "listing_url",
    ],
  },
];

const cardDisplayFields = [
  "address",
  "listing_status",
  "price",
  "price_per_sqft",
  "beds",
  "baths",
  "sq_ft",
  "acres",
  "lot_size",
  "lot_size_square_feet",
  "date_added",
  "listing_date",
  "days_on_redfin",
  "dom_status",
  "views",
  "favorites",
  "interest_velocity",
  "garage",
  "garage_type",
  "basement",
  "fence",
  "flooring",
];

let properties = [];

const elements = {
  cards: document.querySelector("#cards"),
  emptyState: document.querySelector("#empty-state"),
  count: document.querySelector("#property-count"),
  search: document.querySelector("#search-input"),
  strategy: document.querySelector("#strategy-filter"),
  garageFit: document.querySelector("#garage-fit-filter"),
  sort: document.querySelector("#sort-select"),
  sortDirection: document.querySelector("#sort-direction"),
  modal: document.querySelector("#details-modal"),
  modalTitle: document.querySelector("#details-title"),
  modalContent: document.querySelector("#details-content"),
  modalClose: document.querySelector("#details-close"),
};

function formatCurrency(value) {
  const number = parseNumber(value);
  if (number === null) return "-";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(number);
}

function formatNumber(value, digits = 0) {
  const number = parseNumber(value);
  if (number === null) return "-";
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(number);
}

function parseNumber(value) {
  if (value === null || value === undefined || value === "" || value === "-") return null;
  const number = Number(String(value).replace(/[$,%\s,]/g, ""));
  return Number.isFinite(number) ? number : null;
}

function parseDateValue(value) {
  if (value === null || value === undefined || value === "" || value === "-") return null;
  const parsed = Date.parse(String(value));
  return Number.isNaN(parsed) ? null : parsed;
}

function columnLabel(header) {
  return header
    .split("_")
    .map((piece) => {
      if (piece.toLowerCase() === "sqft") return "Sq Ft";
      if (piece.toLowerCase() === "dom") return "DOM";
      if (piece.toLowerCase() === "url") return "URL";
      return piece.charAt(0).toUpperCase() + piece.slice(1);
    })
    .join(" ");
}

function normalizeText(value) {
  return String(value ?? "").toLowerCase();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;")
    .replaceAll("'", "&#039;");
}

function hasDisplayValue(value) {
  return !(
    value === null
    || value === undefined
    || value === ""
    || value === "-"
    || value === "MISSING"
    || value === "Not Provided"
    || value === "No Info"
  );
}

function displayValue(value) {
  return hasDisplayValue(value) ? String(value) : "—";
}

function displayCurrency(value) {
  const formatted = formatCurrency(value);
  return formatted === "-" ? "—" : formatted;
}

function displayNumber(value, digits = 0) {
  const formatted = formatNumber(value, digits);
  return formatted === "-" ? "—" : formatted;
}

function displayPricePerSqft(value) {
  const number = parseNumber(value);
  return number === null ? "—" : `$${formatNumber(number, 0)}`;
}

function compactDate(value) {
  if (!hasDisplayValue(value)) return "";
  const parsed = parseDateValue(value);
  if (parsed === null) return String(value);
  return new Intl.DateTimeFormat("en-CA").format(new Date(parsed));
}

function lotDisplay(property) {
  if (hasDisplayValue(property.acres)) return `${displayValue(property.acres)} ac`;
  if (hasDisplayValue(property.lot_size)) return displayValue(property.lot_size);
  if (hasDisplayValue(property.lot_size_square_feet)) return `${displayNumber(property.lot_size_square_feet)} sf lot`;
  return "—";
}

function listingDateDisplay(property) {
  if (hasDisplayValue(property.date_added)) return property.date_added;
  if (hasDisplayValue(property.listing_date)) return property.listing_date;
  return "—";
}

function bedroomsBathsDisplay(property) {
  return `${displayValue(property.beds)} bd / ${displayValue(property.baths)} ba`;
}

function basementDisplay(value) {
  const normalized = normalizeText(value);
  if (!hasDisplayValue(value)) return "—";
  if (
    normalized === "no"
    || normalized === "none"
    || normalized === "no basement"
    || normalized === "does not apply"
  ) {
    return "No";
  }
  return "Yes";
}

function statusClass(status) {
  const normalized = normalizeText(status || "For Sale").replace(/\s+/g, "-");
  if (normalized.includes("sold")) return "status-sold";
  if (normalized.includes("pending")) return "status-pending";
  return "status-for-sale";
}

function listingStatusDisplay(status) {
  const normalized = normalizeText(status);
  if (normalized.includes("sold")) return "Sold";
  if (normalized.includes("pending")) return "Pending";
  return "For Sale";
}

function urgencyInfo(property) {
  const score = parseNumber(property.urgency_score);
  const text = normalizeText(property.urgency_score);
  if (score !== null) {
    if (score <= 4) {
      if (score >= 4) return { className: "urgency-red", label: "Act quickly" };
      if (score >= 3) return { className: "urgency-orange", label: "Elevated urgency" };
      if (score >= 2) return { className: "urgency-yellow", label: "Moderate urgency" };
      return { className: "urgency-green", label: "Low urgency / watch" };
    }
    if (score >= 75) return { className: "urgency-red", label: "Act quickly" };
    if (score >= 50) return { className: "urgency-orange", label: "Elevated urgency" };
    if (score >= 25) return { className: "urgency-yellow", label: "Moderate urgency" };
    return { className: "urgency-green", label: "Low urgency / watch" };
  }
  if (text.includes("high") || text.includes("act")) return { className: "urgency-red", label: "Act quickly" };
  if (text.includes("elevated")) return { className: "urgency-orange", label: "Elevated urgency" };
  if (text.includes("moderate")) return { className: "urgency-yellow", label: "Moderate urgency" };
  return { className: "urgency-green", label: "Low urgency / watch" };
}

function buyerEngagement(property) {
  if (hasDisplayValue(property.buyer_interest_signal)) return property.buyer_interest_signal;
  if (hasDisplayValue(property.interest_velocity)) return `${property.interest_velocity} interest`;
  const views = parseNumber(property.views);
  if (views === null) return "Buyer interest unclear";
  if (views >= 100) return "High buyer engagement";
  if (views >= 40) return "Moderate buyer engagement";
  return "Low buyer engagement";
}

function domDisplay(property) {
  if (hasDisplayValue(property.days_on_redfin)) return `${property.days_on_redfin} DOM`;
  if (hasDisplayValue(property.dom_status)) return property.dom_status;
  return "—";
}

function priceReductionText(property) {
  const count = parseNumber(property.price_change_count_1y);
  const hasReductionData = hasDisplayValue(property.price_reduction_pct)
    || hasDisplayValue(property.price_reduction_date)
    || hasDisplayValue(property.price_reduction_amount)
    || (count !== null && count > 0);
  if (!hasReductionData) return "";

  const parts = [];
  if (hasDisplayValue(property.price_reduction_pct)) parts.push(displayValue(property.price_reduction_pct));
  if (hasDisplayValue(property.price_reduction_amount) && !parts.length) parts.push(displayValue(property.price_reduction_amount));

  const date = compactDate(property.price_reduction_date);
  let text = "↓ Price drop";
  if (parts.length) text += `: ${parts.join(" ")}`;
  if (date) text += ` on ${date}`;
  if (!parts.length && !date && count !== null && count > 0) text += `: ${count} change${count === 1 ? "" : "s"} in 1y`;
  return text;
}

function sortChipValue(property) {
  const field = elements.sort.value;
  const value = field === "garage_fit" ? getGarageFit(property) : property[field];
  return `Sorted by: ${columnLabel(field)} = ${displayValue(value)}`;
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let inQuotes = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];

    if (char === "\"") {
      if (inQuotes && next === "\"") {
        field += "\"";
        index += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (char === "," && !inQuotes) {
      row.push(field);
      field = "";
      continue;
    }

    if ((char === "\n" || char === "\r") && !inQuotes) {
      if (char === "\r" && next === "\n") index += 1;
      row.push(field);
      if (row.some((value) => value.trim() !== "")) rows.push(row);
      row = [];
      field = "";
      continue;
    }

    field += char;
  }

  row.push(field);
  if (row.some((value) => value.trim() !== "")) rows.push(row);
  return rows;
}

function csvToProperties(csvText) {
  const rows = parseCsv(csvText);
  if (rows.length < 2) return [];

  const headers = rows[0].map((header) => header.trim());
  return rows.slice(1).map((row) => {
    const property = {};
    headers.forEach((header, index) => {
      if (!header) return;
      property[header] = (row[index] ?? "").trim();
    });
    return property;
  }).filter((property) => Object.values(property).some((value) => value !== ""));
}

function getGarageFit(property) {
  if (property.garage_fit) return property.garage_fit;
  if (property.garage === "Yes") return "Garage Present";
  if (property.garage === "No") return "No Garage";
  return "Garage Unknown";
}

function populateSelect(select, values) {
  for (const value of values) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.append(option);
  }
}

function populateFilters(data) {
  const strategies = [...new Set(data.map((item) => item.strategy_category).filter(Boolean))].sort();
  const garageFits = [...new Set(data.map(getGarageFit).filter(Boolean))].sort();
  populateSelect(elements.strategy, strategies);
  populateSelect(elements.garageFit, garageFits);
}

function csvHeaders(data) {
  const dynamicHeaders = data.flatMap((property) => Object.keys(property));
  return [...new Set([...sheetHeaders, ...dynamicHeaders])];
}

function populateSortOptions(data = []) {
  elements.sort.replaceChildren();
  for (const header of csvHeaders(data)) {
    const option = document.createElement("option");
    option.value = header;
    option.textContent = columnLabel(header);
    elements.sort.append(option);
  }
  elements.sort.value = "price";
}

function getFilteredProperties() {
  const query = normalizeText(elements.search.value);
  const strategy = elements.strategy.value;
  const garageFit = elements.garageFit.value;

  return properties
    .filter((property) => {
      const propertyGarageFit = getGarageFit(property);
      const searchable = [
        property.address,
        property.strategy_category,
        property.final_decision,
        property.garage,
        property.garage_type,
        propertyGarageFit,
        property.basement,
        property.buyer_interest_signal,
      ].map(normalizeText).join(" ");

      const matchesQuery = !query || searchable.includes(query);
      const matchesStrategy = strategy === "all" || property.strategy_category === strategy;
      const matchesGarageFit = garageFit === "all" || propertyGarageFit === garageFit;

      return matchesQuery && matchesStrategy && matchesGarageFit;
    })
    .sort(sortProperties);
}

function sortProperties(a, b) {
  const column = elements.sort.value;
  const direction = elements.sortDirection.value === "desc" ? -1 : 1;
  const strategyRank = {
    "Competitive Target": 1,
    "Leverage Opportunity": 2,
    "Leverage Opportunity - No Garage": 3,
    Watch: 4,
    "Watch - No Garage": 5,
    "Manual Review": 6,
    Pass: 7,
    "Pass - No Garage": 8,
  };

  if (column === "strategy_category") {
    return ((strategyRank[a.strategy_category] ?? 99) - (strategyRank[b.strategy_category] ?? 99)) * direction;
  }

  const left = sortableValue(a, column);
  const right = sortableValue(b, column);

  if (left.empty && right.empty) return 0;
  if (left.empty) return 1;
  if (right.empty) return -1;

  if (left.type === "number" && right.type === "number") {
    return (left.value - right.value) * direction;
  }

  if (left.type === "date" && right.type === "date") {
    return (left.value - right.value) * direction;
  }

  return String(left.value).localeCompare(String(right.value), undefined, {
    numeric: true,
    sensitivity: "base",
  }) * direction;
}

function sortableValue(property, column) {
  const raw = column === "garage_fit" ? getGarageFit(property) : property[column];
  if (
    raw === null
    || raw === undefined
    || raw === ""
    || raw === "-"
    || raw === "MISSING"
    || raw === "No Info"
    || raw === "Not Provided"
  ) {
    return { empty: true };
  }

  const numeric = parseNumber(raw);
  if (numeric !== null && /(?:\d|\$|%)/.test(String(raw))) {
    return { empty: false, type: "number", value: numeric };
  }

  const date = parseDateValue(raw);
  if (date !== null && /(?:\d{1,2}\/\d{1,2}\/\d{2,4}|\d{4}-\d{2}-\d{2}|[A-Za-z]{3,9}\s+\d{1,2})/.test(String(raw))) {
    return { empty: false, type: "date", value: date };
  }

  return { empty: false, type: "text", value: raw };
}

function updateCount(filtered) {
  elements.count.textContent = `${filtered.length} ${filtered.length === 1 ? "property" : "properties"}`;
}

function renderCards(data) {
  elements.cards.innerHTML = "";
  elements.emptyState.textContent = "No matching properties.";
  elements.emptyState.hidden = data.length > 0;

  const fragment = document.createDocumentFragment();
  data.forEach((property, index) => {
    fragment.append(createCard(property, index));
  });
  elements.cards.append(fragment);
}

function detailFieldsForSection(property, section, usedFields) {
  const pairs = [];
  for (const field of section.fields) {
    if (!Object.prototype.hasOwnProperty.call(property, field)) continue;
    usedFields.add(field);
    if (hasDisplayValue(property[field])) pairs.push([field, property[field]]);
  }
  return pairs;
}

function renderDetailSection(title, pairs) {
  if (!pairs.length) return "";
  const rows = pairs.map(([field, value]) => `
    <div class="detail-row">
      <span>${escapeHtml(columnLabel(field))}</span>
      <strong>${renderDetailValue(field, value)}</strong>
    </div>
  `).join("");

  return `
    <section class="detail-section">
      <h3>${escapeHtml(title)}</h3>
      <div class="detail-grid">${rows}</div>
    </section>
  `;
}

function renderDetailValue(field, value) {
  if (field === "listing_url" && hasDisplayValue(value)) {
    const escaped = escapeHtml(value);
    return `<a href="${escaped}" target="_blank" rel="noopener">${escaped}</a>`;
  }
  return escapeHtml(value);
}

function openDetails(property) {
  const usedFields = new Set(cardDisplayFields);
  const sectionPairs = detailSections.map((section) => {
    const pairs = detailFieldsForSection(property, section, usedFields);
    return { ...section, pairs };
  });

  const extraPairs = Object.keys(property)
    .filter((field) => !usedFields.has(field) && hasDisplayValue(property[field]))
    .sort()
    .map((field) => [field, property[field]]);
  if (extraPairs.length) sectionPairs.push({ title: "Other Fields", pairs: extraPairs });

  elements.modalTitle.textContent = property.address || "Property";
  elements.modalContent.innerHTML = sectionPairs
    .map((section) => renderDetailSection(section.title, section.pairs))
    .join("");
  elements.modal.hidden = false;
  document.body.classList.add("modal-open");
}

function closeDetails() {
  elements.modal.hidden = true;
  elements.modalContent.innerHTML = "";
  document.body.classList.remove("modal-open");
}

function createCard(property) {
  const card = document.createElement("article");
  card.className = "property-card";

  const listingStatus = listingStatusDisplay(property.listing_status);
  const urgency = urgencyInfo(property);
  const priceDrop = priceReductionText(property);
  const listingLink = hasDisplayValue(property.listing_url)
    ? `<a class="open-link" href="${escapeHtml(property.listing_url)}" target="_blank" rel="noopener">Open Listing</a>`
    : `<span class="open-link disabled" aria-disabled="true">Open Listing</span>`;

  card.innerHTML = `
    <div class="card-main-row">
      <div class="title-block">
        <h2 class="address">${escapeHtml(property.address || "Unknown address")}</h2>
        <span class="status-pill ${statusClass(listingStatus)}">${escapeHtml(listingStatus)}</span>
      </div>
      <div class="primary-metrics">
        <span><strong>${displayCurrency(property.price)}</strong><small>Price</small></span>
        <span><strong>${displayPricePerSqft(property.price_per_sqft)}</strong><small>$/Sq Ft</small></span>
        <span><strong>${escapeHtml(bedroomsBathsDisplay(property))}</strong><small>Beds / Baths</small></span>
        <span><strong>${displayNumber(property.sq_ft)}</strong><small>Sq Ft</small></span>
        <span><strong>${escapeHtml(lotDisplay(property))}</strong><small>Lot</small></span>
        <span><strong>${escapeHtml(listingDateDisplay(property))}</strong><small>Added</small></span>
      </div>
      ${listingLink}
    </div>

    <div class="market-row">
      <span class="urgency-indicator ${urgency.className}" title="${escapeHtml(urgency.label)}" aria-label="${escapeHtml(urgency.label)}"></span>
      <span><strong>Engagement</strong> ${escapeHtml(buyerEngagement(property))}</span>
      <span><strong>Views</strong> ${displayNumber(property.views)}</span>
      <span><strong>Favorites</strong> ${displayNumber(property.favorites)}</span>
      <span><strong>DOM</strong> ${escapeHtml(domDisplay(property))}</span>
      ${priceDrop ? `<span class="price-drop">${escapeHtml(priceDrop)}</span>` : ""}
    </div>

    <div class="features-row">
      <span><strong>Garage</strong> ${escapeHtml(displayValue(property.garage))}</span>
      <span><strong>Type</strong> ${escapeHtml(displayValue(property.garage_type))}</span>
      <span><strong>Basement</strong> ${escapeHtml(basementDisplay(property.basement))}</span>
      <span><strong>Fence</strong> ${escapeHtml(displayValue(property.fence))}</span>
      <span><strong>Flooring</strong> ${escapeHtml(displayValue(property.flooring))}</span>
    </div>

    <div class="card-footer">
      <span class="sort-chip">${escapeHtml(sortChipValue(property))}</span>
      <div class="action-buttons">
        <button class="details-button" type="button">Details</button>
      </div>
    </div>
  `;

  card.querySelector(".details-button").addEventListener("click", () => {
    openDetails(property);
  });

  return card;
}

function render() {
  const filtered = getFilteredProperties();
  updateCount(filtered);
  renderCards(filtered);
}

function showDashboardError() {
  properties = [];
  elements.cards.innerHTML = "";
  updateCount([]);
  elements.emptyState.textContent = "Unable to load Google Sheets data.";
  elements.emptyState.hidden = false;
}

async function loadData() {
  if (!CSV_URL.trim()) {
    throw new Error("CSV_URL is blank");
  }

  const response = await fetch(CSV_URL, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`CSV request failed with status ${response.status}`);
  }

  const csvText = await response.text();
  const parsedProperties = csvToProperties(csvText);
  if (!parsedProperties.length) {
    throw new Error("CSV parsed with no property rows");
  }

  console.log(`Loaded ${parsedProperties.length} properties from CSV`);
  return parsedProperties;
}

async function init() {
  try {
    properties = await loadData();
    populateSortOptions(properties);
    populateFilters(properties);
  } catch (error) {
    console.error(error);
    populateSortOptions();
    showDashboardError();
  }

  elements.search.addEventListener("input", render);
  elements.strategy.addEventListener("change", render);
  elements.garageFit.addEventListener("change", render);
  elements.sort.addEventListener("change", render);
  elements.sortDirection.addEventListener("change", render);
  elements.modalClose.addEventListener("click", closeDetails);
  elements.modal.addEventListener("click", (event) => {
    if (event.target === elements.modal) closeDetails();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !elements.modal.hidden) closeDetails();
  });
  if (properties.length) render();
}

init();
