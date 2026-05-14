import json
import re
from datetime import date, datetime, timedelta

try:
    from normalize_property import MISSING, has_value, normalize_property
except ModuleNotFoundError:
    from app.normalize_property import MISSING, has_value, normalize_property

INPUT_FILE = "outputs/raw_text.txt"
METADATA_INPUT_FILE = "outputs/extraction_metadata.json"
OUTPUT_FILE = "outputs/scored_property.json"

def extract_field(pattern, text, default=None):
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else default

def extract_int_field(patterns, text):
    for pattern in patterns:
        value = extract_field(pattern, text)
        if value:
            return int(value.replace(",", ""))
    return None

def clean_number(value):
    if value in (None, "", MISSING):
        return None
    match = re.search(r"\d+(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?", str(value))
    if not match:
        return None
    parsed = float(match.group(0).replace(",", ""))
    return int(parsed) if parsed.is_integer() else parsed

def extract_pdf_living_sqft(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    lot_context = re.compile(r"\b(lot|acres?|land|parcel)\b", re.IGNORECASE)
    sqft_pattern = re.compile(r"(\d{1,3}(?:,\d{3})+|\d{3,4})\s+sq\s*ft\b", re.IGNORECASE)

    for index, line in enumerate(lines):
        if lot_context.search(line):
            continue

        match = sqft_pattern.search(line)
        if not match:
            continue

        previous_line = lines[index - 1] if index > 0 else ""
        if lot_context.search(previous_line):
            continue

        return match.group(1)

    return None

def extract_pdf_full_baths(text):
    for line in text.splitlines():
        stripped = line.strip()
        if re.search(r"\d+\.\d+\s*(?:ba|bath|baths)\b", stripped, re.IGNORECASE):
            continue

        match = re.search(r"\b(\d+)\s*(?:ba|bath|baths)\b", stripped, re.IGNORECASE)
        if match:
            return match.group(1)

    return None

def detect_listing_status(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    current_status_text = "\n".join(lines[:160])
    badge_statuses = {
        "SOLD": "Sold",
        "PENDING": "Pending",
        "UNDER CONTRACT": "Pending",
        "CONTINGENT": "Pending",
        "FOR SALE": "For Sale",
        "ACTIVE": "For Sale",
    }
    price_pattern = re.compile(r"^\$?\d{1,3}(?:,\d{3})+(?:\.\d{2})?$")

    # Redfin PDFs place the current status badge immediately above the large
    # listing price on the first page. Prefer that local header pattern so
    # historical sale events do not make active/pending listings look sold.
    for index, line in enumerate(lines[:100]):
        if not price_pattern.match(line):
            continue

        nearby_status_lines = lines[max(0, index - 3) : index]
        for status_line in reversed(nearby_status_lines):
            status = badge_statuses.get(status_line.upper())
            if status:
                return status

    status_label_pattern = re.compile(r"^(?:MLS Status|Mls Status|Listing Status|Status)\s*:?\s*(.*)$", re.IGNORECASE)
    for index, line in enumerate(lines[:160]):
        label_match = status_label_pattern.match(line)
        if not label_match:
            continue

        label_value = label_match.group(1).strip()
        if not label_value and index + 1 < len(lines):
            label_value = lines[index + 1]

        if re.search(r"\b(?:Sold|Closed)\b", label_value, re.IGNORECASE):
            return "Sold"
        if re.search(r"\b(?:Pending|Under Contract|Contingent)\b", label_value, re.IGNORECASE):
            return "Pending"
        if re.search(r"\b(?:For Sale|Active)\b", label_value, re.IGNORECASE):
            return "For Sale"

    for index, line in enumerate(lines[:80]):
        status = badge_statuses.get(line.upper())
        if not status:
            continue

        nearby_lines = lines[index + 1 : index + 6]
        if any(price_pattern.match(nearby_line) for nearby_line in nearby_lines):
            return status

    if re.search(r"\bThis home is pending\b", current_status_text, re.IGNORECASE):
        return "Pending"
    if re.search(r"\bThis home (?:has )?sold\b", current_status_text, re.IGNORECASE):
        return "Sold"

    return "For Sale"

def recalculate_price_per_sqft(data):
    price = clean_number(data.get("price"))
    sqft = clean_number(data.get("sq_ft"))

    if price and sqft:
        data["price_per_sqft"] = round(price / sqft, 2)
    else:
        data["price_per_sqft"] = MISSING

    return data

def calculate_rate_per_day(count, days_on_redfin):
    if count == MISSING or days_on_redfin == MISSING:
        return MISSING
    if count is None or days_on_redfin is None:
        return MISSING

    days = int(days_on_redfin)
    if days < 1:
        days = 1

    return round(int(count) / days, 2)

def classify_dom_status(days_on_redfin):
    # MISSING DOM is operationally treated as Just Listed because Redfin PDFs for very new listings often omit DOM.
    if days_on_redfin == MISSING or days_on_redfin is None:
        return "Just Listed"

    days = int(days_on_redfin)
    if days <= 7:
        return "Just Listed"
    if days <= 29:
        return "Recent"
    if days <= 59:
        return "Aging"
    return "Stale"

def calculate_favorite_conversion_rate(favorites, views):
    if favorites == MISSING or views == MISSING:
        return MISSING
    if favorites is None or views is None:
        return MISSING

    views = int(views)
    if views == 0:
        return MISSING

    return round(int(favorites) / views, 2)

def classify_interest_velocity(views_per_day):
    if views_per_day == MISSING or views_per_day is None:
        return MISSING

    if views_per_day >= 25:
        return "High"
    if views_per_day >= 10:
        return "Moderate"
    return "Low"

def classify_buyer_interest_signal(data):
    if (
        data.get("views_per_day") == MISSING
        or data.get("favorites_per_day") == MISSING
        or data.get("favorite_conversion_rate") == MISSING
    ):
        return "Buyer interest unclear"

    views_per_day = data["views_per_day"]
    favorites_per_day = data["favorites_per_day"]
    conversion = data["favorite_conversion_rate"]
    days_on_redfin = int(data["days_on_redfin"]) if has_value(data, "days_on_redfin") else None

    if views_per_day >= 25 and conversion < 0.05:
        return "High browsing, weak buyer commitment"
    if favorites_per_day >= 1:
        return "Strong buyer interest"
    if views_per_day < 10 and days_on_redfin is not None and days_on_redfin >= 30:
        return "Low buyer attention"
    if 10 <= views_per_day < 25 and 0.05 <= conversion <= 0.15:
        return "Normal market interest"
    return "Buyer interest unclear"

def missing_market_interest_notes(data):
    notes = []
    if data.get("days_on_redfin") == MISSING:
        if data.get("views_per_day") == MISSING:
            notes.append("views_per_day unavailable because days_on_redfin is MISSING")
        if data.get("favorites_per_day") == MISSING:
            notes.append("favorites_per_day unavailable because days_on_redfin is MISSING")
    return notes

def numeric_or_none(value):
    return clean_number(value)

def int_or_default(value, default=0):
    number = clean_number(value)
    if number is None:
        return default
    return int(number)

def current_status_value(data):
    return data.get("current_status") or data.get("listing_status") or "For Sale"

def current_dom_value(data):
    if has_value(data, "current_dom"):
        return int(clean_number(data.get("current_dom")))
    if has_value(data, "days_on_redfin"):
        return int(clean_number(data.get("days_on_redfin")))
    return None

def current_price_value(data):
    return numeric_or_none(data.get("current_price")) or numeric_or_none(data.get("price"))

def recent_price_drop_value(data):
    amount = numeric_or_none(data.get("price_reduction_amount"))
    price_change_count = numeric_or_none(data.get("price_change_count_1y"))
    return bool((amount is not None and amount > 0) or (price_change_count is not None and price_change_count >= 1))

def price_drop_pct_value(data):
    existing = numeric_or_none(data.get("price_drop_pct"))
    if existing is not None:
        return existing

    existing = numeric_or_none(data.get("price_reduction_pct"))
    if existing is not None:
        return existing

    price_before = numeric_or_none(data.get("price_before_reduction"))
    current_price = current_price_value(data)
    if price_before and current_price and price_before > current_price:
        return round((price_before - current_price) / price_before, 4)
    return MISSING

def back_on_market_value(data):
    listed_count = numeric_or_none(data.get("listed_count_1y"))
    removed_count = numeric_or_none(data.get("listing_removed_count_1y"))
    if listed_count is None or removed_count is None:
        return MISSING
    return "Yes" if listed_count > 1 and removed_count >= 1 else "No"

def pending_speed_value(data):
    status = current_status_value(data)
    dom = current_dom_value(data)
    if status != "Pending" or dom is None:
        return MISSING
    if dom <= 7:
        return "Pending within 7 days"
    if dom <= 21:
        return "Pending within 21 days"
    return "Pending after 21 days"

def update_live_market_fields(data):
    data["current_status"] = current_status_value(data)
    data["current_dom"] = current_dom_value(data) if current_dom_value(data) is not None else MISSING
    current_price = current_price_value(data)
    data["current_price"] = current_price if current_price is not None else MISSING
    data["recent_price_drop"] = "Yes" if recent_price_drop_value(data) else "No"
    data["price_drop_pct"] = price_drop_pct_value(data)
    data["back_on_market"] = back_on_market_value(data)
    data["pending_speed"] = pending_speed_value(data)
    return data

def update_redfin_snapshot_interest(data):
    score = 1

    if has_value(data, "views_per_day"):
        views_per_day = float(data["views_per_day"])
        if views_per_day >= 25:
            score += 2
        elif views_per_day >= 10:
            score += 1

    if has_value(data, "favorites_per_day") and float(data["favorites_per_day"]) >= 1:
        score += 1

    if has_value(data, "favorite_conversion_rate"):
        conversion = float(data["favorite_conversion_rate"])
        if 0.05 <= conversion <= 0.2:
            score += 1

    data["redfin_snapshot_interest_score"] = min(score, 5)
    return data

def update_live_market_interest(data):
    update_live_market_fields(data)
    status = current_status_value(data)
    dom = current_dom_value(data)
    recent_price_drop = recent_price_drop_value(data)
    price_changes = numeric_or_none(data.get("price_change_count_1y")) or 0
    removed_count = numeric_or_none(data.get("listing_removed_count_1y")) or 0
    listed_count = numeric_or_none(data.get("listed_count_1y")) or 0
    back_on_market = data.get("back_on_market") == "Yes"

    score = 2
    flags = []

    if status == "Sold":
        score = 5
        flags.append("Sold status reflects completed market action")
    elif status == "Pending":
        if dom is not None and dom <= 7:
            score = 5
            flags.append("Pending within 7 days")
        elif dom is not None and dom <= 21:
            score = 4
            flags.append("Pending within 21 days")
        else:
            score = 3
            flags.append("Pending status")
    else:
        if dom is None:
            flags.append("Current DOM unavailable")
        elif dom <= 7 and not recent_price_drop:
            score = 4
            flags.append("Active with 0-7 current DOM and no price drop")
        elif dom <= 7:
            score = 3
            flags.append("Active with 0-7 current DOM")
        elif dom <= 21:
            score = 3
            flags.append("Active with 8-21 current DOM")
        else:
            score = 1
            flags.append("Active with current DOM over 21")

    if recent_price_drop:
        score -= 1
        flags.append("Recent price drop")
    if price_changes >= 2:
        score -= 1
        flags.append("Multiple price changes in last 365 days")
    if removed_count >= 1 or listed_count > 1:
        score -= 1
        flags.append("Recent relisting/removal activity")
    if back_on_market:
        flags.append("Back on market signal")

    data["live_market_interest_score"] = max(1, min(score, 5))
    data["live_market_interest_flags"] = flags
    return data

def parse_redfin_history_date(value):
    try:
        return datetime.strptime(value.strip(), "%b %d, %Y").date()
    except ValueError:
        return None

def extract_listing_history_1y(text, today=None):
    today = today or date.today()
    cutoff = today - timedelta(days=365)
    counts = {
        "listed_count_1y": 0,
        "listing_removed_count_1y": 0,
        "price_change_count_1y": 0,
    }
    event_to_field = {
        "Listed": "listed_count_1y",
        "Listing Removed": "listing_removed_count_1y",
        "Price Changed": "price_change_count_1y",
    }
    current_date = None
    saw_target_event = False
    undated_target_event = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        parsed_date = parse_redfin_history_date(line)
        if parsed_date:
            current_date = parsed_date
            continue

        if line not in event_to_field:
            continue

        saw_target_event = True
        if current_date is None:
            undated_target_event = True
            continue

        if cutoff <= current_date <= today:
            counts[event_to_field[line]] += 1

    if saw_target_event and undated_target_event:
        return {
            "listed_count_1y": MISSING,
            "listing_removed_count_1y": MISSING,
            "price_change_count_1y": MISSING,
        }

    return counts

def load_extraction_metadata():
    try:
        with open(METADATA_INPUT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def detect_garage(text):
    explicit_no_patterns = [
        r"\bno\s+(?:garage|garages)\b",
        r"\bwithout\s+(?:a\s+)?garage\b",
        r"\bgarage\s*(?:[:\-]\s*)?no\b",
    ]

    explicit_yes_patterns = [
        r"\b(?:attached|detached|heated|oversized)\s+garage\b",
        r"\b(?:single|double|triple|two[\s-]stall|three[\s-]stall)\s+garage\b",
        r"\b[1-9]\s*(?:car|stall)\s+garage\b",
        r"\bgarage\s+(?:spaces?|parking|door|stall|included|present)\b",
    ]

    for pattern in explicit_no_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return "No"

    for pattern in explicit_yes_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return "Yes"

    return None

def get_missing_fields(data, fields):
    return [field for field in fields if not has_value(data, field)]

def score_data_completeness(data, core_fields, secondary_fields):
    total_weight = len(core_fields) * 2 + len(secondary_fields)
    missing_weight = len(get_missing_fields(data, core_fields)) * 2
    missing_weight += len(get_missing_fields(data, secondary_fields))
    return round(((total_weight - missing_weight) / total_weight) * 100)

def score_extraction_confidence(data, core_fields, secondary_fields):
    score = 100
    score -= len(get_missing_fields(data, core_fields)) * 15
    score -= len(get_missing_fields(data, secondary_fields)) * 5
    return max(score, 0)

def extraction_quality_fields():
    core_fields = [
        "address",
        "price",
        "sq_ft",
        "price_per_sqft",
        "year_built",
        "days_on_redfin",
        "garage",
    ]
    secondary_fields = [
        "beds",
        "baths",
        "garage_type",
        "basement",
        "flooring",
        "fence",
        "construction_materials",
        "foundation_details",
        "roof",
        "sewer",
        "water_source",
        "appliances",
        "cooling",
        "heating",
        "interior_features",
        "rooms",
    ]
    return core_fields, secondary_fields

def update_extraction_quality(data):
    core_fields, secondary_fields = extraction_quality_fields()
    missing_core_fields = get_missing_fields(data, core_fields)
    missing_secondary_fields = get_missing_fields(data, secondary_fields)

    data["missing_fields"] = missing_core_fields + missing_secondary_fields
    data["data_completeness_score"] = score_data_completeness(data, core_fields, secondary_fields)
    data["extraction_confidence_score"] = score_extraction_confidence(data, core_fields, secondary_fields)

    return data

def classify_age_risk(data):
    if not has_value(data, "year_built"):
        return "Unknown"

    year_built = int(data["year_built"])
    if year_built < 1940:
        return "Higher age risk"
    if year_built < 1980:
        return "Moderate age risk"
    return "Lower age risk"

def classify_garage_requirement(data):
    if data["garage"] == "Yes":
        return "Meets requirement"
    if data["garage"] == "No":
        return "Fails requirement"
    return "Unknown"

def classify_garage_fit(data):
    if data.get("garage") == "Yes":
        return "Garage Present"
    if data.get("garage") == "No":
        return "No Garage"
    return "Garage Unknown"

def classify_price_per_sqft(data):
    if not has_value(data, "price_per_sqft"):
        return "Price per sq ft missing"
    if data["price_per_sqft"] < 140:
        return "Lower price per sq ft"
    if data["price_per_sqft"] > 180:
        return "Higher price per sq ft"
    return "Mid price per sq ft"

def update_property_risk(data):
    data["age_risk"] = classify_age_risk(data)
    data["garage_fit"] = classify_garage_fit(data)
    data["garage_requirement"] = classify_garage_requirement(data)
    data["price_per_sqft_signal"] = classify_price_per_sqft(data)

    property_risk_score = 0
    property_risk_flags = []

    if data["age_risk"] == "Higher age risk":
        property_risk_score += 2
        property_risk_flags.append("Built before 1940")
    elif data["age_risk"] == "Moderate age risk":
        property_risk_score += 1
        property_risk_flags.append("Built before 1980")
    elif data["age_risk"] == "Unknown":
        property_risk_score += 1
        property_risk_flags.append("Year built missing")

    if data["garage_requirement"] == "Fails requirement":
        property_risk_score += 3
        property_risk_flags.append("Does not meet garage requirement")
    elif data.get("garage") == MISSING:
        property_risk_score += 2
        property_risk_flags.append("Garage status missing")

    if data["data_completeness_score"] < 50:
        property_risk_score += 2
        property_risk_flags.append("Low data completeness")
    elif data["data_completeness_score"] < 80:
        property_risk_score += 1
        property_risk_flags.append("Partial data completeness")

    if data["price_per_sqft_signal"] == "Higher price per sq ft":
        property_risk_score += 1
        property_risk_flags.append("Higher price per sq ft")

    data["property_risk_score"] = property_risk_score
    data["property_risk_flags"] = property_risk_flags

    return data

def update_market_activity(data):
    update_redfin_snapshot_interest(data)
    update_live_market_interest(data)

    market_activity_score = data.get("live_market_interest_score", 1)
    market_activity_flags = []

    market_activity_flags.extend(data.get("live_market_interest_flags", []))
    if data.get("redfin_snapshot_interest_score", 1) >= 4:
        market_activity_flags.append("Strong Redfin snapshot interest")
    else:
        market_activity_flags.append("Redfin traffic is snapshot-only context")

    if data["price_per_sqft_signal"] == "Lower price per sq ft":
        market_activity_score += 1
        market_activity_flags.append("Lower price per sq ft")
    elif data["price_per_sqft_signal"] == "Higher price per sq ft":
        market_activity_flags.append("Higher price per sq ft")
    elif data["price_per_sqft_signal"] == "Price per sq ft missing":
        market_activity_flags.append("Price per sq ft missing")

    if data.get("buyer_leverage_score", 0) >= 4:
        market_activity_score += 1
        market_activity_flags.append("Multiple buyer leverage signals")

    data["market_activity_score"] = min(market_activity_score, 5)
    data["market_activity_flags"] = market_activity_flags
    data["urgency_score"] = data["market_activity_score"]

    return data

def update_final_decision(data):
    core_fields, _secondary_fields = extraction_quality_fields()
    missing_core_fields = get_missing_fields(data, core_fields)

    if data["data_completeness_score"] < 40 or len(missing_core_fields) >= 4:
        final_decision = "Data Insufficient"
    elif data["garage_requirement"] == "Unknown" or data["data_completeness_score"] < 70:
        final_decision = "Manual Verification Required"
    elif data["age_risk"] == "Higher age risk" and data["data_completeness_score"] < 85:
        final_decision = "Manual Verification Required"
    elif data.get("property_risk_score", 0) >= 5 and data["garage_requirement"] != "Fails requirement":
        final_decision = "Pass"
    elif (
        data.get("buyer_leverage_score", 0) >= 4
        and has_value(data, "price_per_sqft")
        and data["price_per_sqft"] <= 180
        and data["garage_requirement"] == "Meets requirement"
    ):
        final_decision = "Consider"
    elif (
        data.get("live_market_interest_score", 0) >= 4
        and has_value(data, "price_per_sqft")
        and data["price_per_sqft"] <= 180
        and data["garage_requirement"] == "Meets requirement"
    ):
        final_decision = "Consider"
    else:
        final_decision = "Watch"

    data["final_decision"] = final_decision

    return data

def update_buyer_leverage(data):
    update_live_market_fields(data)

    buyer_leverage_score = 1
    buyer_leverage_flags = []
    status = current_status_value(data)
    dom = current_dom_value(data)
    price_change_count = int_or_default(data.get("price_change_count_1y"))
    listing_removed_count = int_or_default(data.get("listing_removed_count_1y"))
    listed_count = int_or_default(data.get("listed_count_1y"))

    if status == "For Sale":
        if dom is not None and dom >= 60:
            buyer_leverage_score += 2
            buyer_leverage_flags.append("Active with 60+ current DOM")
        elif dom is not None and dom >= 30:
            buyer_leverage_score += 1.5
            buyer_leverage_flags.append("Active with 30-59 current DOM")
        elif dom is not None and dom >= 22:
            buyer_leverage_score += 1
            buyer_leverage_flags.append("Active with current DOM over 21")
    elif status in {"Pending", "Sold"}:
        buyer_leverage_flags.append(f"{status} status reduces current buyer leverage")

    if recent_price_drop_value(data):
        buyer_leverage_score += 1
        buyer_leverage_flags.append("Recent price drop")

    if price_change_count >= 2:
        buyer_leverage_score += 1
        buyer_leverage_flags.append("Multiple price changes in last 365 days")
    elif price_change_count == 1:
        buyer_leverage_score += 0.5
        buyer_leverage_flags.append("One price change in last 365 days")

    if listing_removed_count >= 1:
        buyer_leverage_score += 1
        buyer_leverage_flags.append("Listing removed in last 365 days")

    if listed_count > 1:
        buyer_leverage_score += 1
        buyer_leverage_flags.append("Multiple listings in last 365 days")

    if data.get("back_on_market") == "Yes":
        buyer_leverage_score += 1
        buyer_leverage_flags.append("Back on market")

    data["buyer_leverage_score"] = min(buyer_leverage_score, 5)
    data["buyer_leverage_flags"] = buyer_leverage_flags
    return data

def no_garage_leverage_signals(data, stale_or_aging, buyer_signal):
    return [
        data.get("buyer_leverage_score", 0) >= 3,
        stale_or_aging,
        has_value(data, "listed_count_1y") and data["listed_count_1y"] > 1,
        has_value(data, "listing_removed_count_1y") and data["listing_removed_count_1y"] >= 1,
        has_value(data, "price_change_count_1y") and data["price_change_count_1y"] >= 1,
        has_value(data, "price_reduction_amount") and data["price_reduction_amount"] > 0,
        data.get("price_per_sqft_signal") == "Lower price per sq ft",
        "low buyer attention" in buyer_signal,
    ]

def classify_strategy_category(data):
    core_fields, _secondary_fields = extraction_quality_fields()
    missing_core_fields = get_missing_fields(data, core_fields)
    garage_fit = classify_garage_fit(data)
    final_decision_manual = data.get("final_decision") in {
        "Manual Verification Required",
        "Data Insufficient",
    }
    if garage_fit == "Garage Unknown" and data.get("final_decision") == "Manual Verification Required":
        final_decision_manual = False

    manual_review = (
        final_decision_manual
        or len(missing_core_fields) >= 3
        or data.get("extraction_confidence_score", 100) < 60
    )

    dom = int(data["days_on_redfin"]) if has_value(data, "days_on_redfin") else None
    dom_status = data.get("dom_status")
    recent_dom = dom is not None and dom <= 29
    stale_or_aging = dom is not None and dom >= 30
    price_per_sqft = data.get("price_per_sqft") if has_value(data, "price_per_sqft") else None
    price_not_extreme = price_per_sqft is not None and 100 <= price_per_sqft <= 220
    manageable_risk = data.get("property_risk_score", 0) <= 3
    buyer_signal = str(data.get("buyer_interest_signal", "")).lower()
    live_interest = data.get("live_market_interest_score", 1)
    normal_or_strong_interest = (
        live_interest >= 3
        or "strong buyer interest" in buyer_signal
        or "normal market interest" in buyer_signal
    )
    high_risk = data.get("property_risk_score", 0) >= 5
    high_price = data.get("price_per_sqft_signal") == "Higher price per sq ft"
    final_pass_beyond_garage = (
        data.get("final_decision") == "Pass"
        and data.get("garage_requirement") != "Fails requirement"
    )

    data["garage_fit"] = garage_fit

    if garage_fit == "Garage Unknown":
        if not manual_review and manageable_risk and not high_price:
            return "Watch"
        return "Manual Review"

    if garage_fit == "No Garage":
        if high_risk or high_price or final_pass_beyond_garage:
            return "Pass - No Garage"

        if manual_review:
            return "Manual Review"

        if sum(bool(signal) for signal in no_garage_leverage_signals(data, stale_or_aging, buyer_signal)) >= 1:
            return "Leverage Opportunity - No Garage"

        return "Watch - No Garage"

    if data.get("final_decision") == "Pass":
        return "Pass"

    if manual_review:
        return "Manual Review"

    leverage_signals = [
        stale_or_aging,
        dom_status == "Stale",
        has_value(data, "listing_removed_count_1y") and data["listing_removed_count_1y"] >= 1,
        has_value(data, "price_change_count_1y") and data["price_change_count_1y"] >= 1,
        has_value(data, "price_reduction_amount") and data["price_reduction_amount"] > 0,
        recent_price_drop_value(data),
        data.get("back_on_market") == "Yes",
        "low buyer attention" in buyer_signal,
        data.get("buyer_leverage_score", 0) >= 3,
    ]

    if (
        data.get("final_decision") in {"Consider", "Watch"}
        and recent_dom
        and normal_or_strong_interest
        and manageable_risk
        and price_not_extreme
    ):
        return "Competitive Target"

    if (
        data.get("final_decision") != "Pass"
        and manageable_risk
        and sum(bool(signal) for signal in leverage_signals) >= 2
    ):
        return "Leverage Opportunity"

    return "Watch"

def update_strategy_category(data):
    data["garage_fit"] = classify_garage_fit(data)
    data["strategy_category"] = classify_strategy_category(data)
    return data

def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        text = f.read()

    lower_text = text.lower()

    data = {}

    metadata = load_extraction_metadata()
    data["listing_url"] = metadata.get("listing_url")
    data["mls_number"] = metadata.get("mls_number")
    data["idx_url"] = metadata.get("idx_url")
    data["source_pdf"] = metadata.get("source_pdf")
    data["image_folder"] = metadata.get("image_folder")
    data["listing_status"] = detect_listing_status(text)

    # Address
    address = None
    for line in text.splitlines():
        if "sioux falls, sd" in line.lower() and any(c.isdigit() for c in line):
            address = line.split("|")[0].strip()
            break
    data["address"] = address

    # Price
    data["price"] = extract_field(r"\$(\d{1,3},\d{3})", text)

    # Redfin PDFs include both living area and lot area. Never use lot-size
    # context as top-level home square footage.
    data["sq_ft"] = extract_pdf_living_sqft(text)

    # Beds / Baths
    data["beds"] = extract_field(r"(\d+)\s*bd", text)
    data["baths"] = extract_pdf_full_baths(text)

    # Year
    data["year_built"] = extract_field(r"Year Built\s+(\d{4})", text)

    # DOM
    data["days_on_redfin"] = extract_field(r"(\d+)\s+days on Redfin", text)

    # Popularity fields
    data["views"] = extract_int_field(
        [
            r"(\d[\d,]*)\s+views?\b",
            r"Viewed\s+(\d[\d,]*)\s+times\b",
            r"\bViews\s+(\d[\d,]*)\b",
        ],
        text,
    )
    data["favorites"] = extract_int_field(
        [
            r"(\d[\d,]*)\s+favorites?\b",
            r"Favorited\s+(\d[\d,]*)\s+times\b",
            r"\bFavorites\s+(\d[\d,]*)\b",
        ],
        text,
    )

    # Listing behavior
    data.update(extract_listing_history_1y(text))

    # Garage
    data["garage"] = detect_garage(text)

    if data["garage"] == "No":
        data["garage_type"] = None
    elif "detached garage" in lower_text:
        data["garage_type"] = "Detached"
    elif "attached garage" in lower_text:
        data["garage_type"] = "Attached"
    else:
        data["garage_type"] = None

    # Basement classification
    if "no basement" in lower_text:
        data["basement"] = "None"
    elif "finished basement" in lower_text:
        data["basement"] = "Finished"
    elif "unfinished basement" in lower_text:
        data["basement"] = "Unfinished"
    elif "basement" in lower_text:
        data["basement"] = "Unspecified"
    else:
        data["basement"] = "Unknown"

    # Flooring
    if "hardwood" in lower_text or "wood floors" in lower_text:
        data["flooring"] = "Wood"
    elif "vinyl" in lower_text or "lvp" in lower_text or "laminate" in lower_text:
        data["flooring"] = "Vinyl"
    else:
        data["flooring"] = "Unknown"

    # Fence
    if "fenced" in lower_text:
        data["fence"] = "Yes"
    elif "no fence" in lower_text:
        data["fence"] = "No"
    else:
        data["fence"] = "Unknown"

    recalculate_price_per_sqft(data)

    data = normalize_property(data)
    data["dom_status"] = classify_dom_status(data["days_on_redfin"])
    data["views_per_day"] = calculate_rate_per_day(data["views"], data["days_on_redfin"])
    data["favorites_per_day"] = calculate_rate_per_day(data["favorites"], data["days_on_redfin"])
    data["favorite_conversion_rate"] = calculate_favorite_conversion_rate(data["favorites"], data["views"])
    data["interest_velocity"] = classify_interest_velocity(data["views_per_day"])
    data["buyer_interest_signal"] = classify_buyer_interest_signal(data)
    data["market_interest_notes"] = missing_market_interest_notes(data)

    # Extracted facts are the normalized values above. The scoring below must
    # not reinterpret missing facts as negative or positive property condition.
    data = update_extraction_quality(data)

    update_property_risk(data)
    # Buyer leverage is based on current/listing behavior, not Redfin traffic.
    update_buyer_leverage(data)

    update_market_activity(data)

    # Recommendation logic is conservative and uses only known listing data.
    update_final_decision(data)
    update_strategy_category(data)

    # Legacy sheet/dashboard compatibility: strategy fit is no longer a
    # decision engine, but downstream exports still expect these fields.
    data.setdefault("strategy_fit_score", MISSING)
    data.setdefault("strategy_fit_flags", [])

    # Save
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print("Extraction complete")

if __name__ == "__main__":
    main()
