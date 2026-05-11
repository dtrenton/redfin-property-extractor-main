const CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSXqJIzYh_rVeZmiQyf8YweSAtG3aUhi4_MdrAYVn8hTsLJZjvWvBYD46o3BWetRHCGkfPTI65-Hvb8/pub?gid=0&single=true&output=csv";

const sheetHeaders = [
  "address",
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
    title: "Core Metrics",
    fields: [
      "address",
      "price",
      "sq_ft",
      "price_per_sqft",
      "beds",
      "baths",
      "year_built",
      "acres",
      "date_added",
      "listing_url",
      "image_folder",
    ],
  },
  {
    title: "Market Activity",
    fields: [
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
      "flooring",
      "fence",
    ],
  },
  {
    title: "Garage & Basement",
    fields: [
      "garage",
      "garage_fit",
      "garage_type",
      "garage_spaces",
      "garage_amenities",
      "basement",
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
    ],
  },
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
  metricCompetitive: document.querySelector("#metric-competitive"),
  metricLeverage: document.querySelector("#metric-leverage"),
  metricWatch: document.querySelector("#metric-watch"),
  metricPass: document.querySelector("#metric-pass"),
  metricManual: document.querySelector("#metric-manual"),
  metricNoGarage: document.querySelector("#metric-no-garage"),
  metricPps: document.querySelector("#metric-pps"),
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
  );
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

function strategyClass(strategy) {
  const text = normalizeText(strategy);
  if (text === "competitive target") return "competitive";
  if (text === "leverage opportunity") return "leverage";
  if (text === "leverage opportunity - no garage") return "leverage-no-garage";
  if (text === "watch - no garage") return "watch-no-garage";
  if (text === "pass - no garage") return "pass-no-garage";
  if (text.includes("pass")) return "pass";
  if (text.includes("manual") || text.includes("insufficient")) return "manual";
  if (text.includes("watch")) return "watch";
  if (text.includes("leverage")) return "leverage";
  return "competitive";
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
  elements.sort.value = "strategy_category";
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

function updateSummary(filtered) {
  elements.count.textContent = `${filtered.length} ${filtered.length === 1 ? "property" : "properties"}`;
  elements.metricCompetitive.textContent = filtered.filter((item) => item.strategy_category === "Competitive Target").length;
  elements.metricLeverage.textContent = filtered.filter((item) => normalizeText(item.strategy_category).includes("leverage opportunity")).length;
  elements.metricWatch.textContent = filtered.filter((item) => normalizeText(item.strategy_category).includes("watch")).length;
  elements.metricPass.textContent = filtered.filter((item) => normalizeText(item.strategy_category).includes("pass")).length;
  elements.metricManual.textContent = filtered.filter((item) => item.strategy_category === "Manual Review").length;
  elements.metricNoGarage.textContent = filtered.filter((item) => (
    item.strategy_category === "Leverage Opportunity - No Garage"
    || item.strategy_category === "Watch - No Garage"
  )).length;

  const ppsValues = filtered.map((item) => parseNumber(item.price_per_sqft)).filter((value) => value !== null).sort((a, b) => a - b);
  if (!ppsValues.length) {
    elements.metricPps.textContent = "-";
    return;
  }
  const middle = Math.floor(ppsValues.length / 2);
  const median = ppsValues.length % 2 ? ppsValues[middle] : (ppsValues[middle - 1] + ppsValues[middle]) / 2;
  elements.metricPps.textContent = `$${formatNumber(median, 0)}`;
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
  const usedFields = new Set();
  const sectionPairs = detailSections.map((section) => {
    const pairs = detailFieldsForSection(property, section, usedFields);
    return { ...section, pairs };
  });

  const extraPairs = Object.keys(property)
    .filter((field) => !usedFields.has(field) && hasDisplayValue(property[field]))
    .sort()
    .map((field) => [field, property[field]]);
  if (extraPairs.length) {
    sectionPairs[0].pairs = [...sectionPairs[0].pairs, ...extraPairs];
  }

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

  const strategy = property.strategy_category || "Watch";
  const decision = property.final_decision || "Watch";
  const garageFit = getGarageFit(property);
  const listingLink = property.listing_url
    ? `<a class="open-link" href="${property.listing_url}" target="_blank" rel="noopener">Open listing</a>`
    : "";

  card.innerHTML = `
    <div class="card-top">
      <h2 class="address">${property.address || "Unknown address"}</h2>
      <div class="badges">
        <span class="decision ${strategyClass(strategy)}">${strategy}</span>
        <span class="garage-fit">${garageFit}</span>
      </div>
    </div>

    <div class="facts">
      <div class="fact"><span>Price</span><strong>${formatCurrency(property.price)}</strong></div>
      <div class="fact"><span>Sq Ft</span><strong>${formatNumber(property.sq_ft)}</strong></div>
      <div class="fact"><span>$/Sq Ft</span><strong>$${formatNumber(property.price_per_sqft)}</strong></div>
      <div class="fact"><span>Beds / Baths</span><strong>${property.beds ?? "-"} / ${property.baths ?? "-"}</strong></div>
      <div class="fact"><span>Garage</span><strong>${property.garage || "-"}</strong></div>
      <div class="fact"><span>DOM</span><strong>${property.days_on_redfin || "-"}</strong></div>
      <div class="fact"><span>Decision</span><strong>${decision}</strong></div>
    </div>

    <div class="signals">
      <span class="signal">${property.interest_velocity || "-"}</span>
      <span class="signal">${property.buyer_interest_signal || "Buyer interest unclear"}</span>
      <span class="signal">${property.basement || "No Info"} basement</span>
      <span class="signal">${property.heating || "No Info"} heat</span>
    </div>

    <div class="card-actions">
      <span class="source">${property.construction_materials || "No Info"} · ${property.roof || "No Info"} roof</span>
      <div class="action-buttons">
        <button class="details-button" type="button">Details</button>
        ${listingLink}
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
  updateSummary(filtered);
  renderCards(filtered);
}

function showDashboardError() {
  properties = [];
  elements.cards.innerHTML = "";
  updateSummary([]);
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
