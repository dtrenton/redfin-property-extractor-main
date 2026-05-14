import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup


JSON_OUTPUT = Path("outputs/idx_property_details.json")
TEXT_OUTPUT = Path("outputs/idx_property_details.txt")
ALLOWED_PARAGON_IMAGE_HOSTS = {
    "zimg.paragon.ice.com",
    "cdnparap80.paragonrels.com",
}
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")

REQUIRED_SECTION_HEADINGS = [
    "Primary Features",
    "Location",
    "Interior",
    "External",
    "Financial",
    "Additional",
]
OPTIONAL_SECTION_HEADINGS = ["Zoning Info"]
ALL_SECTION_HEADINGS = REQUIRED_SECTION_HEADINGS + OPTIONAL_SECTION_HEADINGS

KNOWN_LABELS = {
    "# of Bathrooms (Full)",
    "# of Garage Spaces",
    "Above Grade Finished Area",
    "Acres",
    "Additional Property Info",
    "Appliances",
    "Architectural Style",
    "Basement",
    "Basement Finished Sq.Ft.",
    "Basement Finished Sq Ft",
    "Basement Finished SqFt",
    "Basement Level # of Bedrooms",
    "Basement Level Bath Description",
    "Basement Level Bedrooms",
    "Basement Level Number Bedrooms",
    "Basement Unfinished Sq.Ft.",
    "Basement Unfinished Sq Ft",
    "Basement Unfinished SqFt",
    "Bathrooms Full",
    "Bathrooms Half",
    "Bathrooms Total",
    "Bedrooms Total",
    "Below Grade Finished Area",
    "Below Grade Finished Sq.Ft.",
    "Below Grade Finished Sq Ft",
    "Below Grade Finished SqFt",
    "Below Grade Unfinished Area",
    "Below Grade Unfinished Sq.Ft.",
    "Below Grade Unfinished Sq Ft",
    "Below Grade Unfinished SqFt",
    "City",
    "Construction Materials",
    "Cooling",
    "County",
    "Elementary School",
    "Elementary School District",
    "Exterior Features",
    "Fencing",
    "Fireplace Features",
    "Fireplaces Total",
    "Flooring",
    "Foundation Details",
    "Full Baths",
    "Full Bathrooms",
    "Garage Amenities",
    "Garage Dimensions",
    "Garage Spaces",
    "Garage Type",
    "Heating",
    "High School",
    "Interior Features",
    "IDX Include",
    "Inside City Limits",
    "List Price",
    "Listing ID",
    "Living Area",
    "Lot Features",
    "Lot Size Dimensions",
    "Lot Size Square Feet",
    "Lower Level Appx Finished Sq.Ft.",
    "Lvt Date",
    "Main Level Appx Finished Sq.Ft.",
    "Main Level Approx Finished SqFt",
    "Main Level Bath Description",
    "Main Level Bedrooms",
    "Main Level Number Bedrooms",
    "Middle Or Junior School",
    "Mls Status",
    "NAR Contact Info",
    "Other Structures",
    "Parcel Number",
    "Parking Features",
    "Patio And Porch Features",
    "Postal Code",
    "Price Date",
    "Price Before Reduction",
    "Price Reduction Date",
    "Property Sub Type",
    "Property Type",
    "Road Responsibility",
    "Road Surface Type",
    "Roof",
    "Rooms Total",
    "Sewer",
    "State",
    "Tax Annual Amount",
    "Taxes Reflect",
    "Total Finished Sq Ft",
    "Upper Level # of Bedrooms",
    "Upper Level Appx Finished Sq.Ft.",
    "Upper Level Bath Description",
    "Upper Level Bedrooms",
    "Upper Level Number Bedrooms",
    "Water Source",
    "Water Heater",
    "Water Softener",
    "Year Built",
    "Zoning",
}

LIST_FIELDS = {
    "Appliances": "appliances",
    "Cooling": "cooling",
    "Flooring": "flooring",
    "Heating": "heating",
    "Interior Features": "interior_features",
}


