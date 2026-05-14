import json
import re
import sys
import tempfile
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from extract_redfin_pdf import (  # noqa: E402
    extract_address_from_text,
    extract_listing_url,
    extract_text_from_pdf,
    find_redfin_url,
    image_folder_for_pdf,
)
from extract_idx_page import extract_idx_image_urls  # noqa: E402
from enrich_with_idx import download_idx_images  # noqa: E402
from normalize_property import MISSING, normalize_property  # noqa: E402
from rubric import (  # noqa: E402
    calculate_favorite_conversion_rate,
    calculate_rate_per_day,
    classify_dom_status,
    classify_buyer_interest_signal,
    classify_interest_velocity,
    detect_garage,
    extract_field,
    extract_int_field,
    extract_listing_history_1y,
)


FIXTURE_FILE = ROOT / "tests" / "fixtures" / "expected_extraction.json"
REQUIRED_KEYS = {
    "listing_url",
    "source_pdf",
    "image_folder",
    "address",
    "garage",
    "year_built",
    "views",
    "favorites",
    "views_per_day",
    "favorites_per_day",
    "dom_status",
    "interest_velocity",
    "favorite_conversion_rate",
    "buyer_interest_signal",
    "listed_count_1y",
    "listing_removed_count_1y",
    "price_change_count_1y",
    "listed_count_lifetime",
    "listing_removed_count_lifetime",
}


