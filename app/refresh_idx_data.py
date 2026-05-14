import argparse
import time
from datetime import datetime

try:
    from append_to_sheet import (
        APPROVED_APPEND_ONLY_HEADER_ORDER,
        auth_sheet,
        column_letter,
        ensure_headers,
        is_missing_export_value,
        numeric_value,
        normalize_sheet_value,
        row_dict_from_values,
        set_row_values,
        value_for_header,
    )
    from extract_idx_page import extract_idx_page
    from rubric import (
        MISSING,
        update_buyer_leverage,
        update_live_market_interest,
    )
except ModuleNotFoundError:
    from app.append_to_sheet import (
        APPROVED_APPEND_ONLY_HEADER_ORDER,
        auth_sheet,
        column_letter,
        ensure_headers,
        is_missing_export_value,
        numeric_value,
        normalize_sheet_value,
        row_dict_from_values,
        set_row_values,
        value_for_header,
    )
    from app.extract_idx_page import extract_idx_page
    from app.rubric import (
        MISSING,
        update_buyer_leverage,
        update_live_market_interest,
    )


SNAPSHOT_ONLY_FIELDS = {
    "views",
    "favorites",
    "views_per_day",
    "favorites_per_day",
    "favorite_conversion_rate",
    "interest_velocity",
}

REFRESH_HEADERS = [
    "current_status",
    "current_dom",
    "current_price",
    "price_change_count_1y",
    "price_before_reduction",
    "price_reduction_date",
    "price_reduction_amount",
    "price_reduction_pct",
    "listing_photo_url",
    "idx_image_urls",
    "last_checked",
    "refresh_success",
    "refresh_notes",
    "recent_price_drop",
    "price_drop_pct",
    "back_on_market",
    "pending_speed",
    "live_market_interest_score",
    "live_market_interest_flags",
    "buyer_leverage_score",
    "buyer_leverage_flags",
]

PRICE_REDUCTION_LABELS = [
    "Price Before Reduction",
    "Previous Price",
    "Original Price",
]

PRICE_REDUCTION_DATE_LABELS = [
    "Price Reduction Date",
]

NUMERIC_FIELDS = [
    "price_change_count_1y",
    "listed_count_1y",
    "listing_removed_count_1y",
    "current_dom",
    "days_on_redfin",
    "current_price",
    "price",
    "sq_ft",
    "price_per_sqft",
    "views",
    "favorites",
]

INTEGER_FIELDS = {
    "price_change_count_1y",
    "listed_count_1y",
    "listing_removed_count_1y",
    "current_dom",
    "days_on_redfin",
    "views",
    "favorites",
}


def is_quota_error(exc):
    text = str(exc).lower()
    return "429" in text or "quota exceeded" in text or "rate limit" in text


def with_retry(action, description, stats, max_attempts=5):
    delay = 1
    for attempt in range(1, max_attempts + 1):
        try:
            return action()
        except Exception as exc:
            if not is_quota_error(exc) or attempt == max_attempts:
                raise
            stats["api_retries"] += 1
            print(f"Google Sheets rate limit during {description}; retrying in {delay}s")
            time.sleep(delay)
            delay *= 2


def chunks(values, size):
    for index in range(0, len(values), size):
        yield values[index : index + size]


def blankish(value):
    if value is None:
        return True
    return str(value).strip().upper() in {
        "",
        "MISSING",
        "NOT PROVIDED",
        "NO INFO",
        "DOES NOT APPLY",
        "-",
    }


def to_int(value, default=0):
    if blankish(value):
        return default
    try:
        return int(float(str(value).replace("$", "").replace(",", "").strip()))
    except (TypeError, ValueError):
        return default


