import sys

from append_to_sheet import (
    auth_sheet,
    column_letter,
    derive_idx_url_from_existing_row,
    ensure_headers,
    is_missing_export_value,
    row_dict_from_values,
    set_row_values,
)


def should_fill(value):
    return is_missing_export_value(value)


def main():
    dry_run = "--dry-run" in sys.argv
    sheet = auth_sheet()
    existing = ensure_headers(
        sheet,
        {"mls_number": "", "idx_url": "", "current_status": "", "last_checked": "", "refresh_success": "", "refresh_notes": ""},
        remove_legacy=False,
    )

    if len(existing) <= 1:
        print("No existing property rows to backfill")
        return

    header_row = existing[0]
    updated = 0
    skipped = 0

    for row_number, values in enumerate(existing[1:], start=2):
        row_data = row_dict_from_values(header_row, values)
        idx_url, mls_number = derive_idx_url_from_existing_row(row_data)

        updates = {}
        if mls_number and should_fill(row_data.get("mls_number")):
            updates["mls_number"] = mls_number
        if idx_url and should_fill(row_data.get("idx_url")):
            updates["idx_url"] = idx_url

        identifier = row_data.get("address") or row_data.get("listing_url") or f"row {row_number}"
        source_pdf = row_data.get("source_pdf", "")
        if updates:
            update_result = f"{'would update' if dry_run else 'updated'} {', '.join(updates.keys())}"
        else:
            update_result = "skipped; existing values already present" if idx_url or mls_number else "skipped; MLS not found"

        print(f"Row {row_number}")
        print(f"  address: {identifier}")
        print(f"  source_pdf: {source_pdf}")
        print(f"  derived_mls_number: {mls_number or ''}")
        print(f"  derived_idx_url: {idx_url or ''}")
        print(f"  update_result: {update_result}")

        if updates:
            if not dry_run:
                next_row = set_row_values(values, header_row, updates)
                end_col = column_letter(len(header_row))
                sheet.update(range_name=f"A{row_number}:{end_col}{row_number}", values=[next_row])
            updated += 1
        else:
            skipped += 1

    action = "would update" if dry_run else "updated"
    print(f"Backfill summary: {updated} {action}, {skipped} skipped")


if __name__ == "__main__":
    main()