def load_fixtures():
    with open(FIXTURE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_fixture_data(pdf_path):
    text = extract_text_from_pdf(str(pdf_path))
    listing_url = extract_listing_url(str(pdf_path), text)
    address = extract_address_from_text(text)
    listed_count_lifetime = len(re.findall(r"\bListed\b", text, re.IGNORECASE))
    listing_removed_count_lifetime = len(re.findall(r"\bListing Removed\b", text, re.IGNORECASE))

    data = {
        "listing_url": listing_url,
        "source_pdf": str(pdf_path.relative_to(ROOT)),
        "image_folder": image_folder_for_pdf(str(pdf_path.relative_to(ROOT)), listing_url, address),
        "address": address,
        "garage": detect_garage(text),
        "year_built": extract_field(r"Year Built\s+(\d{4})", text),
        "days_on_redfin": extract_field(r"(\d+)\s+days on Redfin", text),
        "views": extract_int_field(
            [
                r"(\d[\d,]*)\s+views?\b",
                r"Viewed\s+(\d[\d,]*)\s+times\b",
                r"\bViews\s+(\d[\d,]*)\b",
            ],
            text,
        ),
        "favorites": extract_int_field(
            [
                r"(\d[\d,]*)\s+favorites?\b",
                r"Favorited\s+(\d[\d,]*)\s+times\b",
                r"\bFavorites\s+(\d[\d,]*)\b",
            ],
            text,
        ),
        "listed_count_lifetime": listed_count_lifetime,
        "listing_removed_count_lifetime": listing_removed_count_lifetime,
    }
    data.update(extract_listing_history_1y(text, today=date(2026, 5, 9)))

    data = normalize_property(data)
    data["dom_status"] = classify_dom_status(data["days_on_redfin"])
    data["views_per_day"] = calculate_rate_per_day(data["views"], data["days_on_redfin"])
    data["favorites_per_day"] = calculate_rate_per_day(data["favorites"], data["days_on_redfin"])
    data["favorite_conversion_rate"] = calculate_favorite_conversion_rate(data["favorites"], data["views"])
    data["interest_velocity"] = classify_interest_velocity(data["views_per_day"])
    data["buyer_interest_signal"] = classify_buyer_interest_signal(data)

    return text, data


def test_no_redfin_url_is_marked_missing():
    assert find_redfin_url(["plain text with no listing URL"]) == MISSING


def test_fixtures_extract_expected_fields():
    for fixture in load_fixtures():
        pdf_path = ROOT / fixture["pdf_filename"]
        expected = fixture["expected"]

        assert pdf_path.exists(), f"Missing fixture PDF: {pdf_path}"

        text, data = extract_fixture_data(pdf_path)

        assert text.strip(), f"No text extracted from {pdf_path}"
        assert REQUIRED_KEYS.issubset(data.keys())
        assert data["address"] == expected["address"]
        assert data["listing_url"] == expected["listing_url"]
        assert data["garage"] == expected["garage"]
        assert data["year_built"] == expected["year_built"]
        assert data["views"] == expected["views"]
        assert data["favorites"] == expected["favorites"]
        assert data["views_per_day"] == expected["views_per_day"]
        assert data["favorites_per_day"] == expected["favorites_per_day"]
        assert data["listed_count_1y"] == expected["listed_count_1y"]
        assert data["listing_removed_count_1y"] == expected["listing_removed_count_1y"]
        assert data["price_change_count_1y"] == expected["price_change_count_1y"]
        assert data["image_folder"] == expected["image_folder"]


def test_garage_is_not_silently_defaulted_to_no():
    missing_garage_fixtures = [
        fixture for fixture in load_fixtures() if fixture["expected"]["garage"] == MISSING
    ]

    assert missing_garage_fixtures, "Expected at least one fixture with missing garage data"

    for fixture in missing_garage_fixtures:
        pdf_path = ROOT / fixture["pdf_filename"]
        _, data = extract_fixture_data(pdf_path)

        assert data["garage"] == MISSING
        assert data["garage"] != "No"


def test_missing_values_are_normalized_to_missing():
    normalized = normalize_property(
        {
            "listing_url": None,
            "source_pdf": "",
            "image_folder": "Unknown",
            "address": "Unspecified",
            "garage": None,
            "views": None,
            "favorites": None,
            "views_per_day": None,
            "favorites_per_day": None,
            "dom_status": None,
            "interest_velocity": None,
            "favorite_conversion_rate": None,
            "buyer_interest_signal": None,
            "listed_count_1y": None,
            "listing_removed_count_1y": None,
            "price_change_count_1y": None,
        }
    )

    assert normalized["listing_url"] == MISSING
    assert normalized["source_pdf"] == MISSING
    assert normalized["image_folder"] == MISSING
    assert normalized["address"] == MISSING
    assert normalized["garage"] == MISSING
    assert normalized["views"] == MISSING
    assert normalized["favorites"] == MISSING
    assert normalized["views_per_day"] == MISSING
    assert normalized["favorites_per_day"] == MISSING
    assert normalized["dom_status"] == MISSING
    assert normalized["interest_velocity"] == MISSING
    assert normalized["favorite_conversion_rate"] == MISSING
    assert normalized["buyer_interest_signal"] == MISSING
    assert normalized["listed_count_1y"] == MISSING
    assert normalized["listing_removed_count_1y"] == MISSING
    assert normalized["price_change_count_1y"] == MISSING


def test_market_interest_rate_calculations():
    assert calculate_rate_per_day(86, "8") == 10.75
    assert calculate_rate_per_day(2, "65") == 0.03
    assert calculate_rate_per_day(5, "0") == 5.0
    assert calculate_rate_per_day(5, "MISSING") == MISSING
    assert calculate_rate_per_day(MISSING, "8") == MISSING


def test_dom_status_interpretation_preserves_missing_raw_dom():
    assert classify_dom_status(MISSING) == "Just Listed"
    assert classify_dom_status("0") == "Just Listed"
    assert classify_dom_status("7") == "Just Listed"
    assert classify_dom_status("8") == "Recent"
    assert classify_dom_status("29") == "Recent"
    assert classify_dom_status("30") == "Aging"
    assert classify_dom_status("59") == "Aging"
    assert classify_dom_status("60") == "Stale"


def test_buyer_interest_interpretation_fields():
    assert calculate_favorite_conversion_rate(4, 86) == 0.05
    assert calculate_favorite_conversion_rate(0, 0) == MISSING
    assert classify_interest_velocity(25) == "High"
    assert classify_interest_velocity(10) == "Moderate"
    assert classify_interest_velocity(9.99) == "Low"
    assert classify_interest_velocity(MISSING) == MISSING

    assert classify_buyer_interest_signal(
        {
            "views_per_day": 30,
            "favorites_per_day": 0.2,
            "favorite_conversion_rate": 0.03,
            "days_on_redfin": "5",
        }
    ) == "High browsing, weak buyer commitment"
    assert classify_buyer_interest_signal(
        {
            "views_per_day": 12,
            "favorites_per_day": 1.2,
            "favorite_conversion_rate": 0.1,
            "days_on_redfin": "5",
        }
    ) == "Strong buyer interest"
    assert classify_buyer_interest_signal(
        {
            "views_per_day": 5,
            "favorites_per_day": 0.1,
            "favorite_conversion_rate": 0.02,
            "days_on_redfin": "45",
        }
    ) == "Low buyer attention"
    assert classify_buyer_interest_signal(
        {
            "views_per_day": 12,
            "favorites_per_day": 0.5,
            "favorite_conversion_rate": 0.1,
            "days_on_redfin": "10",
        }
    ) == "Normal market interest"
    assert classify_buyer_interest_signal(
        {
            "views_per_day": MISSING,
            "favorites_per_day": MISSING,
            "favorite_conversion_rate": MISSING,
            "days_on_redfin": MISSING,
        }
    ) == "Buyer interest unclear"


def test_listing_history_uses_only_recent_dated_events():
    text = "\n".join(
        [
            "May 1, 2026",
            "Listed",
            "$200,000",
            "Jan 1, 2026",
            "Listing Removed",
            "—",
            "Dec 1, 2025",
            "Price Changed",
            "$190,000",
            "Jan 1, 2020",
            "Listed",
            "$100,000",
        ]
    )

    history = extract_listing_history_1y(text, today=date(2026, 5, 9))

    assert history["listed_count_1y"] == 1
    assert history["listing_removed_count_1y"] == 1
    assert history["price_change_count_1y"] == 1


def test_listing_history_missing_when_event_dates_are_unreliable():
    history = extract_listing_history_1y("Listed\n$200,000", today=date(2026, 5, 9))

    assert history["listed_count_1y"] == MISSING
    assert history["listing_removed_count_1y"] == MISSING
    assert history["price_change_count_1y"] == MISSING


def test_scored_output_uses_buyer_leverage_terms():
    import rubric

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        raw_text = "\n".join(
            [
                "May 1, 2026",
                "Listed",
                "$200,000",
                "Jan 1, 2026",
                "Listing Removed",
                "Dec 1, 2025",
                "Price Changed",
                "110 S West Ave Ave, Sioux Falls, SD 57104",
                "Year Built",
                "1922",
                "60 days on Redfin",
                "10 views",
                "2 favorites",
            ]
        )
        input_file = temp_path / "raw_text.txt"
        output_file = temp_path / "scored_property.json"
        input_file.write_text(raw_text, encoding="utf-8")

        original_input = rubric.INPUT_FILE
        original_output = rubric.OUTPUT_FILE
        original_metadata = rubric.METADATA_INPUT_FILE

        try:
            rubric.INPUT_FILE = str(input_file)
            rubric.OUTPUT_FILE = str(output_file)
            rubric.METADATA_INPUT_FILE = str(temp_path / "missing_metadata.json")
            rubric.main()
        finally:
            rubric.INPUT_FILE = original_input
            rubric.OUTPUT_FILE = original_output
            rubric.METADATA_INPUT_FILE = original_metadata

        scored = json.loads(output_file.read_text(encoding="utf-8"))

    assert "buyer_leverage_score" in scored
    assert "buyer_leverage_flags" in scored
    assert all("leverage" not in key or key.startswith("buyer_") for key in scored)
    assert scored["strategy_fit_score"] == MISSING
    assert scored["strategy_fit_flags"] == []


def test_sheet_export_includes_price_refresh_fields():
    from append_to_sheet import build_row, desired_headers

    data = {
        "address": "1105 N Kiwanis Ave Ave, Sioux Falls, SD 57104",
        "price": "199,900",
        "current_price": 199900,
        "price_before_reduction": 229900,
        "price_reduction_date": "2026-04-16T00:00:00",
        "last_checked": "2026-05-13 22:45:00",
        "refresh_success": "TRUE",
    }
    headers = desired_headers(data)
    required = [
        "price_before_reduction",
        "price_reduction_date",
        "price_reduction_amount",
        "price_reduction_pct",
        "last_checked",
        "refresh_success",
    ]

    assert all(header in headers for header in required)

    row = build_row(data, headers)
    values = dict(zip(headers, row))

    assert values["price_before_reduction"] == "$229,900"
    assert values["price_reduction_date"] == "04/16/2026"
    assert values["price_reduction_amount"] == "$30,000"
    assert values["price_reduction_pct"] == "13.0%"
    assert values["last_checked"] == "2026-05-13 22:45:00"
    assert values["refresh_success"] == "TRUE"


def test_refresh_payload_updates_price_refresh_fields_without_blank_overwrite():
    from refresh_idx_data import build_refresh_payload, safe_updates_for_row

    row_data = {
        "address": "1105 N Kiwanis Ave Ave, Sioux Falls, SD 57104",
        "price": "199,900",
        "price_change_count_1y": "1",
        "listed_count_1y": "1",
        "listing_removed_count_1y": "0",
    }
    idx_data = {
        "mls_status": "Active - Active",
        "price": "$199,900",
        "listing_photo_url": "https://zimg.paragon.ice.com/ParagonImages/Property/PI/RASE/22603373/0/home-photo.jpg",
        "sections": {
            "Financial": {
                "Price Before Reduction": "$229,900",
                "Price Reduction Date": "2026-04-16T00:00:00",
            }
        },
        "debug": {"errors": []},
    }

    payload = build_refresh_payload(row_data, idx_data)
    updates = safe_updates_for_row(row_data, payload)

    assert updates["price_before_reduction"] == "$229,900"
    assert updates["price_reduction_date"] == "04/16/2026"
    assert updates["price_reduction_amount"] == "$30,000"
    assert updates["price_reduction_pct"] == "13.0%"
    assert updates["last_checked"]
    assert updates["refresh_success"] == "TRUE"
    assert updates["listing_photo_url"] == "https://zimg.paragon.ice.com/ParagonImages/Property/PI/RASE/22603373/0/home-photo.jpg"

    existing = {"price_before_reduction": "$229,900"}
    blank_updates = safe_updates_for_row(
        existing,
        {
            "last_checked": "2026-05-13 22:45:00",
            "refresh_success": "FALSE",
            "price_before_reduction": "",
        },
    )

    assert "price_before_reduction" not in blank_updates
    assert blank_updates["last_checked"] == "2026-05-13 22:45:00"
    assert blank_updates["refresh_success"] == "FALSE"


def test_sheet_value_normalization_converts_lists_dicts_and_bools():
    from append_to_sheet import build_row, normalize_sheet_value, set_row_values

    headers = ["address", "idx_image_urls", "live_market_interest_flags", "idx_details", "refresh_success"]
    data = {
        "address": "1105 N Kiwanis Ave Ave, Sioux Falls, SD 57104",
        "idx_image_urls": [
            "https://zimg.paragon.ice.com/ParagonImages/Property/PI/RASE/22603373/0/front.JPG",
            "https://zimg.paragon.ice.com/ParagonImages/Property/PI/RASE/22603373/0/kitchen.JPG",
        ],
        "live_market_interest_flags": ["Current DOM unavailable", "Recent price drop"],
        "idx_details": {"status": "Active", "count": 1},
        "refresh_success": True,
    }

    row = build_row(data, headers)
    values = dict(zip(headers, row))

    assert isinstance(values["idx_image_urls"], str)
    assert values["idx_image_urls"].count("zimg.paragon.ice.com") == 2
    assert values["live_market_interest_flags"] == "Current DOM unavailable | Recent price drop"
    assert values["idx_details"] == '{"status": "Active", "count": 1}'
    assert values["refresh_success"] == "TRUE"
    assert normalize_sheet_value(None) == ""

    updated = set_row_values(["", "", "", "", ""], headers, data)
    assert all(not isinstance(value, (list, dict, bool)) for value in updated)


def test_idx_image_url_extraction_accepts_only_zimg_direct_images():
    idx_url = "https://rase-inc.idxbroker.com/idx/details/listing/c239/22603373?printable=1"
    html = f"""
      <html>
        <body>
          <img src="{idx_url}">
          <img src="https://www.redfin.com/photo.jpg">
          <img src="https://zimg.paragon.ice.com/ParagonImages/Property/PI/RASE/22603373/0/photo.JPG">
          <img src="https://zimg.paragon.ice.com/ParagonImages/Property/PI/RASE/22603373/0/photo.webp">
          <img src="https://zimg.paragon.ice.com/ParagonImages/Property/PI/RASE/22603373/0/not-image.pdf">
        </body>
      </html>
    """

    assert extract_idx_image_urls(html) == [
        "https://zimg.paragon.ice.com/ParagonImages/Property/PI/RASE/22603373/0/photo.JPG",
        "https://zimg.paragon.ice.com/ParagonImages/Property/PI/RASE/22603373/0/photo.webp",
    ]


def test_idx_image_download_writes_sequential_manifest_only(monkeypatch, tmp_path):
    class FakeResponse:
        content = b"fake-image-bytes"

        def raise_for_status(self):
            return None

    class FakeSession:
        def get(self, url, headers=None, timeout=None):
            assert "zimg.paragon.ice.com" in url
            return FakeResponse()

    monkeypatch.setattr("enrich_with_idx.requests.Session", lambda: FakeSession())

    enriched = {
        "listing_url": "https://www.redfin.com/SD/Sioux-Falls/example/home/1",
        "idx_url": "https://rase-inc.idxbroker.com/idx/details/listing/c239/22603373?printable=1",
        "mls_number": "22603373",
        "address": "1105 N Kiwanis Ave Ave, Sioux Falls, SD 57104",
        "image_folder": str(tmp_path / "1105-n-kiwanis-ave"),
    }
    idx_data = {
        "idx_image_urls": [
            "https://zimg.paragon.ice.com/ParagonImages/Property/PI/RASE/22603373/0/front.JPG",
            "https://zimg.paragon.ice.com/ParagonImages/Property/PI/RASE/22603373/0/kitchen.webp",
        ]
    }

    download_idx_images(enriched, idx_data)

    image_folder = Path(enriched["image_folder"])
    assert (image_folder / "idx_01.jpg").exists()
    assert (image_folder / "idx_02.webp").exists()

    manifest = json.loads((image_folder / "manifest.json").read_text(encoding="utf-8"))
    assert [image["filename"] for image in manifest["images"]] == ["idx_01.jpg", "idx_02.webp"]
    assert all("zimg.paragon.ice.com" in image["source_url"] for image in manifest["images"])


def test_idx_image_download_empty_list_warns_without_redfin_fallback(tmp_path):
    enriched = {
        "listing_url": "https://www.redfin.com/SD/Sioux-Falls/example/home/1",
        "idx_url": "https://rase-inc.idxbroker.com/idx/details/listing/c239/22603373?printable=1",
        "mls_number": "22603373",
        "address": "1105 N Kiwanis Ave Ave, Sioux Falls, SD 57104",
        "image_folder": str(tmp_path / "1105-n-kiwanis-ave"),
    }

    download_idx_images(enriched, {"idx_image_urls": []})

    manifest = json.loads((Path(enriched["image_folder"]) / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["images"] == []
    assert enriched["listing_photo_url"] == MISSING
    assert any("No zimg.paragon.ice.com" in warning for warning in enriched["idx_enrichment_warnings"])


def test_process_all_pdfs_does_not_call_redfin_pdf_image_extraction():
    process_file = ROOT / "app" / "process_all_pdfs.py"
    source = process_file.read_text(encoding="utf-8")

    assert "app/extract_pdf_images.py" not in source
    assert '("images"' not in source
