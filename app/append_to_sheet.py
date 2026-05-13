import json
import re
import sys
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

try:
    from enrich_with_idx import (
        IDX_UNAVAILABLE_WARNING,
        extract_mls_number_from_listing_url,
        extract_mls_number_from_text,
        idx_printable_unavailable,
        idx_url_for_mls,
        normalize_listing_status,
    )
    from extract_idx_page import extract_idx_page
except ModuleNotFoundError:
    from app.enrich_with_idx import (
        IDX_UNAVAILABLE_WARNING,
        extract_mls_number_from_listing_url,
        extract_mls_number_from_text,
        idx_printable_unavailable,
        idx_url_for_mls,
        normalize_listing_status,
    )
    from app.extract_idx_page import extract_idx_page

SHEET_ID = "1ZCf2qBp0TJ4iy2oi58geDf39cFCG6QTpB7rW2i3nHzg"
CREDENTIALS_FILE = "credentials/service_account.json"
INPUT_FILE = "outputs/scored_property.json"

HEADERS = [
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
    "data_completeness_score",
    "date_added",
    "listing_url",
    "mls_number",
    "idx_url",
    "last_checked",
    "refresh_success",
    "image_folder",
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

LIVE_REFRESH_HEADERS = [
    "mls_number",
    "idx_url",
    "current_status",
    "current_dom",
    "current_price",
    "last_checked",
    "refresh_success",
    "data_completeness_score",
    "recent_price_drop",
    "price_drop_pct",
    "back_on_market",
    "pending_speed",
    "live_market_interest_score",
    "live_market_interest_flags",
    "refresh_notes",
]

REFRESH_NOTES_HEADER = "refresh_notes"
APPROVED_APPEND_ONLY_HEADER_ORDER = LIVE_REFRESH_HEADERS
APPROVED_APPEND_ONLY_HEADERS = set(APPROVED_APPEND_ONLY_HEADER_ORDER)

UNWANTED_LIVE_REFRESH_HEADERS = {
    "market_interest_notes",
    "missing_fields",
    "extraction_confidence_score",
    "age_risk",
    "garage_requirement",
    "price_per_sqft_signal",
    "price_change_count",
    "market_activity_score",
    "market_activity_flags",
}

AUTO_PAYLOAD_HEADER_EXCLUDE = {
    "idx_details",
    "rooms",
    "idx_enrichment_errors",
    "idx_enrichment_warnings",
    "idx_enriched_fields",
    "validation_warnings",
} | UNWANTED_LIVE_REFRESH_HEADERS

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

BLANK_IF_MISSING_HEADERS = {
    "last_checked",
    "refresh_success",
    "refresh_notes",
}

REMOVED_EXPORT_HEADERS = UNWANTED_LIVE_REFRESH_HEADERS


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
        "no info",
        "missing",
    }:
        return True
    return False


def idx_enrichment_succeeded(data):
    return data.get("idx_enrichment_status") == "success"


def idx_has_basement_field(data):
    for section in data.get("idx_details", {}).get("sections", {}).values():
        if "Basement" in section:
            return True
    return False


def idx_has_fence_field(data):
    for section in data.get("idx_details", {}).get("sections", {}).values():
        if "Fencing" in section or "Fence" in section:
            return True
    return False


def garage_is_no(data):
    return str(data.get("garage", "")).strip().lower() == "no"


def garage_fit_value(data):
    garage = str(data.get("garage", "")).strip().lower()
    if garage == "yes":
        return "Garage Present"
    if garage == "no":
        return "No Garage"
    return "Garage Unknown"


def placeholder_for_header(header, data):
    if header in BLANK_IF_MISSING_HEADERS:
        return ""
    if header == "garage_spaces" and garage_is_no(data):
        return 0
    if header == "garage_type" and garage_is_no(data):
        return "No Garage"
    if header == "basement" and idx_enrichment_succeeded(data) and not idx_has_basement_field(data):
        return "No Basement"
    if header == "fence" and idx_enrichment_succeeded(data) and not idx_has_fence_field(data):
        return "No Fence"
    if does_not_apply(header, data):
        return "Does Not Apply"
    if header == "finished_basement_pct":
        return "No Info"
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
    if header == "listing_status" and is_missing_export_value(value):
        value = "For Sale"

    if header == "current_status" and is_missing_export_value(value):
        value = data.get("listing_status") or "For Sale"

    if header == "garage_fit" and is_missing_export_value(value):
        value = garage_fit_value(data)

    if is_missing_export_value(value) and header in idx_fallbacks:
        value = idx_fallbacks[header]()

    if header == "fence" and value is not None and str(value).strip().lower() in {"no", "none", "no fence"}:
        return "No Fence"
    if header == "garage_type" and value is not None and str(value).strip().lower() in {"no", "none", "no garage"}:
        return "No Garage"

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


