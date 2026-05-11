import json
import hashlib
import re
import sys
from pathlib import Path

import fitz

try:
    from extract_redfin_pdf import MISSING, extract_address_from_text, extract_listing_url, image_folder_for_pdf, listing_id_from_url
except ModuleNotFoundError:
    from app.extract_redfin_pdf import MISSING, extract_address_from_text, extract_listing_url, image_folder_for_pdf, listing_id_from_url


OUTPUT_ROOT = Path("outputs/images")
MIN_WIDTH = 500
MIN_HEIGHT = 350
MIN_FILE_SIZE = 40 * 1024
MIN_ASPECT_RATIO = 1.2
MAX_ASPECT_RATIO = 2.2
WHITE_BACKGROUND_THRESHOLD = 0.85


def image_extension(image):
    ext = image.get("ext") or "bin"
    return re.sub(r"[^A-Za-z0-9]", "", ext).lower() or "bin"


def image_rects(page, xref):
    try:
        return page.get_image_rects(xref)
    except Exception:
        return []


def best_rect(rects):
    if not rects:
        return None
    return max(rects, key=lambda rect: rect.width * rect.height)


def is_top_or_middle_region(page, rect):
    if rect is None:
        return False

    center_y = (rect.y0 + rect.y1) / 2
    return center_y <= page.rect.height * 0.7


def mostly_white_or_transparent(image_bytes):
    try:
        pix = fitz.Pixmap(image_bytes)
    except Exception:
        return False

    if pix.width == 0 or pix.height == 0:
        return False

    sample_step_x = max(pix.width // 25, 1)
    sample_step_y = max(pix.height // 25, 1)
    channels = pix.n
    alpha_index = channels - 1 if pix.alpha else None
    white_or_transparent = 0
    total = 0

    for y in range(0, pix.height, sample_step_y):
        for x in range(0, pix.width, sample_step_x):
            pixel = pix.pixel(x, y)
            total += 1

            if alpha_index is not None and pixel[alpha_index] < 20:
                white_or_transparent += 1
                continue

            red = pixel[0]
            green = pixel[1] if channels > 1 else red
            blue = pixel[2] if channels > 2 else red

            if red > 245 and green > 245 and blue > 245:
                white_or_transparent += 1

    return total > 0 and (white_or_transparent / total) >= WHITE_BACKGROUND_THRESHOLD


def keep_image(image, image_bytes, page, xref):
    width = image.get("width", 0)
    height = image.get("height", 0)
    file_size = len(image_bytes)

    if width < MIN_WIDTH:
        return False, f"width below {MIN_WIDTH}px"
    if height < MIN_HEIGHT:
        return False, f"height below {MIN_HEIGHT}px"
    if file_size < MIN_FILE_SIZE:
        return False, f"file size below {MIN_FILE_SIZE} bytes"

    aspect_ratio = width / height if height else 0
    if aspect_ratio < MIN_ASPECT_RATIO or aspect_ratio > MAX_ASPECT_RATIO:
        return False, f"aspect ratio outside {MIN_ASPECT_RATIO}-{MAX_ASPECT_RATIO}"
    if 0.9 <= aspect_ratio <= 1.1:
        return False, "nearly square image"
    if mostly_white_or_transparent(image_bytes):
        return False, "mostly white or transparent background"

    rect = best_rect(image_rects(page, xref))
    reason_parts = [
        f"{width}x{height}",
        f"{round(file_size / 1024)}KB",
        f"aspect ratio {aspect_ratio:.2f}",
    ]

    if rect is not None:
        reason_parts.append("top/middle page region" if is_top_or_middle_region(page, rect) else "large embedded image")
    else:
        reason_parts.append("large embedded image")

    return True, "; ".join(reason_parts)


def extract_pdf_images(pdf_path):
    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"File not found: {pdf_path}")

    doc = fitz.open(pdf_path)
    text = "".join(page.get_text() for page in doc)
    listing_url = extract_listing_url(str(pdf_path), text)
    listing_id = listing_id_from_url(listing_url)
    address = extract_address_from_text(text)
    output_folder = Path(image_folder_for_pdf(str(pdf_path), listing_url, address))
    output_slug = output_folder.name
    output_folder.mkdir(parents=True, exist_ok=True)

    for existing_image in output_folder.glob("page-*-image-*.*"):
        existing_image.unlink()

    seen_hashes = set()
    images = []
    total_embedded = 0
    skipped_count = 0
    saved_count = 0

    for page_index in range(len(doc)):
        page = doc[page_index]
        for image_index, image_info in enumerate(page.get_images(full=True), start=1):
            total_embedded += 1
            xref = image_info[0]
            image = doc.extract_image(xref)
            image_bytes = image["image"]
            digest = hashlib.sha256(image_bytes).hexdigest()

            if digest in seen_hashes:
                skipped_count += 1
                continue

            seen_hashes.add(digest)
            keep, reason = keep_image(image, image_bytes, page, xref)
            if not keep:
                skipped_count += 1
                continue

            saved_count += 1
            ext = image_extension(image)
            output_path = output_folder / f"page-{page_index + 1:02d}-image-{image_index:02d}-{digest[:10]}.{ext}"

            if not output_path.exists():
                with open(output_path, "wb") as f:
                    f.write(image_bytes)

            images.append(
                {
                    "filename": output_path.name,
                    "width": image.get("width"),
                    "height": image.get("height"),
                    "file_size": len(image_bytes),
                    "page_number": page_index + 1,
                    "reason_kept": reason,
                }
            )

    manifest_path = output_folder / "manifest.json"
    manifest = {
        "listing_url": listing_url,
        "listing_id": listing_id or MISSING,
        "address": address,
        "source_pdf": str(pdf_path),
        "image_folder": str(output_folder),
        "images": images,
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Source PDF: {pdf_path}")
    print(f"Listing ID or fallback slug: {output_slug}")
    print(f"Total embedded images found: {total_embedded}")
    print(f"Images skipped: {skipped_count}")
    print(f"Images saved: {saved_count}")
    print(f"Output folder: {output_folder}")

    return str(output_folder)


def main():
    if len(sys.argv) < 2:
        print('Usage: python3 app/extract_pdf_images.py "samples/example.pdf"')
        return

    extract_pdf_images(sys.argv[1])


if __name__ == "__main__":
    main()