def to_float(value, default=None):
    if blankish(value):
        return default
    try:
        return float(str(value).replace("$", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def coerce_numeric_fields(data):
    coerced = dict(data)
    for field in NUMERIC_FIELDS:
        if field not in coerced:
            continue
        if field in INTEGER_FIELDS:
            coerced[field] = to_int(coerced.get(field), default=0)
        else:
            converted = to_float(coerced.get(field))
            if converted is not None:
                coerced[field] = converted
    return coerced


def first_section_value(idx_data, labels):
    for section in idx_data.get("sections", {}).values():
        for label in labels:
            value = section.get(label)
            if not is_missing_export_value(value):
                return value
    return None


def normalize_status(value):
    if is_missing_export_value(value):
        return None
    text = str(value)
    if "sold" in text.lower() or "closed" in text.lower():
        return "Sold"
    if "pending" in text.lower() or "under contract" in text.lower() or "contingent" in text.lower():
        return "Pending"
    if "active" in text.lower() or "for sale" in text.lower():
        return "For Sale"
    return text.strip()


def extract_current_dom(idx_data):
    value = first_section_value(
        idx_data,
        [
            "Days On Market",
            "Days on Market",
            "DOM",
            "Cumulative Days On Market",
            "Cumulative Days on Market",
        ],
    )
    number = numeric_value(value)
    return number if number is not None else None


def extract_price_change_count_1y(idx_data, existing_value):
    # IDX printable pages usually expose current fields rather than a full event
    # timeline. Preserve the existing Redfin-derived 1-year count unless IDX
    # later exposes a directly parseable count.
    if not is_missing_export_value(existing_value):
        return existing_value
    return None


def build_refresh_payload(row_data, idx_data):
    payload = {
        "last_checked": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "refresh_success": "TRUE",
        "refresh_notes": "IDX refresh completed.",
    }

    status = normalize_status(idx_data.get("mls_status"))
    if status:
        payload["current_status"] = status

    current_dom = extract_current_dom(idx_data)
    if current_dom is not None:
        payload["current_dom"] = current_dom

    current_price = numeric_value(idx_data.get("price"))
    if current_price is not None:
        payload["current_price"] = current_price

    if not is_missing_export_value(idx_data.get("listing_photo_url")):
        payload["listing_photo_url"] = idx_data.get("listing_photo_url")
    if not is_missing_export_value(idx_data.get("idx_image_urls")):
        payload["idx_image_urls"] = idx_data.get("idx_image_urls")

    price_change_count = extract_price_change_count_1y(
        idx_data,
        row_data.get("price_change_count_1y"),
    )
    if price_change_count is not None:
        payload["price_change_count_1y"] = price_change_count

    price_before_reduction = numeric_value(first_section_value(idx_data, PRICE_REDUCTION_LABELS))
    price_reduction_date = first_section_value(idx_data, PRICE_REDUCTION_DATE_LABELS)
    if price_before_reduction and current_price and price_before_reduction > current_price:
        reduction_amount = price_before_reduction - current_price
        payload["price_before_reduction"] = price_before_reduction
        if not is_missing_export_value(price_reduction_date):
            payload["price_reduction_date"] = price_reduction_date
        payload["price_reduction_amount"] = round(reduction_amount, 2)
        payload["price_reduction_pct"] = round(reduction_amount / price_before_reduction, 4)
        payload["recent_price_drop"] = "Yes"
        payload["price_drop_pct"] = payload["price_reduction_pct"]
    elif not is_missing_export_value(row_data.get("price_reduction_amount")):
        payload["recent_price_drop"] = "Yes"
    else:
        payload["recent_price_drop"] = "No"

    scoring_data = coerce_numeric_fields(row_data)
    scoring_data.update(payload)
    scoring_data = coerce_numeric_fields(scoring_data)
    update_live_market_interest(scoring_data)
    update_buyer_leverage(scoring_data)

    for header in [
        "recent_price_drop",
        "price_drop_pct",
        "back_on_market",
        "pending_speed",
        "live_market_interest_score",
        "live_market_interest_flags",
        "buyer_leverage_score",
        "buyer_leverage_flags",
    ]:
        if header in scoring_data and not is_missing_export_value(scoring_data.get(header)):
            payload[header] = scoring_data[header]

    return payload


def format_refresh_updates_for_sheet(row_data, payload):
    formatted = dict(payload)
    merged = dict(row_data)
    merged.update(payload)

    for header in [
        "price_before_reduction",
        "price_reduction_date",
        "price_reduction_amount",
        "price_reduction_pct",
        "last_checked",
        "refresh_success",
    ]:
        if header not in formatted:
            continue
        formatted_value = value_for_header(merged, header)
        if not is_missing_export_value(formatted_value):
            formatted[header] = formatted_value

    return formatted


def row_identifier(row_data):
    return (
        row_data.get("listing_url")
        or row_data.get("idx_url")
        or row_data.get("address")
        or "unknown row"
    )


def safe_updates_for_row(row_data, payload):
    updates = {}
    for header, value in format_refresh_updates_for_sheet(row_data, payload).items():
        if header in SNAPSHOT_ONLY_FIELDS:
            continue
        if is_missing_export_value(value) and not header.startswith("refresh_"):
            continue
        updates[header] = value
    return updates


def prepare_sheet(dry_run, stats):
    sheet = auth_sheet()
    seed = {header: "" for header in APPROVED_APPEND_ONLY_HEADER_ORDER}
    if dry_run:
        existing = with_retry(sheet.get_all_values, "read rows", stats)
        if not existing:
            existing = [list(seed.keys())]
        else:
            missing = [header for header in APPROVED_APPEND_ONLY_HEADER_ORDER if header not in existing[0]]
            if missing:
                existing[0] = existing[0] + missing
        return sheet, existing

    existing = with_retry(
        lambda: ensure_headers(sheet, seed, remove_legacy=False),
        "ensure headers",
        stats,
    )
    return sheet, existing


def write_updates(sheet, header_row, updates, batch_size, stats):
    for batch in chunks(sorted(updates.items()), batch_size):
        body = [
            {
                "range": f"A{row_number}:{column_letter(len(header_row))}{row_number}",
                "values": [[
                    normalize_sheet_value(value, header_row[index] if index < len(header_row) else None)
                    for index, value in enumerate(row)
                ]],
            }
            for row_number, row in batch
        ]
        with_retry(lambda body=body: sheet.batch_update(body), "batch row updates", stats)
        time.sleep(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sheet-batch-size", type=int, default=25)
    args = parser.parse_args()

    stats = {
        "rows_refreshed": 0,
        "rows_skipped": 0,
        "idx_failures": 0,
        "api_retries": 0,
        "status_transitions": 0,
        "price_drops_detected": 0,
    }

    sheet, existing = prepare_sheet(args.dry_run, stats)
    if len(existing) <= 1:
        print("No existing rows to refresh")
        return

    header_row = existing[0]
    staged_updates = {}
    seen_keys = set()

    for row_number, values in enumerate(existing[1:], start=2):
        row_data = row_dict_from_values(header_row, values)
        idx_url = row_data.get("idx_url")
        key = row_data.get("listing_url") or idx_url or row_data.get("address")

        if key in seen_keys:
            stats["rows_skipped"] += 1
            print(f"Row {row_number}: skipped duplicate key {key}")
            continue
        if key:
            seen_keys.add(key)

        if is_missing_export_value(idx_url):
            stats["rows_skipped"] += 1
            print(f"Row {row_number}: skipped missing idx_url ({row_identifier(row_data)})")
            continue

        try:
            idx_data = extract_idx_page(idx_url)
        except Exception as exc:
            stats["idx_failures"] += 1
            payload = {
                "last_checked": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "refresh_success": "FALSE",
                "refresh_notes": f"IDX fetch failed: {exc}",
            }
            updates = safe_updates_for_row(row_data, payload)
            next_row = set_row_values(values, header_row, updates)
            staged_updates[row_number] = next_row
            print(f"Row {row_number}: IDX failure for {row_identifier(row_data)}")
            continue

        errors = idx_data.get("debug", {}).get("errors", [])
        if errors:
            stats["idx_failures"] += 1
            payload = {
                "last_checked": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "refresh_success": "FALSE",
                "refresh_notes": "; ".join(str(error) for error in errors),
            }
        else:
            payload = build_refresh_payload(row_data, idx_data)
            old_status = row_data.get("current_status") or row_data.get("listing_status")
            new_status = payload.get("current_status")
            if new_status and old_status and new_status != old_status:
                stats["status_transitions"] += 1
            if payload.get("recent_price_drop") == "Yes":
                stats["price_drops_detected"] += 1
            stats["rows_refreshed"] += 1

        updates = safe_updates_for_row(row_data, payload)
        next_row = set_row_values(values, header_row, updates)
        staged_updates[row_number] = next_row
        result = "would update" if args.dry_run else "staged"
        print(f"Row {row_number}: {result} {row_identifier(row_data)}")

    if args.dry_run:
        print("Dry run complete; Google Sheet not written.")
    elif staged_updates:
        write_updates(sheet, header_row, staged_updates, max(1, args.sheet_batch_size), stats)

    print(
        "Summary: "
        f"rows refreshed: {stats['rows_refreshed']}, "
        f"rows skipped: {stats['rows_skipped']}, "
        f"IDX failures: {stats['idx_failures']}, "
        f"API retries: {stats['api_retries']}, "
        f"pending/sold transitions detected: {stats['status_transitions']}, "
        f"price drops detected: {stats['price_drops_detected']}"
    )


if __name__ == "__main__":
    main()