def clean_value(value):
    return re.sub(r"\s+", " ", str(value)).strip()


def build_printable_url(url):
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["printable"] = "1"
    return urlunparse(parsed._replace(query=urlencode(query)))


def empty_result(source_url, printable_url):
    return {
        "source_url": source_url,
        "printable_url": printable_url,
        "listing_id": None,
        "sections": {},
        "derived": {},
        "rooms": {},
        "debug": {
            "missing_required_sections": REQUIRED_SECTION_HEADINGS[:],
            "fields_merged_detected": False,
            "derived_values_used": [],
            "printable_url_used": printable_url != source_url,
            "number_conversion_errors": [],
            "errors": [],
            "warnings": [],
            "raw_section_text": {},
        },
    }


def visible_text_from_html(html):
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    text = soup.get_text("\n")
    lines = [clean_value(line) for line in text.splitlines() if clean_value(line)]
    return "\n".join(lines)


def is_section_heading(line):
    return clean_value(line) in ALL_SECTION_HEADINGS


def is_label_like(line):
    line = clean_value(line)
    if not line:
        return False
    if line.rstrip(":") in KNOWN_LABELS:
        return True
    if re.match(r"^.+\s+(Length|Width|Level):?$", line, re.IGNORECASE):
        return True
    return bool(re.match(r"^[A-Z][A-Za-z0-9 #/&().'-]{1,80}:\s*", line))


def is_standalone_label(line):
    label = clean_value(line).rstrip(":")
    if label in KNOWN_LABELS:
        return True
    return bool(re.match(r"^.+\s+(Length|Width|Level)$", label, re.IGNORECASE))


def next_line_value(lines, index):
    next_index = index + 1
    if next_index >= len(lines):
        return "", index + 1

    next_line = clean_value(lines[next_index])
    if is_section_heading(next_line) or is_label_like(next_line):
        return "", index + 1

    return next_line, next_index + 1


def parse_label_value(line):
    if ":" not in line:
        return None, None

    label, value = line.split(":", 1)
    label = clean_value(label)
    value = clean_value(value)
    if not label:
        return None, None
    return label, value


def split_embedded_label_values(line, debug):
    matches = list(re.finditer(r"(?<!\w)([A-Z][A-Za-z0-9 #/&().'-]{1,80}?)\s*:", line))

    if len(matches) <= 1:
        label, value = parse_label_value(line)
        return [(label, value)] if label is not None else []

    debug["fields_merged_detected"] = True
    parsed = []
    for index, match in enumerate(matches):
        label = clean_value(match.group(1))
        value_start = match.end()
        value_end = matches[index + 1].start() if index + 1 < len(matches) else len(line)
        parsed.append((label, clean_value(line[value_start:value_end])))
    return parsed


def parse_section_lines(lines, debug):
    fields = {}
    index = 0

    while index < len(lines):
        line = clean_value(lines[index])
        if not line:
            index += 1
            continue

        if ":" in line:
            label, value = parse_label_value(line)
            if label and value == "" and (is_standalone_label(label) or line.endswith(":")):
                value, index = next_line_value(lines, index)
                fields[label] = value
                continue

            for parsed_label, parsed_value in split_embedded_label_values(line, debug):
                if parsed_label:
                    fields[parsed_label] = parsed_value
            index += 1
            continue

        label = line.rstrip(":")
        if is_standalone_label(label):
            value, index = next_line_value(lines, index)
            fields[label] = value
            continue

        index += 1

    return fields


def parse_sections(text, debug):
    sections = {}
    raw_section_lines = {heading: [] for heading in ALL_SECTION_HEADINGS}
    current_section = None

    for raw_line in text.splitlines():
        line = clean_value(raw_line)
        if is_section_heading(line):
            current_section = line
            continue

        if current_section:
            raw_section_lines[current_section].append(line)

    for heading in ALL_SECTION_HEADINGS:
        lines = raw_section_lines.get(heading, [])
        if lines:
            sections[heading] = parse_section_lines(lines, debug)
            debug["raw_section_text"][heading] = "\n".join(lines)

    debug["missing_required_sections"] = [
        heading for heading in REQUIRED_SECTION_HEADINGS if heading not in sections
    ]
    if not sections:
        debug["errors"].append("No IDX MLS sections were found in the visible page text.")

    return sections


