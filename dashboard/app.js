const CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSXqJIzYh_rVeZmiQyf8YweSAtG3aUhi4_MdrAYVn8hTsLJZjvWvBYD46o3BWetRHCGkfPTI65-Hvb8/pub?gid=0&single=true&output=csv";

const sheetHeaders = [
  "address",
  "listing_status",
  "current_status",
  "price",
  "sq_ft",
  "price_per_sqft",
  "beds",
  "baths",
  "year_built",
  "days_on_redfin",
  "current_dom",
  "dom_status",
  "views",
  "favorites",
  "views_per_day",
  "favorites_per_day",
  "interest_velocity",
  "redfin_snapshot_interest_score",
  "live_market_interest_score",
  "live_market_interest_flags",
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
  "listing_photo_url",
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
  "current_price",
  "recent_price_drop",
  "price_drop_pct",
  "back_on_market",
  "pending_speed",
  "last_checked",
];

const detailSections = [
  {
    title: "Market Activity",
    fields: [
      "views",
      "favorites",
      "views_per_day",
      "favorites_per_day",
      "favorite_conversion_rate",
      "interest_velocity",
      "redfin_snapshot_interest_score",
      "buyer_interest_signal",
      "live_market_interest_score",
      "live_market_interest_flags",
      "current_dom",
      "current_price",
      "recent_price_drop",
      "price_drop_pct",
      "back_on_market",
      "pending_speed",
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
  "current_dom",
  "dom_status",
  "views",
  "favorites",
  "interest_velocity",
  "current_status",
  "last_checked",
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
  marketTabs: [...document.querySelectorAll("[data-market-state]")],
  price: document.querySelector("#price-filter"),
  dom: document.querySelector("#dom-filter"),
  priceDrop: document.querySelector("#price-drop-filter"),
  beds: document.querySelector("#beds-filter"),
  baths: document.querySelector("#baths-filter"),
  garage: document.querySelector("#garage-filter"),
  basement: document.querySelector("#basement-filter"),
  fence: document.querySelector("#fence-filter"),
  flooring: document.querySelector("#flooring-filter"),
  flooringSearch: document.querySelector("#flooring-search"),
  construction: document.querySelector("#construction-filter"),
  constructionSearch: document.querySelector("#construction-search"),
  foundation: document.querySelector("#foundation-filter"),
  foundationSearch: document.querySelector("#foundation-search"),
  hvac: document.querySelector("#hvac-filter"),
  hvacSearch: document.querySelector("#hvac-search"),
  roof: document.querySelector("#roof-filter"),
  roofSearch: document.querySelector("#roof-search"),
  water: document.querySelector("#water-filter"),
  waterSearch: document.querySelector("#water-search"),
  appliances: document.querySelector("#appliances-filter"),
  appliancesSearch: document.querySelector("#appliances-search"),
  sortPrimary: document.querySelector("#sort-primary"),
  sortPrimaryDirection: document.querySelector("#sort-primary-direction"),
  sortSecondary: document.querySelector("#sort-secondary"),
  sortSecondaryDirection: document.querySelector("#sort-secondary-direction"),
  sortTertiary: document.querySelector("#sort-tertiary"),
  sortTertiaryDirection: document.querySelector("#sort-tertiary-direction"),
  modal: document.querySelector("#details-modal"),
  modalTitle: document.querySelector("#details-title"),
  modalContent: document.querySelector("#details-content"),
  modalClose: document.querySelector("#details-close"),
};

let activeMarketState = "Active";

const advancedFilterConfigs = [
  { key: "flooring", fields: ["flooring"] },
  { key: "construction", fields: ["construction_materials"] },
  { key: "foundation", fields: ["foundation_details"] },
  { key: "hvac", fields: ["heating", "cooling"] },
  { key: "roof", fields: ["roof"] },
  { key: "water", fields: ["water_source"] },
  { key: "appliances", fields: ["appliances"] },
];

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
  const overrides = {
    days_on_redfin: "Current DOM",
    current_dom: "Current DOM",
    views: "Redfin Snapshot Views",
    favorites: "Redfin Snapshot Favorites",
    views_per_day: "Redfin Snapshot Views/Day",
    favorites_per_day: "Redfin Snapshot Favorites/Day",
    favorite_conversion_rate: "Redfin Snapshot Favorite Rate",
    interest_velocity: "Redfin Snapshot Velocity",
  };
  if (overrides[header]) return overrides[header];
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

function isPlaceholderValue(value) {
  if (value === null || value === undefined) return true;
  if (Array.isArray(value) && !value.length) return true;
  return [
    "",
    "missing",
    "not provided",
    "no info",
    "does not apply",
    "n/a",
    "-",
  ].includes(normalizeText(value).trim());
}

function splitAttributeValues(value) {
  if (isPlaceholderValue(value)) return [];
  return String(value)
    .split(/[,;/|]+/)
    .map((item) => item.trim())
    .filter((item) => !isPlaceholderValue(item));
}

function normalizedAttributeKey(value) {
  return normalizeText(value).replace(/\s+/g, " ").trim();
}

function selectedValues(select) {
  return [...select.selectedOptions].map((option) => option.value);
}

function propertyAttributeValues(property, fields) {
  return fields.flatMap((field) => splitAttributeValues(property[field]));
}

function matchesAdvancedFilter(property, config) {
  const select = elements[config.key];
  const selected = selectedValues(select);
  if (!selected.length) return true;
  const propertyValues = propertyAttributeValues(property, config.fields).map(normalizedAttributeKey);
  return selected.some((value) => propertyValues.includes(value));
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

function marketState(property) {
  const status = listingStatusDisplay(property.current_status || property.listing_status);
  return status === "For Sale" ? "Active" : status;
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
  if (hasDisplayValue(property.current_dom)) return `${property.current_dom} DOM`;
  if (hasDisplayValue(property.days_on_redfin)) return `${property.days_on_redfin} DOM`;
  if (hasDisplayValue(property.dom_status)) return property.dom_status;
  return "—";
}

function compactDomDisplay(property) {
  const days = parseNumber(property.current_dom) ?? parseNumber(property.days_on_redfin);
  if (days !== null) return `${formatNumber(days)}d`;
  if (hasDisplayValue(property.dom_status)) return property.dom_status;
  return "—";
}

function currentPrice(property) {
  return hasDisplayValue(property.current_price) ? property.current_price : property.price;
}

function priceDropAmount(property) {
  if (hasDisplayValue(property.price_reduction_amount)) return property.price_reduction_amount;
  const before = parseNumber(property.price_before_reduction);
  const current = parseNumber(currentPrice(property));
  if (before !== null && current !== null && before > current) return before - current;
  return "";
}

function priceDropDisplay(property) {
  const amount = priceDropAmount(property);
  return hasDisplayValue(amount) ? displayCurrency(amount) : "";
}

function priceCutCount(property) {
  return parseNumber(property.price_change_count_1y) ?? 0;
}

function relistCount(property) {
  return parseNumber(property.listed_count_1y) ?? 0;
}

function hasPriceDrop(property) {
  const explicit = normalizeText(property.recent_price_drop);
  return explicit === "yes" || priceCutCount(property) > 0 || hasDisplayValue(priceDropAmount(property));
}

function pendingDays(property) {
  const match = String(property.pending_speed || "").match(/(\d+)/);
  if (match) return Number(match[1]);
  return parseNumber(property.current_dom) ?? parseNumber(property.days_on_redfin);
}

function backOnMarketDisplay(property) {
  const value = normalizeText(property.back_on_market);
  if (value !== "yes") {
    const relists = relistCount(property);
    return relists > 1 ? `Relisted ${formatNumber(relists)}x` : "";
  }
  const dom = parseNumber(property.current_dom);
  if (dom !== null && dom <= 3) return `Back on Market • ${formatNumber(dom)}d`;
  const relists = relistCount(property);
  return relists > 1 ? `Relisted ${formatNumber(relists)}x` : "Relisted";
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

function firstDelimitedValue(value) {
  if (!hasDisplayValue(value)) return "";
  return String(value)
    .split(/[|,\n]/)
    .map((item) => item.trim())
    .filter(Boolean)[0] || "";
}

function zimgImageUrl(value) {
  const url = firstDelimitedValue(value);
  if (!url) return "";
  if (!/^https?:\/\//i.test(url)) return "";
  if (!url.includes("zimg.paragon.ice.com")) return "";
  try {
    const parsed = new URL(url);
    if (!parsed.hostname.toLowerCase().endsWith("zimg.paragon.ice.com")) return "";
    if (!/\.(jpe?g|png|webp)$/i.test(parsed.pathname)) return "";
  } catch (error) {
    return "";
  }
  return url;
}

function dashboardRelativeImagePath(path) {
  if (!hasDisplayValue(path)) return "";
  const cleanPath = String(path).trim();
  if (/^https?:\/\//i.test(cleanPath) || cleanPath.startsWith("../") || cleanPath.startsWith("./")) {
    return cleanPath;
  }
  if (cleanPath.startsWith("outputs/")) return `../${cleanPath}`;
  return cleanPath;
}

function localIdxImageCandidate(property) {
  const folder = dashboardRelativeImagePath(property.image_folder);
  if (!folder) return "";
  return `${folder.replace(/\/$/, "")}/idx_01.jpg`;
}

function listingPhoto(property) {
  return zimgImageUrl(property.listing_photo_url)
    || zimgImageUrl(property.idx_image_urls)
    || localIdxImageCandidate(property)
    || "";
}

function renderListingPhoto(property) {
  const url = listingPhoto(property);
  if (!hasDisplayValue(url)) return "";
  return `
    <div class="listing-photo">
      <img src="${escapeHtml(url)}" alt="${escapeHtml(property.address || "Property photo")}" loading="lazy" onerror="this.closest('.listing-photo').remove()">
    </div>
  `;
}

function evidenceChip(label, value, className = "") {
  if (!hasDisplayValue(value)) return "";
  return `<span class="market-metric ${className}"><small>${escapeHtml(label)}</small><strong>${escapeHtml(value)}</strong></span>`;
}

function buyerInterestLevel(property) {
  const score = parseNumber(property.live_market_interest_score)
    ?? parseNumber(property.redfin_snapshot_interest_score)
    ?? parseNumber(property.urgency_score);
  if (score === null) return 1;
  return Math.max(1, Math.min(5, Math.round(score)));
}

function renderBuyerInterestScale(property) {
  const level = buyerInterestLevel(property);
  const segments = [1, 2, 3, 4, 5].map((step) => (
    `<span class="interest-segment ${step <= level ? "active" : ""}"></span>`
  )).join("");
  return `
    <span class="buyer-interest-scale interest-${level}" title="Buyer interest ${level}/5">
      <small>Buyer Interest</small>
      <span class="interest-meter">${segments}</span>
    </span>
  `;
}

function domSignalClass(property) {
  const dom = parseNumber(property.current_dom) ?? parseNumber(property.days_on_redfin);
  if (dom === null) return "signal-neutral";
  if (dom <= 7) return "signal-active";
  if (dom > 21) return "signal-warning";
  return "signal-neutral";
}

function cutsSignalClass(property) {
  const cuts = priceCutCount(property);
  if (cuts >= 2) return "signal-danger";
  if (cuts === 1) return "signal-warning";
  return "signal-neutral";
}

function activeMarketStrip(property) {
  const chips = [
    evidenceChip("Current DOM", compactDomDisplay(property), domSignalClass(property)),
    renderBuyerInterestScale(property),
  ];
  const drop = priceDropDisplay(property);
  chips.push(evidenceChip("Cuts", `${formatNumber(priceCutCount(property))}`, cutsSignalClass(property)));
  if (drop) chips.push(evidenceChip("Price Drop", drop, "price-drop signal-danger"));
  const relisted = backOnMarketDisplay(property);
  if (relisted) chips.push(evidenceChip("Relisted", relisted, "back-market signal-warning"));
  return chips.join("");
}

function pendingMarketStrip(property) {
  const days = pendingDays(property);
  const pendingText = days !== null ? `Pending in ${formatNumber(days)}d` : displayValue(property.pending_speed);
  const chips = [evidenceChip("Pending", pendingText), renderBuyerInterestScale(property)];
  chips.push(evidenceChip("Cuts Before Pending", `${formatNumber(priceCutCount(property))}`));
  chips.push(evidenceChip("Price", displayCurrency(currentPrice(property))));
  return chips.join("");
}

function soldMarketStrip(property) {
  const days = pendingDays(property);
  const daysText = days !== null ? `${formatNumber(days)}d` : "—";
  return [
    evidenceChip("Sold", "Sold"),
    renderBuyerInterestScale(property),
    evidenceChip("Days to Pending/Sold", daysText),
    evidenceChip("Cuts Before Sale", `${formatNumber(priceCutCount(property))}`),
  ].join("");
}

function marketEvidenceStrip(property) {
  const state = marketState(property);
  if (state === "Pending") return pendingMarketStrip(property);
  if (state === "Sold") return soldMarketStrip(property);
  return activeMarketStrip(property);
}

function sortChipValue(property) {
  const sorts = activeSortFields();
  if (!sorts.length) return "<span><small>Filter:</small><strong>None</strong></span>";
  return sorts.map(({ field, direction }, index) => {
    const directionLabel = direction === "desc" ? "↓" : "↑";
    const value = field === "garage_fit" ? getGarageFit(property) : property[field];
    return `<span><small>Filter ${index + 1}: ${escapeHtml(columnLabel(field))}:</small><strong>${escapeHtml(displayValue(value))}</strong><b>${directionLabel}</b></span>`;
  }).join("");
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
  elements.sortTertiary.value = "current_dom";
}

function collectAdvancedOptions(data, fields) {
  const options = new Map();
  data.forEach((property) => {
    propertyAttributeValues(property, fields).forEach((value) => {
      const key = normalizedAttributeKey(value);
      if (!key || options.has(key)) return;
      options.set(key, value);
    });
  });
  return [...options.entries()]
    .sort((left, right) => left[1].localeCompare(right[1], undefined, {
      numeric: true,
      sensitivity: "base",
    }))
    .map(([value, label]) => ({ value, label }));
}

function filterAdvancedOptions(config) {
  const select = elements[config.key];
  const search = elements[`${config.key}Search`];
  const query = normalizeText(search.value).trim();
  [...select.options].forEach((option) => {
    option.hidden = Boolean(query) && !normalizeText(option.textContent).includes(query);
  });
}

function populateAdvancedFilters(data = []) {
  advancedFilterConfigs.forEach((config) => {
    const select = elements[config.key];
    const search = elements[`${config.key}Search`];
    const wrapper = document.querySelector(`[data-advanced-filter="${config.key}"]`);
    const options = collectAdvancedOptions(data, config.fields);

    select.replaceChildren();
    search.value = "";
    options.forEach(({ value, label }) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      select.append(option);
    });

    wrapper.hidden = options.length === 0;
    search.hidden = options.length <= 10;
    select.size = Math.min(Math.max(options.length, 2), 6);
    filterAdvancedOptions(config);
  });
}

function activeSortFields() {
  return [
    { field: elements.sortPrimary.value, direction: elements.sortPrimaryDirection.value },
    { field: elements.sortSecondary.value, direction: elements.sortSecondaryDirection.value },
    { field: elements.sortTertiary.value, direction: elements.sortTertiaryDirection.value },
  ].filter((sort) => sort.field);
}

function getFilteredProperties() {
  const query = normalizeText(elements.search.value);
  const priceFilter = elements.price.value;
  const domFilter = elements.dom.value;
  const priceDropFilter = elements.priceDrop.value;

  return properties
    .filter((property) => {
      const propertyGarageFit = getGarageFit(property);
      const listingStatus = marketState(property);
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
      const matchesStatus = listingStatus === activeMarketState;

      const price = parseNumber(currentPrice(property));
      const matchesPrice = priceFilter === "all"
        || (priceFilter === "under-150" && price !== null && price < 150000)
        || (priceFilter === "150-200" && price !== null && price >= 150000 && price < 200000)
        || (priceFilter === "200-250" && price !== null && price >= 200000 && price < 250000)
        || (priceFilter === "250-plus" && price !== null && price >= 250000);

      const dom = parseNumber(property.current_dom) ?? parseNumber(property.days_on_redfin);
      const matchesDom = domFilter === "all"
        || (domFilter === "0-7" && dom !== null && dom <= 7)
        || (domFilter === "8-21" && dom !== null && dom >= 8 && dom <= 21)
        || (domFilter === "22-60" && dom !== null && dom >= 22 && dom <= 60)
        || (domFilter === "60-plus" && dom !== null && dom > 60);

      const drop = hasPriceDrop(property);
      const matchesDrop = priceDropFilter === "all"
        || (priceDropFilter === "yes" && drop)
        || (priceDropFilter === "no" && !drop);

      const matchesBeds = elements.beds.value === "all" || (parseNumber(property.beds) ?? 0) >= Number(elements.beds.value);
      const matchesBaths = elements.baths.value === "all" || (parseNumber(property.baths) ?? 0) >= Number(elements.baths.value);
      const matchesGarage = elements.garage.value === "all" || property.garage === elements.garage.value;
      const matchesBasement = elements.basement.value === "all"
        || (elements.basement.value === "yes" && basementDisplay(property.basement) === "Yes")
        || (elements.basement.value === "no" && basementDisplay(property.basement) === "No");
      const fenceValue = normalizeText(property.fence);
      const matchesFence = elements.fence.value === "all"
        || (elements.fence.value === "yes" && isPositiveFeature(property.fence))
        || (elements.fence.value === "no" && (fenceValue.includes("no") || !hasDisplayValue(property.fence)));
      const matchesAdvanced = advancedFilterConfigs.every((config) => matchesAdvancedFilter(property, config));

      return matchesQuery
        && matchesStatus
        && matchesPrice
        && matchesDom
        && matchesDrop
        && matchesBeds
        && matchesBaths
        && matchesGarage
        && matchesBasement
        && matchesFence
        && matchesAdvanced;
    })
    .sort(sortProperties);
}

function sortProperties(a, b) {
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

  for (const { field: column, direction: sortDirection } of activeSortFields()) {
    const direction = sortDirection === "desc" ? -1 : 1;
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

  const listingStatus = marketState(property);
  const chips = featureChips(property);
  const listingLink = hasDisplayValue(property.listing_url)
    ? `<a class="open-link" href="${escapeHtml(property.listing_url)}" target="_blank" rel="noopener">Open Listing</a>`
    : `<span class="open-link disabled" aria-disabled="true">Open Listing</span>`;

  card.innerHTML = `
    <div class="card-grid">
      <div class="card-left">
        ${renderListingPhoto(property)}
        <div class="card-identity">
          <div class="title-block">
            <h2 class="address" title="${escapeHtml(property.address || "Unknown address")}">${escapeHtml(compactAddress(property.address))}</h2>
            <span class="status-pill ${statusClass(listingStatus)}">${escapeHtml(listingStatus)}</span>
          </div>
          <div class="primary-metrics">
            <span><strong>${displayCurrency(currentPrice(property))}</strong><small>Price</small></span>
            <span><strong>${displayPricePerSqft(property.price_per_sqft)}</strong><small>Price/Sq Ft</small></span>
            <span><strong>${escapeHtml(bedroomsBathsDisplay(property))}</strong><small>Beds / Baths</small></span>
            <span><strong>${displayNumber(property.sq_ft)}</strong><small>Sq Ft</small></span>
            <span><strong>${escapeHtml(lotDisplay(property))}</strong><small>Lot</small></span>
          </div>
        </div>
      </div>

      <div class="market-row">
        ${marketEvidenceStrip(property)}
      </div>

      ${chips.length ? `
        <div class="features-row">
          ${chips.map(renderFeatureChip).join("")}
        </div>
      ` : "<div class=\"features-row empty-features\"></div>"}
    </div>

    <div class="card-footer">
      <div class="sort-chip">${sortChipValue(property)}</div>
      <span class="last-checked">Last checked: ${escapeHtml(displayValue(property.last_checked))}</span>
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
    populateAdvancedFilters(properties);
  } catch (error) {
    console.error(error);
    populateSortOptions();
    populateAdvancedFilters();
    showDashboardError();
  }

  elements.search.addEventListener("input", render);
  elements.price.addEventListener("change", render);
  elements.dom.addEventListener("change", render);
  elements.priceDrop.addEventListener("change", render);
  elements.beds.addEventListener("change", render);
  elements.baths.addEventListener("change", render);
  elements.garage.addEventListener("change", render);
  elements.basement.addEventListener("change", render);
  elements.fence.addEventListener("change", render);
  advancedFilterConfigs.forEach((config) => {
    elements[config.key].addEventListener("change", render);
    elements[`${config.key}Search`].addEventListener("input", () => {
      filterAdvancedOptions(config);
    });
  });
  elements.marketTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      activeMarketState = tab.dataset.marketState;
      elements.marketTabs.forEach((button) => {
        button.classList.toggle("active", button === tab);
      });
      render();
    });
  });
  elements.sortPrimary.addEventListener("change", render);
  elements.sortPrimaryDirection.addEventListener("change", render);
  elements.sortSecondary.addEventListener("change", render);
  elements.sortSecondaryDirection.addEventListener("change", render);
  elements.sortTertiary.addEventListener("change", render);
  elements.sortTertiaryDirection.addEventListener("change", render);
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
