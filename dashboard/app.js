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
  status: document.querySelector("#status-filter"),
  sortPrimary: document.querySelector("#sort-primary"),
  sortSecondary: document.querySelector("#sort-secondary"),
  sortTertiary: document.querySelector("#sort-tertiary"),
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

function compactAddress(address) {
  if (!hasDisplayValue(address)) return "Unknown address";
  const street = String(address).split(",")[0].trim();
  const parts = street.split(/\s+/).filter(Boolean);
  if (parts.length <= 3) return street;
  return parts.slice(0, 3).join(" ");
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

function compactDomDisplay(property) {
  const days = parseNumber(property.days_on_redfin);
  if (days !== null) return `${formatNumber(days)}d`;
  if (hasDisplayValue(property.dom_status)) return property.dom_status;
  return "—";
}

function priceReductionCompact(property) {
  const count = parseNumber(property.price_change_count_1y);
  if (hasDisplayValue(property.price_reduction_pct)) return property.price_reduction_pct;
  if (hasDisplayValue(property.price_reduction_amount)) return property.price_reduction_amount;
  if (count !== null && count > 0) return `${count} change${count === 1 ? "" : "s"}`;
  return "";
}

function marketHeat(property) {
  const viewsPerDay = parseNumber(property.views_per_day);
  const favoritesPerDay = parseNumber(property.favorites_per_day);
  const conversion = parseNumber(property.favorite_conversion_rate);
  const days = parseNumber(property.days_on_redfin);
  const status = normalizeText(listingStatusDisplay(property.listing_status));
  const signal = normalizeText(property.buyer_interest_signal);
  const priceChanges = parseNumber(property.price_change_count_1y);
  let score = 0;

  if (viewsPerDay !== null) {
    if (viewsPerDay >= 25) score += 3;
    else if (viewsPerDay >= 10) score += 2;
    else if (viewsPerDay > 0) score += 1;
  }
  if (favoritesPerDay !== null) {
    if (favoritesPerDay >= 2) score += 2;
    else if (favoritesPerDay >= 0.75) score += 1;
  }
  if (conversion !== null) {
    if (conversion >= 0.08) score += 1;
    if (conversion >= 0.15) score += 1;
  }
  if (days !== null) {
    if (days <= 7) score += 2;
    else if (days <= 29) score += 1;
    else if (days >= 60) score -= 1;
  }
  if (status.includes("pending") || status.includes("sold")) score += 2;
  if (priceChanges !== null && priceChanges > 0) score -= 1;
  if (signal.includes("strong")) score += 2;
  else if (signal.includes("normal") || signal.includes("moderate")) score += 1;
  else if (signal.includes("low") || signal.includes("weak")) score -= 1;

  let flames = 0;
  if (score >= 8) flames = 4;
  else if (score >= 6) flames = 3;
  else if (score >= 3) flames = 2;
  else if (score >= 1) flames = 1;

  const labels = [
    "Very low market heat",
    "Weak urgency",
    "Moderate urgency",
    "Strong urgency",
    "Extremely hot / likely to move quickly",
  ];
  return {
    flames,
    label: labels[flames],
    className: `market-heat-${flames}`,
  };
}

function renderMarketHeat(heat, engagement) {
  const segments = [1, 2, 3, 4].map((level) => (
    `<span class="heat-segment ${level <= heat.flames ? "active" : ""}"></span>`
  )).join("");
  return `
    <span class="market-heat ${heat.className}" title="${escapeHtml(`${heat.label}. ${engagement}`)}" aria-label="${escapeHtml(heat.label)}">
      <small>Market Heat</small>
      <span class="heat-meter">${segments}</span>
    </span>
  `;
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
  let text = "Price drop";
  if (parts.length) text += `: ${parts.join(" ")}`;
  if (date) text += ` on ${date}`;
  if (!parts.length && !date && count !== null && count > 0) text += `: ${count} change${count === 1 ? "" : "s"} in 1y`;
  return text;
}

function priceReductionLabel(property) {
  const reduction = priceReductionCompact(property);
  return reduction ? `Price Reduction: ${reduction}` : "";
}

function isPositiveFeature(value) {
  const normalized = normalizeText(value);
  return hasDisplayValue(value)
    && normalized !== "no"
    && normalized !== "none"
    && normalized !== "unknown"
    && normalized !== "n/a"
    && normalized !== "does not apply"
    && normalized !== "no basement"
    && normalized !== "no garage";
}

function usefulFeatureValue(value) {
  return isPositiveFeature(value) ? displayValue(value) : "";
}

function chip(label, value) {
  return { label, value };
}

function featureChips(property) {
  const chips = [];
  const garageType = displayValue(property.garage_type);
  const garageTypeText = normalizeText(garageType);
  if (isPositiveFeature(garageType)) {
    if (garageTypeText.includes("attached")) chips.push(chip("Garage", "Attached"));
    else if (garageTypeText.includes("detached")) chips.push(chip("Garage", "Detached"));
    else chips.push(chip("Garage", garageType));
  }

  const basement = basementDisplay(property.basement);
  if (basement === "Yes") chips.push(chip("Basement", "Yes"));

  const fence = usefulFeatureValue(property.fence);
  if (fence) chips.push(chip("Fence", fence));

  if (usefulFeatureValue(property.flooring)) {
    const flooring = String(property.flooring)
      .split(/[,/;]+/)
      .map((item) => item.trim())
      .filter(Boolean)
      .slice(0, 2)
      .join(", ");
    if (flooring) chips.push(chip("Flooring", flooring));
  }

  const construction = usefulFeatureValue(property.construction_materials);
  if (construction) chips.push(chip("Construction", construction));

  const foundation = usefulFeatureValue(property.foundation_details);
  if (foundation) chips.push(chip("Foundation", foundation));

  const roof = usefulFeatureValue(property.roof);
  if (roof) chips.push(chip("Roof", roof));

  return chips;
}

function renderFeatureChip(item) {
  return `
    <span class="feature-chip">
      <small>${escapeHtml(item.label)}</small>
      <strong>${escapeHtml(item.value)}</strong>
    </span>
  `;
}

function sortChipValue(property) {
  const fields = activeSortFields();
  if (!fields.length) return "Sorted by: none";
  return `Sorted by: ${fields.map((field) => {
    const value = field === "garage_fit" ? getGarageFit(property) : property[field];
    return `${columnLabel(field)} = ${displayValue(value)}`;
  }).join(" | ")}`;
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

function csvHeaders(data) {
  const dynamicHeaders = data.flatMap((property) => Object.keys(property));
  return [...new Set([...sheetHeaders, ...dynamicHeaders])];
}

function populateSortOptions(data = []) {
  const headers = csvHeaders(data);
  const sortControls = [elements.sortPrimary, elements.sortSecondary, elements.sortTertiary];

  for (const select of sortControls) {
    select.replaceChildren();
    const noneOption = document.createElement("option");
    noneOption.value = "";
    noneOption.textContent = "No additional sort";
    select.append(noneOption);

    for (const header of headers) {
      const option = document.createElement("option");
      option.value = header;
      option.textContent = columnLabel(header);
      select.append(option);
    }
  }
  elements.sortPrimary.value = "price";
  elements.sortSecondary.value = "price_per_sqft";
  elements.sortTertiary.value = "days_on_redfin";
}

function activeSortFields() {
  return [
    elements.sortPrimary.value,
    elements.sortSecondary.value,
    elements.sortTertiary.value,
  ].filter(Boolean);
}

function getFilteredProperties() {
  const query = normalizeText(elements.search.value);
  const status = elements.status.value;

  return properties
    .filter((property) => {
      const propertyGarageFit = getGarageFit(property);
      const listingStatus = listingStatusDisplay(property.listing_status);
      const searchable = [
        property.address,
        listingStatus,
        property.strategy_category,
        property.final_decision,
        property.garage,
        property.garage_type,
        propertyGarageFit,
        property.basement,
        property.buyer_interest_signal,
      ].map(normalizeText).join(" ");

      const matchesQuery = !query || searchable.includes(query);
      const matchesStatus = (
        status === "all-statuses"
        || (status === "all" && ["For Sale", "Pending"].includes(listingStatus))
        || listingStatus === status
      );

      return matchesQuery && matchesStatus;
    })
    .sort(sortProperties);
}

function sortProperties(a, b) {
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

  for (const column of activeSortFields()) {
    if (column === "strategy_category") {
      const comparison = (strategyRank[a.strategy_category] ?? 99) - (strategyRank[b.strategy_category] ?? 99);
      if (comparison !== 0) return comparison * direction;
      continue;
    }

    const left = sortableValue(a, column);
    const right = sortableValue(b, column);

    if (left.empty && right.empty) continue;
    if (left.empty) return 1;
    if (right.empty) return -1;

    if (left.type === "number" && right.type === "number") {
      const comparison = left.value - right.value;
      if (comparison !== 0) return comparison * direction;
      continue;
    }

    if (left.type === "date" && right.type === "date") {
      const comparison = left.value - right.value;
      if (comparison !== 0) return comparison * direction;
      continue;
    }

    const comparison = String(left.value).localeCompare(String(right.value), undefined, {
      numeric: true,
      sensitivity: "base",
    });
    if (comparison !== 0) return comparison * direction;
  }

  return 0;
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
  const heat = marketHeat(property);
  const priceDrop = priceReductionText(property);
  const priceReduction = priceReductionLabel(property);
  const chips = featureChips(property);
  const listingLink = hasDisplayValue(property.listing_url)
    ? `<a class="open-link" href="${escapeHtml(property.listing_url)}" target="_blank" rel="noopener">Open Listing</a>`
    : `<span class="open-link disabled" aria-disabled="true">Open Listing</span>`;

  card.innerHTML = `
    <div class="card-main-row">
      <div class="title-block">
        <h2 class="address" title="${escapeHtml(property.address || "Unknown address")}">${escapeHtml(compactAddress(property.address))}</h2>
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
      ${renderMarketHeat(heat, buyerEngagement(property))}
      <span class="market-metric">Views: ${displayNumber(property.views)}</span>
      <span class="market-metric">Favorites: ${displayNumber(property.favorites)}</span>
      <span class="market-metric">DOM: ${escapeHtml(compactDomDisplay(property))}</span>
      ${priceReduction ? `<span class="price-drop" title="${escapeHtml(priceDrop)}">${escapeHtml(priceReduction)}</span>` : ""}
    </div>

    ${chips.length ? `
      <div class="features-row">
        ${chips.map(renderFeatureChip).join("")}
      </div>
    ` : ""}

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
  } catch (error) {
    console.error(error);
    populateSortOptions();
    showDashboardError();
  }

  elements.search.addEventListener("input", render);
  elements.status.addEventListener("change", render);
  elements.sortPrimary.addEventListener("change", render);
  elements.sortSecondary.addEventListener("change", render);
  elements.sortTertiary.addEventListener("change", render);
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