def flatten_sections(sections):
    fields = {}
    for section in sections.values():
        fields.update(section)
    return fields


def first_field(fields, labels):
    for label in labels:
        value = fields.get(label)
        if value not in (None, ""):
            return value
    return None


def first_match(patterns, text):
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return clean_value(match.group(1))
    return None


def number_from_value(value, debug, label):
    if value in (None, ""):
        return None

    text = clean_value(value)
    if text in {"-", "--", "—", "N/A", "None"}:
        return None

    match = re.search(r"-?\d+(?:,\d{3})*(?:\.\d+)?|-?\d+(?:\.\d+)?", text)
    if not match:
        debug["number_conversion_errors"].append(
            {"label": label, "value": text, "reason": "No numeric token found"}
        )
        return None

    numeric = match.group(0).replace(",", "")
    try:
        parsed = float(numeric)
    except ValueError:
        debug["number_conversion_errors"].append(
            {"label": label, "value": text, "reason": "Invalid numeric token"}
        )
        return None

    return int(parsed) if parsed.is_integer() else parsed


def sum_numeric_fields(fields, labels, debug):
    total = 0
    found = False
    for label in labels:
        number = number_from_value(fields.get(label), debug, label)
        if number is not None:
            total += number
            found = True
    return total if found else None


def normalize_list(value):
    if value in (None, ""):
        return []
    pieces = re.split(r"[,;|]\s*", clean_value(value))
    return [piece.strip() for piece in pieces if piece.strip()]


def derive_listing_id(text, url, fields):
    return (
        first_field(fields, ["Listing ID"])
        or first_match(
            [
                r"^\s*Listing ID:\s*([A-Za-z0-9-]+)\s*$",
                r"^\s*MLS(?:#| Number| ID)?:\s*([A-Za-z0-9-]+)\s*$",
                r"/listing/[^/]+/([A-Za-z0-9-]+)",
            ],
            text + "\n" + url,
        )
    )


def extract_full_baths_from_text(text):
    value = first_match(
        [
            r"^\s*Full Baths\s*:\s*(\d+)\s*$",
            r"^\s*Full Baths\s*\n\s*(\d+)\s*$",
            r"^\s*Full Bathrooms\s*:\s*(\d+)\s*$",
            r"^\s*Full Bathrooms\s*\n\s*(\d+)\s*$",
        ],
        text,
    )
    return int(value) if value is not None else None


def extract_listing_agent_from_text(text):
    compact_text = clean_value(text.replace("\n", " "))
    result = {}

    match = re.search(
        r"Listed by:\s*(?P<agent>.+?)\s+from\s+(?P<brokerage>.+?)(?:\s+(?P<phone>(?:\+?1[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4})\b|$)",
        compact_text,
        re.IGNORECASE,
    )
    if match:
        result["listing_agent_name"] = clean_value(match.group("agent"))
        result["listing_brokerage"] = clean_value(match.group("brokerage"))
        if match.group("phone"):
            result["nar_contact_info"] = clean_value(match.group("phone"))

    email_match = re.search(
        r"For additional information contact this agent at:\s*([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})",
        compact_text,
        re.IGNORECASE,
    )
    if email_match:
        result["listing_agent_email"] = clean_value(email_match.group(1).rstrip("."))

    phone_match = re.search(
        r"\bPhone:\s*((?:\+?1[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4})\b",
        compact_text,
        re.IGNORECASE,
    )
    if phone_match and "nar_contact_info" not in result:
        result["nar_contact_info"] = clean_value(phone_match.group(1))

    return result


