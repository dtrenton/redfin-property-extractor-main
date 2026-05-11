"""
Plan for rebuilding the Google Sheet into separate fact, behavior, score,
and review tabs.

This module is intentionally non-destructive for now. It defines the target
worksheet layout and rules without changing append_to_sheet.py or writing to
Google Sheets.
"""

MISSING = "MISSING"

PROPERTY_FACTS_HEADERS = [
    "listing_url",
    "address",
    "price",
    "sq_ft",
    "price_per_sqft",
    "beds",
    "baths",
    "year_built",
    "lot_size",
    "garage",
    "garage_type",
    "basement",
    "flooring",
    "fence",
]

MARKET_BEHAVIOR_HEADERS = [
    "address",
    "listing_url",
    "days_on_redfin",
    "dom_status",
    "listed_count_1y",
    "listing_removed_count_1y",
    "price_change_count_1y",
    "views",
    "favorites",
    "views_per_day",
    "favorites_per_day",
    "interest_velocity",
    "favorite_conversion_rate",
    "buyer_interest_signal",
]

SCORECARD_HEADERS = [
    "listing_url",
    "address",
    "age_risk",
    "garage_requirement",
    "data_completeness",
    "buyer_leverage_score",
    "final_decision",
]

REVIEW_NOTES_HEADERS = [
    "listing_url",
    "address",
    "missing_fields",
    "notes",
    "source_file",
    "image_folder",
    "date_added",
]

TAB_LAYOUT = {
    "Property Facts": PROPERTY_FACTS_HEADERS,
    "Market Behavior": MARKET_BEHAVIOR_HEADERS,
    "Scorecard": SCORECARD_HEADERS,
    "Review Notes": REVIEW_NOTES_HEADERS,
}

EXCLUDED_SUBJECTIVE_COLUMNS = [
    "roof_risk",
    "foundation_risk",
    "water_risk",
    "mechanical_risk",
    "electrical_risk",
    "cosmetic_flip_risk",
]

EXTRACTED_FACT_FIELDS = set(PROPERTY_FACTS_HEADERS + MARKET_BEHAVIOR_HEADERS)

COMPUTED_SCORE_FIELDS = set(SCORECARD_HEADERS) - {"address"}

REVIEW_METADATA_FIELDS = set(REVIEW_NOTES_HEADERS) - {"address"}

REBUILD_RULES = [
    "Separate extracted facts from computed scores.",
    "Do not include subjective inspection-risk columns.",
    "Only include fields that can be extracted from PDF or HTML sources.",
    f"Mark missing values as {MISSING}.",
    "Treat garage as a required condition.",
    "Scorecard values must explain known extracted facts only.",
    "Do not change append_to_sheet.py until the rebuild is explicitly implemented.",
]


def print_plan():
    print("Sheet rebuild plan")
    print("==================")

    for tab_name, headers in TAB_LAYOUT.items():
        print(f"\n{tab_name}")
        print(", ".join(headers))

    print("\nExcluded subjective columns")
    print(", ".join(EXCLUDED_SUBJECTIVE_COLUMNS))

    print("\nRules")
    for rule in REBUILD_RULES:
        print(f"- {rule}")


if __name__ == "__main__":
    print_plan()