def build_update_row(existing_values, header_row, data):
    row = list(existing_values)
    if len(row) < len(header_row):
        row.extend([""] * (len(header_row) - len(row)))

    writable_headers = set(desired_headers(data)) | set(data.keys())
    writable_headers -= REMOVED_EXPORT_HEADERS

    for index, header in enumerate(header_row):
        if header in writable_headers:
            row[index] = value_for_header(data, header)
    return row


def unique_headers(headers):
    seen = set()
    unique = []
    for header in headers:
        if header and header not in seen:
            unique.append(header)
            seen.add(header)
    return unique


def payload_headers(data):
    if not data:
        return []
    return [
        header
        for header in data.keys()
        if header in APPROVED_APPEND_ONLY_HEADERS
        and header not in AUTO_PAYLOAD_HEADER_EXCLUDE
        and header not in REMOVED_EXPORT_HEADERS
    ]


def desired_headers(data=None):
    return unique_headers(HEADERS + IDX_EXPORT_HEADERS + LIVE_REFRESH_HEADERS + payload_headers(data))


def validate_append_only_headers(old_headers, new_headers):
    if new_headers[: len(old_headers)] != old_headers:
        raise RuntimeError(
            "Header safety check failed: existing headers would be renamed, removed, or moved. "
            "Aborting without writing to Google Sheets."
        )


def append_missing_headers_only(sheet, existing, missing_headers):
    if not missing_headers:
        return existing

    old_headers = existing[0]
    new_headers = old_headers + missing_headers
    validate_append_only_headers(old_headers, new_headers)
    required_total_columns = len(new_headers)
    if required_total_columns > sheet.col_count:
        sheet.add_cols(required_total_columns - sheet.col_count)

    start_col = column_letter(len(old_headers) + 1)
    end_col = column_letter(len(new_headers))
    sheet.update(range_name=f"{start_col}1:{end_col}1", values=[missing_headers])
    print(f"Headers appended: {', '.join(missing_headers)}")
    existing[0] = new_headers
    return existing


def ensure_headers(sheet, data=None, remove_legacy=False):
    existing = sheet.get_all_values()
    expected_headers = desired_headers(data)

    if not existing:
        header_row = expected_headers
        sheet.append_row(header_row)
        print("Headers created")
        return [header_row]

    header_row = existing[0]
    missing_headers = [
        header for header in APPROVED_APPEND_ONLY_HEADER_ORDER
        if header in expected_headers and header not in header_row
    ]
    return append_missing_headers_only(sheet, existing, missing_headers)


def auth_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).sheet1


def row_dict_from_values(header_row, values):
    return {
        header: values[index] if index < len(values) else ""
        for index, header in enumerate(header_row)
    }


def existing_cell(row_data, *headers):
    for header in headers:
        value = row_data.get(header)
        if not is_missing_export_value(value):
            return value
    return None


def derive_mls_from_existing_row(row_data):
    return (
        existing_cell(row_data, "mls_number")
        or extract_mls_number_from_text(existing_cell(row_data, "source_pdf"))
        or extract_mls_number_from_listing_url(existing_cell(row_data, "listing_url"))
    )


def derive_idx_url_from_existing_row(row_data):
    existing_idx_url = existing_cell(row_data, "idx_url")
    mls_number = derive_mls_from_existing_row(row_data)
    if existing_idx_url:
        return existing_idx_url, mls_number

    if not mls_number:
        return None, None
    return idx_url_for_mls(mls_number), mls_number


def refresh_row_payload(row_data):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "last_checked": now,
        "refresh_success": "No",
        "refresh_notes": "",
    }

    idx_url, mls_number = derive_idx_url_from_existing_row(row_data)
    if mls_number:
        payload["mls_number"] = mls_number
    if idx_url:
        payload["idx_url"] = idx_url
    else:
        payload["refresh_notes"] = "MLS number unavailable; idx_url could not be derived."
        return payload

    try:
        idx_data = extract_idx_page(idx_url)
    except Exception as exc:
        payload["refresh_notes"] = f"IDX refresh failed: {exc}"
        return payload

    if idx_printable_unavailable(idx_data):
        payload["refresh_notes"] = IDX_UNAVAILABLE_WARNING
        payload["current_status"] = existing_cell(row_data, "current_status", "listing_status") or ""
        return payload

    errors = idx_data.get("debug", {}).get("errors", [])
    if errors:
        payload["refresh_notes"] = "; ".join(str(error) for error in errors)
        return payload

    current_status = normalize_listing_status(idx_data.get("mls_status"))
    if current_status:
        payload["current_status"] = current_status
    elif existing_cell(row_data, "listing_status"):
        payload["current_status"] = existing_cell(row_data, "listing_status")

    payload["refresh_success"] = "Yes"
    payload["refresh_notes"] = "IDX refresh completed."
    return payload


