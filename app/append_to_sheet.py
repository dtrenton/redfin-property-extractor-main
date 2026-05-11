import json
import re
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

SHEET_ID = "1ZCf2qBp0TJ4iy2oi58geDf39cFCG6QTpB7rW2i3nHzg"
CREDENTIALS_FILE = "credentials/service_account.json"
INPUT_FILE = "outputs/scored_property.json"

HEADERS = [
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
    "final_decision",
    "date_added",
    "listing_url",
]

IDX_EXPORT_HEADERS = [
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
]

MARKET_TIMING_HEADERS = {
    "days_on_redfin",
    "days_on_market",
}

DASH_PLACEHOLDER_HEADERS = {
    "favorites",
    "views_per_day",
    "favorites_per_day",
    "interest_velocity",
    "favorite_conversion_rate",
}

STRUCTURAL_HEADERS = {
    "flooring",
    "fence",
    "basement",
    "roof",
    "foundation_details",
    "garage_type",
    "heating",
    "cooling",
    "construction_materials",
    "water_source",
    "sewer",
    "appliances",
    "interior_features",
}

NOT_PROVIDED_HEADERS = {
    "price_before_reduction",
    "price_reduction_date",
    "price_reduction_amount",
    "price_reduction_pct",
    "price_reduction_date_only",
    "mls_number",
    "idx_url",
}

PRICE_REDUCTION_HEADERS = {
    "price_before_reduction",
    "price_reduction_date",
    "price_reduction_amount",
    "price_reduction_pct",
}

REMOVED_EXPORT_HEADERS = {
    "listed_count_lifetime",
    "listing_removed_count_lifetime",
    "property_risk_score",
    "property_risk_flags",
    "buyer_leverage_score",
    "buyer_leverage_flags",
    "urgency_flags",
    "strategy_fit_score",
    "strategy_fit_flags",
    "notes",
    "source_pdf",
    "image_folder",
    "nar_contact_info",
    "listing_agent_name",
    "listing_brokerage",
    "listing_agent_email",
}


def column_letter(index):
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def first_idx_section_value(data, labels):
    for section in data.get("idx_details", {}).get("sections", {}).values():
        for label in labels:
            value = section.get(label)
            if value not in (None, ""):
                return value
    return None


def idx_derived_value(data, key):
    value = data.get("idx_details", {}).get("derived", {}).get(key)
    return value if value not in (None, "") else None


def numeric_value(value):
    if is_missing_export_value(value):
        return None
    match = re.search(r"\d+(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?", str(value))
    if not match:
        return None
    parsed = float(match.group(0).replace(",", ""))
    return int(parsed) if parsed.is_integer() else parsed


def date_value(value):
    if is_missing_export_value(value):
        return None
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", str(value).strip())
    if not match:
        return None
    year, month, day = match.groups()
    return f"{month}/{day}/{year}"


def currency_value(value):
    number = numeric_value(value)
    if number is None:
        return None
    return f"${int(round(number)):,}"


def percent_value(value):
    number = numeric_value(value)
    if number is None:
        return None
    return f"{number * 100:.1f}%"


def is_missing_export_value(value):
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().upper() in {
            "",
            "MISSING",
            "NULL",
            "NONE",
            "UNKNOWN",
            "UNSPECIFIED",
            "N/A",
            "NOT PROVIDED",
            "NO INFO",
            "DOES NOT APPLY",
        }
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) == 0
    return False


def does_not_apply(header, data):
    if header == "garage_amenities" and data.get("garage") == "No":
        return True
    if header == "finished_basement_pct" and str(data.get("basement", "")).strip().lower() in {
        "no",
        "none",
        "no basement",
        "missing",
    }:
        return True
    return False


def placeholder_for_header(header, data):
    if does_not_apply(header, data):
        return "Does Not Apply"
    if header in DASH_PLACEHOLDER_HEADERS:
        return "-"
    if header in MARKET_TIMING_HEADERS:
        return "<6 days"
    if header in STRUCTURAL_HEADERS:
        return "No Info"
    if header in NOT_PROVIDED_HEADERS:
        return "Not Provided"
    return "Not Provided"


def format_cell_value(value, header, data):
    if isinstance(value, list):
        value = " | ".join(str(item) for item in value if not is_missing_export_value(item))
    elif isinstance(value, dict):
        value = " | ".join(f"{key}: {val}" for key, val in value.items())

    if is_missing_export_value(value):
        return placeholder_for_header(header, data)

    return value


