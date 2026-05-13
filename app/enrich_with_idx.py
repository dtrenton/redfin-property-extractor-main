import json
import os
import re
import sys
from pathlib import Path

try:
    from extract_idx_page import extract_idx_page
    from normalize_property import MISSING
    from rubric import (
        recalculate_price_per_sqft,
        update_extraction_quality,
        update_final_decision,
        update_market_activity,
        update_property_risk,
        update_strategy_category,
    )
except ModuleNotFoundError:
    from app.extract_idx_page import extract_idx_page
    from app.normalize_property import MISSING
    from app.rubric import (
        recalculate_price_per_sqft,
        update_extraction_quality,
        update_final_decision,
        update_market_activity,
        update_property_risk,
        update_strategy_category,
    )


SCORED_PROPERTY_FILE = Path("outputs/scored_property.json")
EXTRACTION_METADATA_FILE = Path("outputs/extraction_metadata.json")
DEFAULT_IDX_BASE_URL = "https://rase-inc.idxbroker.com/idx/details/listing/c239"
IDX_UNAVAILABLE_WARNING = "IDX printable page not yet available; continuing with Redfin PDF data."
IDX_ONLY_FIELDS = [
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
    "finished_basement_pct",
    "acres",
    "lot_size_square_feet",
    "listing_agent_name",
    "listing_brokerage",
    "listing_agent_email",
    "nar_contact_info",
    "price_before_reduction",
    "price_reduction_date",
    "price_reduction_amount",
    "price_reduction_pct",
]