def derive_beds(fields, debug):
    direct = number_from_value(first_field(fields, ["Bedrooms Total", "Beds"]), debug, "Bedrooms Total")
    if direct is not None:
        return direct

    bedroom_labels = [
        label
        for label in fields
        if "bedroom" in label.lower()
        and "level" in label.lower()
        and not re.search(r"(length|width|comments|description)", label, re.IGNORECASE)
    ]
    derived = sum_numeric_fields(fields, bedroom_labels, debug)
    if derived is not None:
        debug["derived_values_used"].append("beds")
    return derived


def derive_baths(fields, debug):
    full_baths = sum_numeric_fields(
        fields,
        ["Full Baths", "Bathrooms Full", "# of Bathrooms (Full)", "Full Bathrooms"],
        debug,
    )
    if full_baths is not None:
        debug["derived_values_used"].append("baths")
        return full_baths

    return None


def derive_sqft(fields, debug):
    living_area = number_from_value(first_field(fields, ["Living Area"]), debug, "Living Area")
    if living_area is not None:
        return living_area

    above = number_from_value(
        first_field(fields, ["Above Grade Finished Area"]),
        debug,
        "Above Grade Finished Area",
    )
    below = number_from_value(
        first_field(fields, ["Below Grade Finished Area"]),
        debug,
        "Below Grade Finished Area",
    )
    if above is not None and below is not None:
        debug["derived_values_used"].append("sqft")
        return above + below
    if above is not None:
        debug["derived_values_used"].append("sqft")
        return above

    level_total = sum_numeric_fields(
        fields,
        [
            "Main Level Appx Finished Sq.Ft.",
            "Upper Level Appx Finished Sq.Ft.",
            "Lower Level Appx Finished Sq.Ft.",
        ],
        debug,
    )
    if level_total is not None:
        debug["derived_values_used"].append("sqft")
    return level_total


def derive_acres(fields, debug):
    direct = number_from_value(first_field(fields, ["Acres"]), debug, "Acres")
    if direct is not None:
        return direct

    lot_sqft = number_from_value(
        first_field(fields, ["Lot Size Square Feet"]),
        debug,
        "Lot Size Square Feet",
    )
    if lot_sqft is None:
        return None

    debug["derived_values_used"].append("acres")
    return round(lot_sqft / 43560, 4)


def derive_garage(fields, debug):
    spaces = number_from_value(
        first_field(fields, ["# of Garage Spaces", "Garage Spaces"]),
        debug,
        "Garage Spaces",
    )
    garage_type = first_field(fields, ["Garage Type", "Parking Features"])
    if spaces is not None and spaces > 0:
        debug["derived_values_used"].append("garage")
        return "Yes"
    if spaces == 0:
        debug["derived_values_used"].append("garage")
        return "No"
    if garage_type and clean_value(garage_type).lower() not in {"none", "no", "n/a"}:
        debug["derived_values_used"].append("garage")
        return "Yes"
    return None


def derive_finished_basement_pct(fields, debug):
    finished = number_from_value(
        first_field(
            fields,
            [
                "Below Grade Finished Area",
                "Below Grade Finished Sq.Ft.",
                "Below Grade Finished Sq Ft",
                "Below Grade Finished SqFt",
                "Basement Finished Sq.Ft.",
                "Basement Finished Sq Ft",
                "Basement Finished SqFt",
            ],
        ),
        debug,
        "Below Grade Finished Area",
    )
    unfinished = number_from_value(
        first_field(
            fields,
            [
                "Below Grade Unfinished Area",
                "Below Grade Unfinished Sq.Ft.",
                "Below Grade Unfinished Sq Ft",
                "Below Grade Unfinished SqFt",
                "Basement Unfinished Sq.Ft.",
                "Basement Unfinished Sq Ft",
                "Basement Unfinished SqFt",
            ],
        ),
        debug,
        "Below Grade Unfinished Area",
    )

    if finished is None and unfinished is None:
        return None, None
    if finished is None or unfinished is None:
        debug["number_conversion_errors"].append(
            {
                "label": "finished_basement_pct",
                "value": {
                    "finished": finished,
                    "unfinished": unfinished,
                },
                "reason": "Both finished and unfinished basement areas are required for percentage calculation",
            }
        )
        return None, None

    total = finished + unfinished
    if total <= 0:
        return None, None

    debug["derived_values_used"].extend(["finished_basement_pct", "unfinished_basement_pct"])
    return round((finished / total) * 100, 2), round((unfinished / total) * 100, 2)


