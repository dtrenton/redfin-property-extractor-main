from append_to_sheet import (
    auth_sheet,
    column_letter,
    derive_idx_url_from_existing_row,
    ensure_headers,
    row_dict_from_values,
    set_row_values,
)


def main():
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
        if mls_number and not row_data.get("mls_number"):
            updates["mls_number"] = mls_number
        if idx_url and not row_data.get("idx_url"):
            updates["idx_url"] = idx_url

        if updates:
            next_row = set_row_values(values, header_row, updates)
            end_col = column_letter(len(header_row))
            sheet.update(f"A{row_number}:{end_col}{row_number}", [next_row])
            updated += 1
            identifier = row_data.get("address") or row_data.get("listing_url") or f"row {row_number}"
            print(f"Backfilled {identifier}: {', '.join(updates.keys())}")
        else:
            skipped += 1

    print(f"Backfill summary: {updated} updated, {skipped} skipped")


if __name__ == "__main__":
    main()
