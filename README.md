# redfin-property-extractor
Home Buying Comparison Workflow

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

Use `redfin_snapshot_interest_score` for initial traffic context and `live_market_interest_score` / `live_market_interest_flags` for current market action.
