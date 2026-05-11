MISSING = "MISSING"

PROPERTY_FIELDS = [
    "listing_url",
    "source_pdf",
    "image_folder",
    "address",
    "listing_status",
    "price",
    "sq_ft",
    "price_per_sqft",
    "beds",
    "baths",
    "year_built",
    "days_on_redfin",
    "dom_status",
    "views",
    "favorites",
    "views_per_day",
    "favorites_per_day",
    "interest_velocity",
    "favorite_conversion_rate",
    "buyer_interest_signal",
    "strategy_category",
    "garage_fit",
    "listed_count_1y",
    "listing_removed_count_1y",
    "price_change_count_1y",
    "garage",
    "garage_type",
    "basement",
    "flooring",
    "fence",
]


def is_missing(value):
    if value is None or value == "":
        return True
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) == 0
    if isinstance(value, str):
        return value.strip().upper() in {
            "",
            "MISSING",
            "NONE",
            "UNKNOWN",
            "UNSPECIFIED",
            "N/A",
            "NO INFO",
            "NOT PROVIDED",
            "DOES NOT APPLY",
            "<6 DAYS",
        }
    return False


def mark_missing(value):
    return MISSING if is_missing(value) else value


def normalize_property(data):
    normalized = data.copy()

    for field in PROPERTY_FIELDS:
        normalized[field] = mark_missing(normalized.get(field))

    return normalized


def has_value(data, field):
    return not is_missing(data.get(field))
