import json
import shutil
import subprocess
import sys
from pathlib import Path


SAMPLES_DIR = Path("samples")
PROCESSED_DIR = Path("processed")
SCORED_PROPERTY_FILE = Path("outputs/scored_property.json")
EXTRACTION_METADATA_FILE = Path("outputs/extraction_metadata.json")
MISSING = "MISSING"


def run_step(command):
    return subprocess.run(command, capture_output=True, text=True)


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


def append_summary_from_output(output):
    summary = {}
    for line in output.splitlines():
        if line.startswith("ROW_MATCH_METHOD:"):
            summary["row_match_method"] = line.split(":", 1)[1].strip() or MISSING
        elif line.startswith("UPDATE_RESULT:"):
            summary["update_result"] = line.split(":", 1)[1].strip() or MISSING
    return summary


def process_pdf(pdf_path, dry_run=False):
    append_command = [sys.executable, "app/append_to_sheet.py"]
    if dry_run:
        append_command.append("--dry-run")

    steps = [
        ("extract", [sys.executable, "app/extract_redfin_pdf.py", str(pdf_path)]),
        ("images", [sys.executable, "app/extract_pdf_images.py", str(pdf_path)]),
        ("score", [sys.executable, "app/rubric.py"]),
        ("idx_enrich", [sys.executable, "app/enrich_with_idx.py"]),
        ("append", append_command),
    ]

    summary = property_summary()

    for step_name, command in steps:
        result = run_step(command)

        if step_name == "extract":
            summary.update(property_summary(load_json(EXTRACTION_METADATA_FILE)))
        elif step_name in {"score", "idx_enrich"}:
            summary.update(property_summary(load_json(SCORED_PROPERTY_FILE)))
        elif step_name == "append":
            summary.update(append_summary_from_output(result.stdout))

        if result.returncode != 0:
            error = result.stderr.strip() or result.stdout.strip()
            return False, summary, f"{step_name} failed: {error}"

    if dry_run:
        return True, summary, "dry run complete; sheet not written and PDF not moved"

    PROCESSED_DIR.mkdir(exist_ok=True)
    destination = unique_destination(PROCESSED_DIR / pdf_path.name)
    shutil.move(str(pdf_path), str(destination))

    return True, summary, f"appended to sheet and moved to {destination}"


def main():
    dry_run = "--dry-run" in sys.argv
    pdfs = sorted(SAMPLES_DIR.glob("*.pdf"))

    if not pdfs:
        print("No PDFs found in samples/")
        return

    successes = 0
    failures = 0

    for pdf_path in pdfs:
        print(f"Processing: {pdf_path}")
        try:
            ok, summary, message = process_pdf(pdf_path, dry_run=dry_run)
        except Exception as exc:
            ok = False
            summary = property_summary()
            message = str(exc)

        if ok:
            successes += 1
            print_property_summary(pdf_path.name, summary, "SUCCESS", message)
        else:
            failures += 1
            print_property_summary(pdf_path.name, summary, "FAILURE", message)
            print(f"Left in samples/: {pdf_path}")

    print(f"Summary: {successes} succeeded, {failures} failed")


if __name__ == "__main__":
    main()
