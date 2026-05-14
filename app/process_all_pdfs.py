import json
import argparse
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

try:
    from append_to_sheet import (
        APPROVED_APPEND_ONLY_HEADER_ORDER,
        auth_sheet,
        build_row,
        build_update_row,
        column_letter,
        desired_headers,
        ensure_headers,
        find_existing_row_number,
        normalize_sheet_value,
    )
except ModuleNotFoundError:
    from app.append_to_sheet import (
        APPROVED_APPEND_ONLY_HEADER_ORDER,
        auth_sheet,
        build_row,
        build_update_row,
        column_letter,
        desired_headers,
        ensure_headers,
        find_existing_row_number,
        normalize_sheet_value,
    )


SAMPLES_DIR = Path("samples")
PROCESSED_DIR = Path("processed")
SCORED_PROPERTY_FILE = Path("outputs/scored_property.json")
EXTRACTION_METADATA_FILE = Path("outputs/extraction_metadata.json")
MISSING = "MISSING"


def run_step(command):
    return subprocess.run(command, capture_output=True, text=True)


def is_quota_error(exc):
    text = str(exc).lower()
    return "429" in text or "quota exceeded" in text or "read requests per minute" in text


def with_sheet_retry(action, description, stats, max_attempts=5):
    delay = 1
    for attempt in range(1, max_attempts + 1):
        try:
            return action()
        except Exception as exc:
            if not is_quota_error(exc) or attempt == max_attempts:
                raise
            stats["google_sheet_retries"] += 1
            print(f"Google Sheets quota hit during {description}; retrying in {delay}s")
            time.sleep(delay)
            delay *= 2


def chunks(values, size):
    for index in range(0, len(values), size):
        yield values[index : index + size]


def is_duplicate_copy_pdf(path):
    name = path.name.lower()
    return bool(re.search(r"\(\d+\)", name)) or "copy" in name


def unique_destination(path):
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent

    counter = 1
    while True:
        candidate = parent / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def load_json(path):
    if not path.exists():
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def property_summary(data=None):
    data = data or {}
    idx_warnings = data.get("idx_enrichment_warnings") or []
    return {
        "address": data.get("address") or MISSING,
        "listing_url": data.get("listing_url") or MISSING,
        "source_pdf": data.get("source_pdf") or MISSING,
        "derived_mls_number": data.get("mls_number") or MISSING,
        "derived_idx_url": data.get("idx_url") or MISSING,
        "image_folder": data.get("image_folder") or MISSING,
        "final_decision": data.get("final_decision") or MISSING,
        "row_match_method": data.get("row_match_method") or MISSING,
        "update_result": data.get("update_result") or MISSING,
        "idx_warning": idx_warnings[0] if idx_warnings else "",
    }


def print_property_summary(pdf_name, summary, status, message=None):
    print(f"{status}: {pdf_name}")
    print(f"  address: {summary['address']}")
    print(f"  source_pdf: {summary['source_pdf']}")
    print(f"  derived_mls_number: {summary['derived_mls_number']}")
    print(f"  derived_idx_url: {summary['derived_idx_url']}")
    print(f"  row_match_method: {summary['row_match_method']}")
    print(f"  update_result: {summary['update_result']}")
    print(f"  listing_url: {summary['listing_url']}")
    print(f"  image_folder: {summary['image_folder']}")
    print(f"  final_decision: {summary['final_decision']}")
    if summary.get("idx_warning"):
        print(f"  warning: {summary['idx_warning']}")
    if message:
        print(f"  details: {message}")


