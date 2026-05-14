# redfin-property-extractor
Home Buying Comparison Workflow

## Two-Stage Property Monitoring Architecture

This project uses a two-stage workflow for residential property monitoring.

### Stage 1: Redfin PDF Ingestion

The PDF ingestion workflow processes exported Redfin listing PDFs and creates a baseline property record.

During ingestion, the system:

- extracts property facts and metrics from Redfin PDFs
- captures Redfin snapshot traffic metrics
- extracts MLS numbers from PDF headers and filenames
- constructs persistent IDX URLs
- computes initial scoring and leverage metrics
- writes structured property rows into Google Sheets

Snapshot-only Redfin metrics include:

- views
- favorites
- views_per_day
- favorites_per_day
- favorite_conversion_rate
- interest_velocity

These metrics represent listing engagement at the time the PDF was captured and are not refreshed later.

### Stage 2: Live IDX Refresh

The IDX refresh workflow uses stored IDX URLs to monitor live market changes without rescanning PDFs or relying on Redfin.

During refresh, the system:

- checks current listing status
- refreshes days on market (DOM)
- refreshes current price
- detects price drops
- detects pending and sold transitions
- updates leverage and market-interest signals
- refreshes listing facts when available

Live refresh fields include:

- current_status
- current_dom
- current_price
- last_checked
- refresh_success
- refresh_notes

## Common Commands

### Process New Redfin PDFs

```bash
python3 app/process_all_pdfs.py --sheet-batch-size 25
```

### Preview IDX Refresh

```bash
python3 app/refresh_idx_data.py --dry-run
```

### Apply IDX Refresh

```bash
python3 app/refresh_idx_data.py
```

## Testing

Run extraction regression tests with:

```bash
pytest tests/
```

The tests use local PDF fixtures and expected extracted fields. They do not require internet access.

## Market Interest Signals

Redfin traffic fields are static PDF snapshot fields:

- `views`
- `favorites`
- `views_per_day`
- `favorites_per_day`
- `favorite_conversion_rate`
- `interest_velocity`

The project does not attempt to refresh Redfin views or favorites. Redfin blocks automated access, and MLS/IDX data does not provide Redfin traffic metrics.

Refreshable live market interest comes from IDX/MLS-supported listing data when available, including:

- `current_status`
- `current_dom`
- `current_price`
- price drops and price-change counts
- listing/removal activity
- back-on-market and pending-speed signals

Use `redfin_snapshot_interest_score` for initial traffic context and `live_market_interest_score` / `live_market_interest_flags` for current market action