def load_json(path):
    if not path.exists():
        return {}

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    path.parent.mkdir(exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def extract_mls_number_from_value(value):
    if not value:
        return None

    patterns = [
        r"\bMLS#\s*([A-Za-z0-9-]+)",
        r"Source:\s*REALTOR(?:®|\(R\))?\s+Association[^#]*#\s*([A-Za-z0-9-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, str(value), re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def resolve_mls_number(scored_property, metadata):
    return (
        scored_property.get("mls_number")
        or metadata.get("mls_number")
        or extract_mls_number_from_value(scored_property.get("source_pdf"))
        or extract_mls_number_from_value(metadata.get("source_pdf"))
    )


def idx_url_for_mls(mls_number):
    base_url = os.environ.get("IDX_BASE_URL", DEFAULT_IDX_BASE_URL).rstrip("/")
    return f"{base_url}/{mls_number}?printable=1"


def first_section_value(idx_data, labels):
    for section in idx_data.get("sections", {}).values():
        for label in labels:
            value = section.get(label)
            if value not in (None, ""):
                return value
    return None


def idx_full_baths(idx_data):
    top_level = numeric_value(idx_data.get("full_baths"))
    if top_level is not None:
        return top_level

    value = first_section_value(
        idx_data,
        ["Full Baths", "Bathrooms Full", "# of Bathrooms (Full)", "Full Bathrooms"],
    )
    if value is not None:
        return numeric_value(value)
    return numeric_value(idx_data.get("derived", {}).get("baths"))


def printable_value(value):
    if is_fillable_value(value):
        return None
    if isinstance(value, list):
        text = ", ".join(str(item) for item in value if item not in (None, ""))
        return text or None
    return value


def numeric_value(value):
    if is_fillable_value(value):
        return None
    match = re.search(r"\d+(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?", str(value))
    if not match:
        return None
    parsed = float(match.group(0).replace(",", ""))
    return int(parsed) if parsed.is_integer() else parsed


def format_sqft(value):
    number = numeric_value(value)
    if number is None:
        return None
    return f"{int(number):,}" if float(number).is_integer() else str(number)


def format_numeric(value):
    number = numeric_value(value)
    if number is None:
        return None
    return int(number) if float(number).is_integer() else number


def date_only(value):
    if is_fillable_value(value):
        return None
    match = re.match(r"^(\d{4}-\d{2}-\d{2})", str(value).strip())
    return match.group(1) if match else None


def is_fillable_value(value):
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().upper() in {"", "MISSING", "NONE", "UNKNOWN", "UNSPECIFIED", "N/A"}
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) == 0
    return False


def derive_fence_value(idx_data):
    fencing = first_section_value(idx_data, ["Fencing"])
    if fencing in (None, ""):
        return None

    normalized = str(fencing).strip().lower()
    if normalized in {"none", "no", "n/a"}:
        return "No Fence"
    return "Yes"


def external_section(idx_data):
    return idx_data.get("sections", {}).get("External", {})


def has_explicit_garage_evidence(external):
    garage_type = printable_value(external.get("Garage Type"))
    if garage_type:
        return True

    spaces = printable_value(external.get("# of Garage Spaces") or external.get("Garage Spaces"))
    if spaces:
        match = re.search(r"\d+", str(spaces))
        if match and int(match.group(0)) > 0:
            return True

    dimensions = printable_value(external.get("Garage Dimensions"))
    if dimensions:
        return True

    amenities = printable_value(external.get("Garage Amenities"))
    if amenities:
        normalized = str(amenities).strip().lower()
        future_only_phrases = ["room for garage", "future garage", "garage possible"]
        if normalized not in {"none", "no", "n/a"} and not any(phrase in normalized for phrase in future_only_phrases):
            return True

    return False


def has_garage_check_fields(external):
    garage_fields = [
        "Garage Type",
        "# of Garage Spaces",
        "Garage Spaces",
        "Garage Dimensions",
        "Garage Amenities",
    ]
    return any(field in external for field in garage_fields)


def lot_dimensions_product(value):
    if is_fillable_value(value):
        return None

    parts = [float(part) for part in re.findall(r"\d+(?:\.\d+)?", str(value))]
    if len(parts) < 2:
        return None
    if len(parts) == 2:
        return round(parts[0] * parts[1])
    if len(parts) >= 4:
        return round(((parts[0] + parts[2]) / 2) * ((parts[1] + parts[3]) / 2))
    return None


def close_match(left, right):
    if left is None or right is None:
        return False
    return abs(float(left) - float(right)) <= max(25, float(right) * 0.03)


def idx_living_sqft(idx_data):
    interior = idx_data.get("sections", {}).get("Interior", {})
    living_area = numeric_value(interior.get("Living Area"))
    if living_area:
        return living_area, "IDX Interior Living Area"

    above = numeric_value(interior.get("Above Grade Finished Area"))
    below = numeric_value(interior.get("Below Grade Finished Area"))
    if above is not None and below is not None:
        return above + below, "IDX above grade + below grade finished area"

    derived_sqft = numeric_value(idx_data.get("derived", {}).get("sqft"))
    if derived_sqft:
        return derived_sqft, "IDX derived sqft"

    return None, None


def idx_lot_metrics(idx_data):
    external = external_section(idx_data)
    lot_size_square_feet = numeric_value(first_section_value(idx_data, ["Lot Size Square Feet"]))
    acres = numeric_value(idx_data.get("derived", {}).get("acres"))
    if acres is None:
        acres = numeric_value(first_section_value(idx_data, ["Acres"]))

    dimensions_product = lot_dimensions_product(external.get("Lot Size Dimensions"))
    acreage_sqft = round(acres * 43560) if acres is not None else None

    return lot_size_square_feet, acres, dimensions_product, acreage_sqft


def add_sqft_warning(enriched, warning):
    enriched.setdefault("validation_warnings", [])
    if warning not in enriched["validation_warnings"]:
        enriched["validation_warnings"].append(warning)


def add_idx_warning(enriched, warning):
    enriched.setdefault("idx_enrichment_warnings", [])
    if warning not in enriched["idx_enrichment_warnings"]:
        enriched["idx_enrichment_warnings"].append(warning)


def idx_printable_unavailable(idx_data):
    debug = idx_data.get("debug", {})
    errors = debug.get("errors", [])
    sections = idx_data.get("sections", {})
    missing_required = debug.get("missing_required_sections", [])
    status_code = debug.get("http_status_code")

    if status_code == 404:
        return True
    if any("404 Client Error" in str(error) for error in errors):
        return True
    if not sections and missing_required:
        return True
    return False


def apply_idx_unavailable_fallback(enriched):
    enriched["idx_enrichment_status"] = "unavailable"
    enriched["idx_enriched_fields"] = []
    add_idx_warning(enriched, IDX_UNAVAILABLE_WARNING)

    for field in IDX_ONLY_FIELDS:
        if is_fillable_value(enriched.get(field)):
            enriched[field] = MISSING

    update_extraction_quality(enriched)
    update_property_risk(enriched)
    update_market_activity(enriched)
    update_final_decision(enriched)
    update_strategy_category(enriched)
    return enriched


def apply_sqft_validation(enriched, idx_data):
    idx_sqft, idx_sqft_source = idx_living_sqft(idx_data)
    lot_size_square_feet, acres, dimensions_product, acreage_sqft = idx_lot_metrics(idx_data)

    if lot_size_square_feet is not None:
        enriched["lot_size_square_feet"] = lot_size_square_feet
    if acres is not None:
        enriched["acres"] = acres

    current_sqft = numeric_value(enriched.get("sq_ft"))
    if current_sqft is None:
        if idx_sqft is not None:
            enriched["sq_ft"] = format_sqft(idx_sqft)
            enriched["sq_ft_source"] = idx_sqft_source
            enriched["idx_enriched_fields"].append("sq_ft")
        return

    suspect_matches = [
        label
        for label, lot_value in [
            ("Lot Size Square Feet", lot_size_square_feet),
            ("lot dimensions product", dimensions_product),
            ("acreage conversion", acreage_sqft),
        ]
        if current_sqft > 2000 and close_match(current_sqft, lot_value)
    ]

    if suspect_matches and idx_sqft is not None:
        old_sqft = enriched.get("sq_ft")
        enriched["sq_ft"] = format_sqft(idx_sqft)
        enriched["sq_ft_source"] = idx_sqft_source
        enriched["idx_enriched_fields"].append("sq_ft")
        add_sqft_warning(
            enriched,
            f"Replaced suspect sq_ft {old_sqft} with {format_sqft(idx_sqft)} from {idx_sqft_source}; original matched {', '.join(suspect_matches)}.",
        )
    elif current_sqft > 2000:
        add_sqft_warning(
            enriched,
            f"sq_ft {enriched.get('sq_ft')} exceeds 2000; checked against IDX lot metrics and no replacement was applied.",
        )


def apply_garage_interpretation(enriched, idx_data):
    if not is_fillable_value(enriched.get("garage")):
        return

    external = external_section(idx_data)
    if has_explicit_garage_evidence(external):
        enriched["garage"] = "Yes"
        enriched["idx_enriched_fields"].append("garage")
        return

    if not has_garage_check_fields(external):
        enriched["garage"] = "No"
        enriched["idx_enriched_fields"].append("garage")


def apply_garage_type_interpretation(enriched):
    if str(enriched.get("garage", "")).strip().lower() != "no":
        return

    garage_type = enriched.get("garage_type")
    if is_fillable_value(garage_type) or str(garage_type).strip().lower() in {"no", "none", "no garage"}:
        enriched["garage_type"] = "No Garage"
        if "garage_type" not in enriched["idx_enriched_fields"]:
            enriched["idx_enriched_fields"].append("garage_type")


def idx_basement_field(idx_data):
    return first_section_value(idx_data, ["Basement"])


def interpret_idx_basement(idx_data):
    basement = idx_basement_field(idx_data)
    if basement is None:
        return "No Basement"

    normalized = str(basement).strip().lower()
    if normalized in {"", "none", "no", "n/a", "no basement"}:
        return "No Basement"

    return basement


def apply_basement_interpretation(enriched, idx_data):
    if not is_fillable_value(enriched.get("basement")):
        return

    basement = interpret_idx_basement(idx_data)
    if basement:
        enriched["basement"] = basement
        enriched["idx_enriched_fields"].append("basement")


def idx_fence_field(idx_data):
    return first_section_value(idx_data, ["Fencing", "Fence"])


def interpret_idx_fence(idx_data):
    fence = idx_fence_field(idx_data)
    if fence is None:
        return "No Fence"

    normalized = str(fence).strip().lower()
    if normalized in {"", "none", "no", "n/a", "no fence"}:
        return "No Fence"

    return fence


def apply_fence_interpretation(enriched, idx_data):
    current = enriched.get("fence")
    if not is_fillable_value(current):
        if str(current).strip().lower() in {"no", "none", "no fence"}:
            enriched["fence"] = "No Fence"
        return

    fence = interpret_idx_fence(idx_data)
    if fence:
        enriched["fence"] = fence
        enriched["idx_enriched_fields"].append("fence")


def normalize_listing_status(value):
    if is_fillable_value(value):
        return None

    text = str(value)
    if re.search(r"\b(?:Sold|Closed)\b", text, re.IGNORECASE):
        return "Sold"
    if re.search(r"\b(?:Pending|Under Contract|Contingent)\b", text, re.IGNORECASE):
        return "Pending"
    if re.search(r"\b(?:For Sale|Active)\b", text, re.IGNORECASE):
        return "For Sale"
    return None


def idx_candidate_values(idx_data):
    derived = idx_data.get("derived", {})
    return {
        "listing_status": printable_value(normalize_listing_status(idx_data.get("mls_status"))),
        "baths": printable_value(idx_full_baths(idx_data)),
        "garage_type": printable_value(first_section_value(idx_data, ["Garage Type"])),
        "construction_materials": printable_value(
            first_section_value(idx_data, ["Construction Materials"])
        ),
        "foundation_details": printable_value(
            first_section_value(idx_data, ["Foundation Details"])
        ),
        "roof": printable_value(first_section_value(idx_data, ["Roof"])),
        "sewer": printable_value(first_section_value(idx_data, ["Sewer"])),
        "water_source": printable_value(first_section_value(idx_data, ["Water Source"])),
        "appliances": printable_value(derived.get("appliances")),
        "cooling": printable_value(derived.get("cooling")),
        "heating": printable_value(derived.get("heating")),
        "interior_features": printable_value(derived.get("interior_features")),
        "rooms": idx_data.get("rooms") or None,
        "finished_basement_pct": printable_value(derived.get("finished_basement_pct")),
        "acres": printable_value(derived.get("acres")),
        "lot_size_square_feet": printable_value(
            first_section_value(idx_data, ["Lot Size Square Feet"])
        ),
        "listing_agent_name": printable_value(idx_data.get("listing_agent_name")),
        "listing_brokerage": printable_value(idx_data.get("listing_brokerage")),
        "listing_agent_email": printable_value(idx_data.get("listing_agent_email")),
        "nar_contact_info": printable_value(
            idx_data.get("nar_contact_info") or first_section_value(idx_data, ["NAR Contact Info"])
        ),
        "price_before_reduction": format_numeric(
            first_section_value(idx_data, ["Price Before Reduction"])
        ),
        "price_reduction_date": printable_value(
            first_section_value(idx_data, ["Price Reduction Date"])
        ),
    }


def apply_price_reduction_fields(enriched):
    price_before_reduction = numeric_value(enriched.get("price_before_reduction"))
    current_price = numeric_value(enriched.get("price"))
    reduction_date_only = date_only(enriched.get("price_reduction_date"))

    if reduction_date_only:
        enriched["price_reduction_date_only"] = reduction_date_only

    if price_before_reduction is None or current_price is None:
        return

    reduction_amount = price_before_reduction - current_price
    if reduction_amount <= 0:
        return

    enriched["price_reduction_amount"] = round(reduction_amount, 2)
    enriched["price_reduction_pct"] = round(reduction_amount / price_before_reduction, 4)


def merge_idx_details(scored_property, idx_data, idx_url, mls_number):
    enriched = scored_property.copy()
    enriched["mls_number"] = mls_number or MISSING
    enriched["idx_url"] = idx_url or MISSING
    enriched["idx_enrichment_status"] = "success"
    enriched["idx_enriched_fields"] = []
    enriched["idx_details"] = idx_data

    errors = idx_data.get("debug", {}).get("errors", [])
    if idx_printable_unavailable(idx_data):
        if errors:
            enriched["idx_enrichment_errors"] = errors
        return apply_idx_unavailable_fallback(enriched)

    if errors:
        enriched["idx_enrichment_status"] = "failed"
        enriched["idx_enrichment_errors"] = errors
        return enriched

    for field, idx_value in idx_candidate_values(idx_data).items():
        if idx_value is None:
            continue
        if field in {"baths", "listing_status"} or is_fillable_value(enriched.get(field)):
            enriched[field] = idx_value
            enriched["idx_enriched_fields"].append(field)

    apply_basement_interpretation(enriched, idx_data)
    apply_fence_interpretation(enriched, idx_data)
    apply_price_reduction_fields(enriched)
    apply_sqft_validation(enriched, idx_data)
    recalculate_price_per_sqft(enriched)
    apply_garage_interpretation(enriched, idx_data)
    apply_garage_type_interpretation(enriched)
    update_extraction_quality(enriched)
    update_property_risk(enriched)
    update_market_activity(enriched)
    update_final_decision(enriched)
    update_strategy_category(enriched)

    return enriched


def enrich_scored_property():
    scored_property = load_json(SCORED_PROPERTY_FILE)
    metadata = load_json(EXTRACTION_METADATA_FILE)
    if not scored_property:
        raise FileNotFoundError(f"Missing scored property file: {SCORED_PROPERTY_FILE}")

    mls_number = resolve_mls_number(scored_property, metadata)
    if not mls_number or mls_number == MISSING:
        scored_property["mls_number"] = MISSING
        scored_property["idx_url"] = MISSING
        scored_property["idx_enrichment_status"] = "skipped_missing_mls_number"
        scored_property["idx_enriched_fields"] = []
        save_json(SCORED_PROPERTY_FILE, scored_property)
        print("IDX enrichment skipped: MLS number missing")
        return scored_property

    idx_url = idx_url_for_mls(mls_number)
    idx_data = extract_idx_page(idx_url)
    enriched = merge_idx_details(scored_property, idx_data, idx_url, mls_number)
    save_json(SCORED_PROPERTY_FILE, enriched)

    print(f"IDX MLS number: {mls_number}")
    print(f"IDX URL: {idx_url}")
    print(f"IDX enrichment status: {enriched.get('idx_enrichment_status')}")
    for warning in enriched.get("idx_enrichment_warnings", []):
        print(f"IDX warning: {warning}")
    print(f"IDX enriched fields: {', '.join(enriched.get('idx_enriched_fields', [])) or 'none'}")

    return enriched


def main():
    try:
        enriched = enrich_scored_property()
    except Exception as exc:
        print(f"IDX enrichment failed: {exc}", file=sys.stderr)
        sys.exit(1)

    if enriched.get("idx_enrichment_status") not in {"success", "unavailable"}:
        print(
            f"IDX enrichment failed: {enriched.get('idx_enrichment_status')}",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