def process_pdf_locally(pdf_path):
    steps = [
        ("extract", [sys.executable, "app/extract_redfin_pdf.py", str(pdf_path)]),
        ("score", [sys.executable, "app/rubric.py"]),
        ("idx_enrich", [sys.executable, "app/enrich_with_idx.py"]),
    ]

    summary = property_summary()
    scored_property = {}

    for step_name, command in steps:
        result = run_step(command)

        if step_name == "extract":
            summary.update(property_summary(load_json(EXTRACTION_METADATA_FILE)))
        elif step_name in {"score", "idx_enrich"}:
            scored_property = load_json(SCORED_PROPERTY_FILE)
            summary.update(property_summary(scored_property))

        if result.returncode != 0:
            error = result.stderr.strip() or result.stdout.strip()
            return False, summary, f"{step_name} failed: {error}", {}

    return True, summary, "local processing complete", scored_property


def move_pdf_to_processed(pdf_path):
    PROCESSED_DIR.mkdir(exist_ok=True)
    destination = unique_destination(PROCESSED_DIR / pdf_path.name)
    shutil.move(str(pdf_path), str(destination))
    return destination


def approved_header_seed():
    return {header: "" for header in APPROVED_APPEND_ONLY_HEADER_ORDER}


def read_or_prepare_sheet(dry_run, stats):
    sheet = auth_sheet()
    if dry_run:
        existing = with_sheet_retry(sheet.get_all_values, "read existing rows", stats)
        if not existing:
            existing = [desired_headers(approved_header_seed())]
        else:
            header_row = existing[0]
            missing_headers = [
                header for header in APPROVED_APPEND_ONLY_HEADER_ORDER if header not in header_row
            ]
            if missing_headers:
                existing[0] = header_row + missing_headers
        return sheet, existing

    existing = with_sheet_retry(
        lambda: ensure_headers(sheet, approved_header_seed(), remove_legacy=False),
        "ensure headers",
        stats,
    )
    return sheet, existing


def column_values(existing, header_row, header):
    if header not in header_row:
        return []
    index = header_row.index(header)
    return [row[index] if index < len(row) else "" for row in existing]


def stage_sheet_row(data, header_row, existing, original_existing_count, staged_appends, staged_updates):
    listing_urls = column_values(existing, header_row, "listing_url")
    source_pdfs = column_values(existing, header_row, "source_pdf")
    addresses = column_values(existing, header_row, "address")
    row_number, match_type = find_existing_row_number(data, listing_urls, source_pdfs, addresses)

    if row_number:
        existing_values = existing[row_number - 1] if row_number - 1 < len(existing) else []
        row = build_update_row(existing_values, header_row, data)
        existing[row_number - 1] = row
        if row_number <= original_existing_count:
            staged_updates[row_number] = row
        else:
            staged_appends[row_number - original_existing_count - 1] = row
        return match_type, "update existing row"

    row = build_row(data, header_row)
    existing.append(row)
    staged_appends.append(row)
    return "none", "append new row"