def derive_main_level_pct(fields, derived_sqft, debug):
    main = number_from_value(
        first_field(fields, ["Main Level Appx Finished Sq.Ft."]),
        debug,
        "Main Level Appx Finished Sq.Ft.",
    )
    if main is None or not derived_sqft:
        return None

    debug["derived_values_used"].append("main_level_pct")
    return round((main / derived_sqft) * 100, 2)


def derive_fireplace_boolean(fields, debug):
    count = number_from_value(first_field(fields, ["Fireplaces Total"]), debug, "Fireplaces Total")
    if count is not None:
        debug["derived_values_used"].append("fireplace_boolean")
        return count > 0

    features = first_field(fields, ["Fireplace Features"])
    if features is None:
        return None

    text = clean_value(features).lower()
    debug["derived_values_used"].append("fireplace_boolean")
    return text not in {"none", "no", "n/a"}


def room_key(name):
    key = re.sub(r"[^A-Za-z0-9]+", "_", name.strip().lower()).strip("_")
    return key or "room"


def derive_rooms(fields, debug):
    room_parts = {}

    for label, value in fields.items():
        match = re.match(r"(.+?)\s+(Length|Width|Level)$", label, re.IGNORECASE)
        if not match:
            continue

        room = room_key(match.group(1))
        metric = match.group(2).lower()
        room_parts.setdefault(room, {})[metric] = value

    rooms = {}
    for room, values in room_parts.items():
        if not all(key in values for key in ["length", "width", "level"]):
            continue

        length = number_from_value(values["length"], debug, room + " length")
        width = number_from_value(values["width"], debug, room + " width")
        if length is None or width is None:
            continue

        rooms[room] = {
            "length": length,
            "width": width,
            "area_sqft": length * width,
            "level": clean_value(values["level"]),
        }

    if rooms:
        debug["derived_values_used"].append("rooms")
    return rooms


def derive_normalized_fields(fields, debug, full_baths=None):
    derived = {
        "beds": derive_beds(fields, debug),
        "baths": full_baths if full_baths is not None else derive_baths(fields, debug),
        "sqft": None,
        "acres": derive_acres(fields, debug),
        "year_built": number_from_value(first_field(fields, ["Year Built"]), debug, "Year Built"),
        "basement": first_field(fields, ["Basement"]),
        "garage": derive_garage(fields, debug),
    }

    derived["sqft"] = derive_sqft(fields, debug)

    for source_label, output_label in LIST_FIELDS.items():
        derived[output_label] = normalize_list(first_field(fields, [source_label]))

    finished_pct, unfinished_pct = derive_finished_basement_pct(fields, debug)
    derived["finished_basement_pct"] = finished_pct
    derived["unfinished_basement_pct"] = unfinished_pct
    derived["main_level_pct"] = derive_main_level_pct(fields, derived["sqft"], debug)
    derived["fireplace_boolean"] = derive_fireplace_boolean(fields, debug)

    debug["derived_values_used"] = sorted(set(debug["derived_values_used"]))
    return derived


