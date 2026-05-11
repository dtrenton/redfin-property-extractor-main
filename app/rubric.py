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
    market_activity_score = 1
    market_activity_flags = []

    if has_value(data, "days_on_redfin"):
        dom = int(data["days_on_redfin"])

        if dom <= 7:
            market_activity_score += 2
            market_activity_flags.append("0-7 days on Redfin")
        elif dom <= 14:
            market_activity_score += 1
            market_activity_flags.append("8-14 days on Redfin")
    else:
        market_activity_flags.append("Days on Redfin missing")

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

    if data["garage_requirement"] == "Fails requirement":
        final_decision = "Pass"
    elif data["data_completeness_score"] < 40 or len(missing_core_fields) >= 4:
        final_decision = "Data Insufficient"
    elif data["garage_requirement"] == "Unknown" or data["data_completeness_score"] < 70:
        final_decision = "Manual Verification Required"
    elif data["age_risk"] == "Higher age risk" and data["data_completeness_score"] < 85:
        final_decision = "Manual Verification Required"
    elif (
        data.get("buyer_leverage_score", 0) >= 4
        and has_value(data, "price_per_sqft")
        and data["price_per_sqft"] <= 180
        and data["garage_requirement"] == "Meets requirement"
    ):
        final_decision = "Consider"
    elif (
        has_value(data, "days_on_redfin")
        and int(data["days_on_redfin"]) <= 7
        and has_value(data, "price_per_sqft")
        and data["price_per_sqft"] <= 180
        and data["garage_requirement"] == "Meets requirement"
    ):
        final_decision = "Consider"
    else:
        final_decision = "Watch"

    data["final_decision"] = final_decision

    return data

def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        text = f.read()

    lower_text = text.lower()

    data = {}

    metadata = load_extraction_metadata()
    data["listing_url"] = metadata.get("listing_url")
    data["mls_number"] = metadata.get("mls_number")
    data["source_pdf"] = metadata.get("source_pdf")
    data["image_folder"] = metadata.get("image_folder")

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
    data["price_change_count"] = len(re.findall(r"\bprice\s+(?:changed|reduced|dropped|reduction)\b", lower_text))

    # Inferred market signals are based only on observable listing behavior:
    # DOM, recent listing/removal history, price changes, price per sq ft, garage,
    # home age, and missing-data level.
    buyer_leverage_score = 1
    buyer_leverage_flags = []

    if has_value(data, "days_on_redfin"):
        dom = int(data["days_on_redfin"])

        if dom >= 60:
            buyer_leverage_score += 2
            buyer_leverage_flags.append("60+ days on Redfin")
        elif dom >= 30:
            buyer_leverage_score += 1
            buyer_leverage_flags.append("30-59 days on Redfin")
        elif dom >= 8:
            buyer_leverage_score += 0.5
            buyer_leverage_flags.append("8-29 days on Redfin")

    if has_value(data, "listing_removed_count_1y") and data["listing_removed_count_1y"] >= 1:
        buyer_leverage_score += 1
        buyer_leverage_flags.append("Listing removed in last 365 days")

    if has_value(data, "price_change_count_1y") and data["price_change_count_1y"] >= 1:
        buyer_leverage_score += 1
        buyer_leverage_flags.append("Price change in last 365 days")

    if has_value(data, "listed_count_1y") and data["listed_count_1y"] > 1:
        buyer_leverage_score += 1
        buyer_leverage_flags.append("Multiple listings in last 365 days")

    data["buyer_leverage_score"] = min(buyer_leverage_score, 5)
    data["buyer_leverage_flags"] = buyer_leverage_flags

    update_market_activity(data)

    # Recommendation logic is conservative and uses only known listing data.
    update_final_decision(data)


    # Save
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print("Extraction complete")

if __name__ == "__main__":
    main()
