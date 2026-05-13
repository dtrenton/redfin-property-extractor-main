import json
import sys
import fitz
import os
import re

try:
    from normalize_property import MISSING
    from enrich_with_idx import extract_mls_number_from_text, idx_url_for_mls
except ModuleNotFoundError:
    from app.normalize_property import MISSING
    from app.enrich_with_idx import extract_mls_number_from_text, idx_url_for_mls

METADATA_OUTPUT_PATH = "outputs/extraction_metadata.json"
IMAGE_OUTPUT_ROOT = "outputs/images"
REDFIN_URL_PATTERN = re.compile(r"https?://(?:www\.)?redfin\.com/[^\s)<>\"]*/home/\d+", re.IGNORECASE)
def clean_listing_url(url):
    return url.rstrip(".,);]")


def find_redfin_url(values):
    for value in values:
        if not value:
            continue
        match = REDFIN_URL_PATTERN.search(str(value))
        if match:
            return clean_listing_url(match.group(0))
    return MISSING


def safe_slug(value):
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return slug or "unknown-pdf"


def extract_address_from_text(text):
    for line in text.splitlines():
        if "sioux falls, sd" in line.lower() and any(c.isdigit() for c in line):
            return line.split("|")[0].strip()
    return MISSING


def address_folder_slug(address):
    if not address or address == MISSING:
        return None

    street_address = address.split(",")[0]
    words = street_address.split()
    deduped_words = []

    for word in words:
        if deduped_words and deduped_words[-1].lower() == word.lower():
            continue
        deduped_words.append(word)

    return safe_slug(" ".join(deduped_words))


def listing_id_from_url(listing_url):
    if not listing_url or listing_url == MISSING:
        return None

    match = re.search(r"/home/(\d+)", listing_url)
    return match.group(1) if match else None


def image_folder_for_pdf(pdf_path, listing_url, address=None):
    folder_name = address_folder_slug(address) or safe_slug(os.path.splitext(os.path.basename(pdf_path))[0])
    return os.path.join(IMAGE_OUTPUT_ROOT, folder_name)


def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""

    for page in doc:
        text += page.get_text()

    return text


def extract_hyperlink_urls_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    urls = []

    for page in doc:
        for link in page.get_links():
            uri = link.get("uri")
            if uri:
                urls.append(uri)

    return urls


def extract_metadata_values_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    metadata = doc.metadata or {}
    return list(metadata.values())


def extract_listing_url(pdf_path, text):
    return find_redfin_url(
        [text]
        + extract_hyperlink_urls_from_pdf(pdf_path)
        + extract_metadata_values_from_pdf(pdf_path)
    )


def extract_mls_number(text, pdf_path=None):
    values = []
    if pdf_path:
        values.append(os.path.basename(pdf_path))
        values.extend(extract_metadata_values_from_pdf(pdf_path))
    values.append(text)

    for value in values:
        mls_number = extract_mls_number_from_text(value)
        if mls_number:
            return mls_number

    return MISSING

def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_redfin_pdf.py <pdf_path>")
        return

    pdf_path = sys.argv[1]

    if not os.path.exists(pdf_path):
        print(f"File not found: {pdf_path}")
        return

    text = extract_text_from_pdf(pdf_path)
    listing_url = extract_listing_url(pdf_path, text)
    mls_number = extract_mls_number(text, pdf_path)
    idx_url = idx_url_for_mls(mls_number) if mls_number != MISSING else MISSING
    address = extract_address_from_text(text)
    image_folder = image_folder_for_pdf(pdf_path, listing_url, address)

    os.makedirs("outputs", exist_ok=True)

    output_path = "outputs/raw_text.txt"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)

    with open(METADATA_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {
                "listing_url": listing_url,
                "mls_number": mls_number,
                "idx_url": idx_url,
                "source_pdf": pdf_path,
                "image_folder": image_folder,
            },
            f,
            indent=2,
        )

    print(f"Processed: {pdf_path}")
    print(f"Listing URL: {listing_url}")
    print(f"MLS number: {mls_number}")
    print(f"IDX URL: {idx_url}")
    print(f"Image folder: {image_folder}")
    print(f"Characters extracted: {len(text)}")
    print(f"Saved to: {output_path}")
    print(f"Saved metadata to: {METADATA_OUTPUT_PATH}")

if __name__ == "__main__":
    main()