def set_row_values(existing_values, header_row, updates):
    row = list(existing_values)
    if len(row) < len(header_row):
        row.extend([""] * (len(header_row) - len(row)))

    for header, value in updates.items():
        if header in header_row:
            row[header_row.index(header)] = value
    return row


def find_existing_row_number(data, listing_urls, source_pdfs, addresses):
    if data.get("listing_url") and data.get("listing_url") != "MISSING" and data.get("listing_url") in listing_urls:
        return listing_urls.index(data.get("listing_url")) + 1, "listing_url"
    if data.get("source_pdf") and data.get("source_pdf") != "MISSING" and data.get("source_pdf") in source_pdfs:
        return source_pdfs.index(data.get("source_pdf")) + 1, "source_pdf"
    if data.get("address") in addresses:
        return addresses.index(data.get("address")) + 1, "address"
    return None, None


def cleanup_live_refresh_columns():
    print(
        "Automatic column deletion is disabled. "
        "No Google Sheet columns were removed or reordered."
    )


def refresh_existing_rows():
    sheet = auth_sheet()
    existing = ensure_headers(
        sheet,
        {"idx_url": "", "current_status": "", "last_checked": "", "refresh_success": "", "refresh_notes": ""},
        remove_legacy=False,
    )
    if len(existing) <= 1:
        print("No existing property rows to refresh")
        return

    header_row = existing[0]
    refreshed = 0
    failed = 0

    for row_number, values in enumerate(existing[1:], start=2):
        row_data = row_dict_from_values(header_row, values)
        updates = refresh_row_payload(row_data)
        next_row = set_row_values(values, header_row, updates)
        end_col = column_letter(len(header_row))
        sheet.update(range_name=f"A{row_number}:{end_col}{row_number}", values=[next_row])

        if updates.get("refresh_success") == "Yes":
            refreshed += 1
        else:
            failed += 1

        identifier = row_data.get("address") or row_data.get("listing_url") or f"row {row_number}"
        print(
            f"Refreshed {identifier}: {updates.get('refresh_success')} - "
            f"{updates.get('refresh_notes')}"
        )

    print(f"Refresh summary: {refreshed} succeeded, {failed} need attention")


def main():
    dry_run = "--dry-run" in sys.argv

    # Load JSON
    with open(INPUT_FILE, "r") as f:
        data = json.load(f)

    print(f"Listing URL: {data.get('listing_url', 'MISSING')}")

    sheet = auth_sheet()

    existing = sheet.get_all_values() if dry_run else ensure_headers(sheet, data)
    if not existing:
        existing = [desired_headers(data)]
    header_row = existing[0]
    listing_url_col = header_row.index("listing_url") + 1 if "listing_url" in header_row else None
    source_pdf_col = header_row.index("source_pdf") + 1 if "source_pdf" in header_row else None
    address_col = header_row.index("address") + 1 if "address" in header_row else 1

    listing_urls = sheet.col_values(listing_url_col) if listing_url_col else []
    source_pdfs = sheet.col_values(source_pdf_col) if source_pdf_col else []
    addresses = sheet.col_values(address_col)
    row_number, match_type = find_existing_row_number(
        data,
        listing_urls,
        source_pdfs,
        addresses,
    )

    if row_number:
        end_col = column_letter(len(header_row))
        existing_values = existing[row_number - 1] if row_number - 1 < len(existing) else []
        row = build_update_row(existing_values, header_row, data)
        if dry_run:
            print(f"DRY RUN: Existing row would be updated by {match_type}")
            print(f"ROW_MATCH_METHOD: {match_type}")
            print("UPDATE_RESULT: would update existing row")
        else:
            sheet.update(range_name=f"A{row_number}:{end_col}{row_number}", values=[row])
            print(f"Existing row updated by {match_type}")
            print(f"ROW_MATCH_METHOD: {match_type}")
            print("UPDATE_RESULT: updated existing row")
    else:
        row = build_row(data, header_row)
        if dry_run:
            print("DRY RUN: New row would be added")
            print("ROW_MATCH_METHOD: none")
            print("UPDATE_RESULT: would append new row")
        else:
            sheet.append_row(row)
            print("New row added")
            print("ROW_MATCH_METHOD: none")
            print("UPDATE_RESULT: appended new row")

if __name__ == "__main__":
    if "--cleanup-live-refresh-columns" in sys.argv or "cleanup_live_refresh_columns" in sys.argv:
        cleanup_live_refresh_columns()
    elif "--refresh-existing-rows" in sys.argv or "refresh_existing_rows" in sys.argv:
        refresh_existing_rows()
    else:
        main()