def extract_top_level_fields(text, fields):
    top_level = {
        "address": first_match(
            [
                r"^\s*Address:\s*(.+)$",
                r"^\s*Property Address:\s*(.+)$",
                r"^\s*([0-9]{2,6}\s+[^\n]+,\s*[A-Za-z ]+,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?)\s*$",
            ],
            text,
        ),
        "price": first_field(fields, ["List Price", "Price"])
        or first_match(
            [
                r"^\s*Price:\s*(\$[\d,]+(?:\.\d{2})?)\s*$",
                r"^\s*List Price:\s*(\$[\d,]+(?:\.\d{2})?)\s*$",
                r"^\s*(\$[\d,]+(?:\.\d{2})?)\s*$",
            ],
            text,
        ),
        "full_baths": extract_full_baths_from_text(text),
        "mls_status": first_field(fields, ["Mls Status"]),
    }
    top_level.update(extract_listing_agent_from_text(text))
    return top_level


def save_outputs(data, text):
    Path("outputs").mkdir(exist_ok=True)
    JSON_OUTPUT.write_text(json.dumps(data, indent=2), encoding="utf-8")
    TEXT_OUTPUT.write_text(text, encoding="utf-8")


def fetch_printable_html(printable_url, result):
    try:
        response = requests.get(
            printable_url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; redfin-property-extractor/1.0)",
            },
            timeout=30,
        )
        result["debug"]["http_status_code"] = response.status_code
        response.raise_for_status()
        return response.text
    except requests.RequestException as exc:
        result["debug"]["errors"].append(f"Failed to load printable IDX page: {exc}")
        return None


def normalize_idx_image_url(value):
    url = str(value or "").strip().rstrip(".,);]")
    if url.startswith("//"):
        url = f"https:{url}"
    if not url.lower().startswith("https://"):
        return None

    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if hostname not in ALLOWED_PARAGON_IMAGE_HOSTS:
        return None
    if not parsed.path.lower().endswith(IMAGE_EXTENSIONS):
        return None
    return url


def extract_idx_image_urls(html):
    pattern = re.compile(
        r"(?:https:)?//(?:zimg\.paragon\.ice\.com|cdnparap80\.paragonrels\.com)/[^\s\"'<>\\)]+?\.(?:jpe?g|png|webp)",
        re.IGNORECASE,
    )
    urls = []
    seen = set()
    for match in pattern.finditer(html or ""):
        url = normalize_idx_image_url(match.group(0))
        if not url:
            continue
        if url not in seen:
            urls.append(url)
            seen.add(url)
    return urls


def extract_idx_page(url):
    printable_url = build_printable_url(url)
    result = empty_result(url, printable_url)
    html = fetch_printable_html(printable_url, result)

    if not html:
        save_outputs(result, "")
        print(json.dumps(result, indent=2))
        print(f"Saved JSON to: {JSON_OUTPUT}")
        print(f"Saved text to: {TEXT_OUTPUT}")
        return result

    text = visible_text_from_html(html)
    sections = parse_sections(text, result["debug"])
    if result["debug"]["missing_required_sections"]:
        result["debug"]["warnings"].append(
            "Printable IDX page loaded, but one or more required MLS sections were missing."
        )

    fields = flatten_sections(sections)
    result["sections"] = sections
    result["listing_id"] = derive_listing_id(text, printable_url, fields)
    result["idx_image_urls"] = extract_idx_image_urls(html)
    result["listing_photo_url"] = result["idx_image_urls"][0] if result["idx_image_urls"] else None
    if not result["idx_image_urls"]:
        result["debug"]["warnings"].append("No allowed Paragon IDX image URLs found.")
    result.update(extract_top_level_fields(text, fields))
    result["derived"] = derive_normalized_fields(fields, result["debug"], result.get("full_baths"))
    result["rooms"] = derive_rooms(fields, result["debug"])

    save_outputs(result, text)
    print(json.dumps(result, indent=2))
    print(f"Saved JSON to: {JSON_OUTPUT}")
    print(f"Saved text to: {TEXT_OUTPUT}")

    return result


def main():
    if len(sys.argv) < 2:
        print('Usage: python3 app/extract_idx_page.py "https://rase-inc.idxbroker.com/idx/details/listing/c239/22601472"')
        return

    extract_idx_page(sys.argv[1])


if __name__ == "__main__":
    main()