def value_for_header(data, header):
    if header in REMOVED_EXPORT_HEADERS:
        return ""

    if header == "date_added":
        return datetime.now().strftime("%Y-%m-%d")

    idx_fallbacks = {
        "construction_materials": lambda: first_idx_section_value(data, ["Construction Materials"]),
        "foundation_details": lambda: first_idx_section_value(data, ["Foundation Details"]),
        "roof": lambda: first_idx_section_value(data, ["Roof"]),
        "water_source": lambda: first_idx_section_value(data, ["Water Source"]),
        "heating": lambda: idx_derived_value(data, "heating"),
        "cooling": lambda: idx_derived_value(data, "cooling"),
        "garage_spaces": lambda: first_idx_section_value(data, ["# of Garage Spaces", "Garage Spaces"]),
        "garage_amenities": lambda: first_idx_section_value(data, ["Garage Amenities"]),
        "finished_basement_pct": lambda: idx_derived_value(data, "finished_basement_pct"),
        "acres": lambda: idx_derived_value(data, "acres"),
        "price_before_reduction": lambda: first_idx_section_value(data, ["Price Before Reduction"]),
        "price_reduction_date": lambda: first_idx_section_value(data, ["Price Reduction Date"]),
    }

    value = data.get(header)
    if is_missing_export_value(value) and header in idx_fallbacks:
        value = idx_fallbacks[header]()

    if header in PRICE_REDUCTION_HEADERS:
        price_before_reduction = numeric_value(
            data.get("price_before_reduction")
            or first_idx_section_value(data, ["Price Before Reduction"])
        )
        current_price = numeric_value(data.get("price"))
        reduction_amount = None
        if price_before_reduction is not None and current_price is not None:
            reduction_amount = price_before_reduction - current_price

        if price_before_reduction is None or current_price is None or reduction_amount is None or reduction_amount <= 0:
            return ""

        if header == "price_before_reduction":
            return currency_value(price_before_reduction)
        if header == "price_reduction_date":
            return date_value(value) or ""
        if header == "price_reduction_amount":
            return currency_value(reduction_amount)
        if header == "price_reduction_pct":
            return percent_value(reduction_amount / price_before_reduction)

    return format_cell_value(value, header, data)


def build_row(data, header_row):
    return [value_for_header(data, header) for header in header_row]


def desired_headers():
    return HEADERS + IDX_EXPORT_HEADERS


def remove_legacy_columns(sheet, existing):
    if not existing:
        return existing

    header_row = existing[0]
    indexes_to_remove = [
        index for index, header in enumerate(header_row) if header in REMOVED_EXPORT_HEADERS
    ]

    if not indexes_to_remove:
        return existing

    for index in reversed(indexes_to_remove):
        sheet.delete_columns(index + 1)

    removed_headers = [header_row[index] for index in indexes_to_remove]
    print(f"Removed legacy columns: {', '.join(removed_headers)}")
    return sheet.get_all_values()


def ensure_headers(sheet):
    existing = sheet.get_all_values()
    existing = remove_legacy_columns(sheet, existing)
    expected_headers = desired_headers()

    if not existing:
        header_row = expected_headers
        sheet.append_row(header_row)
        print("Headers created")
        return [header_row]

    header_row = existing[0]
    extra_headers = [
        header for header in header_row if header and header not in expected_headers
    ]
    synced_header_row = expected_headers + extra_headers

    if header_row != synced_header_row:
        end_col = column_letter(len(synced_header_row))
        sheet.update(f"A1:{end_col}1", [synced_header_row])
        print("Headers synchronized")
        existing[0] = synced_header_row

    return existing


def main():
    # Load JSON
    with open(INPUT_FILE, "r") as f:
        data = json.load(f)

    print(f"Listing URL: {data.get('listing_url', 'MISSING')}")

    # Auth
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
    client = gspread.authorize(creds)

    sheet = client.open_by_key(SHEET_ID).sheet1

    existing = ensure_headers(sheet)
    header_row = existing[0]
    row = build_row(data, header_row)
    listing_url_col = header_row.index("listing_url") + 1 if "listing_url" in header_row else None
    address_col = header_row.index("address") + 1 if "address" in header_row else 1

    listing_urls = sheet.col_values(listing_url_col) if listing_url_col else []
    addresses = sheet.col_values(address_col)
    row_number = None
    match_type = None

    if data.get("listing_url") and data.get("listing_url") != "MISSING" and data.get("listing_url") in listing_urls:
        row_number = listing_urls.index(data.get("listing_url")) + 1
        match_type = "listing_url"
    elif data.get("address") in addresses:
        row_number = addresses.index(data.get("address")) + 1
        match_type = "address"

    if row_number:
        end_col = column_letter(len(header_row))
        sheet.update(f"A{row_number}:{end_col}{row_number}", [row])
        print(f"Existing row updated by {match_type}")
    else:
        sheet.append_row(row)
        print("New row added")

if __name__ == "__main__":
    main()