def write_sheet_changes(sheet, header_row, staged_updates, staged_appends, batch_size, stats):
    update_items = sorted(staged_updates.items())
    for batch in chunks(update_items, batch_size):
        data = [
            {
                "range": f"A{row_number}:{column_letter(len(header_row))}{row_number}",
                "values": [[
                    normalize_sheet_value(value, header_row[index] if index < len(header_row) else None)
                    for index, value in enumerate(row)
                ]],
            }
            for row_number, row in batch
        ]
        with_sheet_retry(
            lambda data=data: sheet.batch_update(data),
            "batch row updates",
            stats,
        )
        time.sleep(1)

    for batch in chunks(staged_appends, batch_size):
        normalized_batch = [
            [
                normalize_sheet_value(value, header_row[index] if index < len(header_row) else None)
                for index, value in enumerate(row)
            ]
            for row in batch
        ]
        with_sheet_retry(
            lambda batch=normalized_batch: sheet.append_rows(batch, value_input_option="USER_ENTERED"),
            "batch row appends",
            stats,
        )
        time.sleep(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sheet-batch-size", type=int, default=25)
    args = parser.parse_args()

    dry_run = args.dry_run
    batch_size = max(1, args.sheet_batch_size)
    pdfs = sorted(SAMPLES_DIR.glob("*.pdf"))
    skipped_duplicate_pdfs = [pdf for pdf in pdfs if is_duplicate_copy_pdf(pdf)]
    pdfs = [pdf for pdf in pdfs if not is_duplicate_copy_pdf(pdf)]

    if not pdfs and not skipped_duplicate_pdfs:
        print("No PDFs found in samples/")
        return

    stats = {
        "processed": len(pdfs),
        "local_successes": 0,
        "failures": 0,
        "rows_appended": 0,
        "rows_updated": 0,
        "left_in_samples": 0,
        "skipped_duplicate_copy_files": len(skipped_duplicate_pdfs),
        "google_sheet_retries": 0,
    }

    sheet, existing = read_or_prepare_sheet(dry_run, stats)
    header_row = existing[0]
    original_existing_count = len(existing)
    staged_updates = {}
    staged_appends = []
    successful_pdfs = []
    summaries = []

    for pdf_path in skipped_duplicate_pdfs:
        summary = property_summary({"source_pdf": str(pdf_path)})
        summary["update_result"] = "skipped duplicate-copy file"
        summaries.append((pdf_path, summary, "SKIPPED", "duplicate-copy filename left in samples/"))
        stats["left_in_samples"] += 1

    for pdf_path in pdfs:
        print(f"Processing: {pdf_path}")
        try:
            ok, summary, message, scored_property = process_pdf_locally(pdf_path)
        except Exception as exc:
            ok = False
            summary = property_summary()
            message = str(exc)
            scored_property = {}

        if ok:
            match_method, update_result = stage_sheet_row(
                scored_property,
                header_row,
                existing,
                original_existing_count,
                staged_appends,
                staged_updates,
            )
            summary["row_match_method"] = match_method
            summary["update_result"] = (
                f"would {update_result}" if dry_run else update_result
            )
            stats["local_successes"] += 1
            successful_pdfs.append(pdf_path)
            summaries.append((pdf_path, summary, "SUCCESS", message))
        else:
            stats["failures"] += 1
            stats["left_in_samples"] += 1
            summaries.append((pdf_path, summary, "FAILURE", message))

    stats["rows_appended"] = len(staged_appends)
    stats["rows_updated"] = len(staged_updates)

    if dry_run:
        stats["left_in_samples"] += len(successful_pdfs)
        sheet_message = "dry run complete; sheet not written and PDFs not moved"
    else:
        try:
            write_sheet_changes(sheet, header_row, staged_updates, staged_appends, batch_size, stats)
            for pdf_path in successful_pdfs:
                move_pdf_to_processed(pdf_path)
            sheet_message = "sheet writes completed and successful PDFs moved to processed/"
        except Exception as exc:
            stats["left_in_samples"] += len(successful_pdfs)
            sheet_message = f"sheet write failed; successful PDFs left in samples/: {exc}"
            for index, (pdf_path, summary, status, message) in enumerate(summaries):
                if status == "SUCCESS":
                    summaries[index] = (pdf_path, summary, "FAILURE", sheet_message)

    for pdf_path, summary, status, message in summaries:
        detail = message
        if status == "SUCCESS":
            detail = sheet_message if message == "local processing complete" else message
        print_property_summary(pdf_path.name, summary, status, detail)
        if status in {"FAILURE", "SKIPPED"}:
            print(f"Left in samples/: {pdf_path}")

    print(
        "Summary: "
        f"PDFs processed: {stats['processed']}, "
        f"rows appended: {stats['rows_appended']}, "
        f"rows updated: {stats['rows_updated']}, "
        f"PDFs left in samples: {stats['left_in_samples']}, "
        f"skipped duplicate-copy files: {stats['skipped_duplicate_copy_files']}, "
        f"Google Sheets API retries: {stats['google_sheet_retries']}"
    )


if __name__ == "__main__":
    main()
