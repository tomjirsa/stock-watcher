# yfinance DataService Swap — Design Spec

**Date:** 2026-05-16
**Status:** Approved

---

## Problem

The project currently uses Polygon.io as its data provider via `polygon-api-client`. The free Polygon tier enforces a hard rate limit (~5 requests/minute), which causes the scanner to fail with 429 errors for most of the 19-ticker watchlist. Fundamentals never load successfully on the free tier, so `FundamentalStrategy` never fires. The workaround (15-second delays between tickers) makes a full scan take ~5 minutes and still fails on fundamentals.

---

## Goal

Replace the Polygon.io data source with yfinance — a free, no-API-key library that scrapes Yahoo Finance. The change is contained to `DataService`. All other files (strategies, scanner, backtester, Streamlit app) remain unchanged.

---

## Scope

### In scope
- Rewrite `src/data_service.py` to use yfinance
- Remove `api_key` parameter from `DataService.__init__`
- Update `scanner.py` and `backtester.py` `__main__` blocks to stop loading `POLYGON_API_KEY`
- Update `requirements.txt`: remove `polygon-api-client`, add `yfinance`
- Update `tests/test_data_service.py` to mock yfinance instead of RESTClient
- Update `.env.example` and `.github/workflows/scan.yml` to remove `POLYGON_API_KEY`
- Remove the 15-second `request_delay` from `Scanner` (no longer needed)

### Out of scope
- Changes to `FundamentalStrategy`, `MomentumStrategy`, `Scanner`, `Backtester`, `app/main.py`
- P/E scoring improvements (deferred — `sector_median_pe` stays `None`)
- PEG ratio signal (deferred to a future iteration)
- Auto-trading integration

---

## Architecture

`DataService` is a single-responsibility class that abstracts the data source behind a stable interface. Callers (`Scanner`, `Backtester`) only use two methods and are unaware of the provider.

```
Scanner / Backtester
      │
      ▼
 DataService          ← only file that changes
  ├─ get_price_history(ticker, from_date, to_date) → pd.DataFrame
  └─ get_fundamentals(ticker) → dict
      │
      ▼
  yfinance (replaces polygon-api-client)
  + disk cache (unchanged)
```

---

## Data Mapping

### `get_price_history(ticker, from_date, to_date) → pd.DataFrame`

**yfinance call:** `yf.download(ticker, start=from_date, end=to_date, auto_adjust=True, progress=False)`

Returns a DataFrame with columns renamed to lowercase: `open`, `high`, `low`, `close`, `volume`. The DatetimeIndex is converted to `YYYY-MM-DD` strings to match the format strategies expect.

**Note on `auto_adjust=True`:** prices are adjusted for stock splits and dividends. This is an improvement over the previous Polygon implementation (which used unadjusted prices) — adjusted prices produce more accurate moving averages across split events.

**Edge case:** if `yf.download()` returns an empty DataFrame (unknown ticker, no data in range), raise `ValueError("{ticker}: no price data returned")`. Scanner/Backtester catch this, log a warning, and skip the ticker — same behavior as today.

### `get_fundamentals(ticker) → dict`

**yfinance call:** `yf.Ticker(ticker).info`

| Output field | yfinance source | Notes |
|---|---|---|
| `eps` | `info.get('trailingEps')` | Trailing 12-month EPS in USD |
| `revenue` | `info.get('totalRevenue')` | Annual revenue in USD |
| `eps_growth` | `info.get('earningsGrowth')` | YoY growth, e.g. `0.20` = 20% |
| `revenue_growth` | `info.get('revenueGrowth')` | YoY growth, e.g. `0.15` = 15% |
| `pe_ratio` | `info.get('trailingPE')` | TTM P/E; `None` if earnings negative |
| `sector_median_pe` | `None` (hardcoded) | P/E condition stays dormant |

**Edge case:** wrap entire `Ticker.info` access in try/except. On any failure (network error, bad ticker, malformed response), log a warning and return `{}`. `FundamentalStrategy` treats `{}` as no signal — same behavior as today.

---

## Caching

The existing disk cache is unchanged:
- MD5-keyed JSON files in `data/cache/`
- 24-hour freshness window
- On cache hit, yfinance is not called
- On re-run the same day, all data served from cache instantly

---

## Error Handling

| Scenario | Behavior |
|---|---|
| `yf.download()` returns empty DataFrame | Raise `ValueError`, Scanner skips ticker with warning |
| `Ticker.info` raises any exception | Return `{}`, FundamentalStrategy returns `None` |
| Cache hit | Return cached data, no yfinance call |
| Network timeout | Propagates as exception, Scanner skips ticker |

---

## Testing

`tests/test_data_service.py` — same 4 tests, updated mocks:

| Test | What it verifies |
|---|---|
| `test_get_price_history_returns_dataframe` | `yf.download` mock returns correct DataFrame shape and columns |
| `test_get_price_history_uses_cache_on_second_call` | `yf.download` called only once on two identical requests |
| `test_get_fundamentals_returns_dict` | `Ticker.info` mock returns dict with `eps` and `revenue` keys |
| `test_get_fundamentals_returns_empty_dict_on_api_error` | `Ticker.info` raises exception → returns `{}` |

All other test files (`test_models.py`, `test_momentum.py`, `test_fundamental.py`, `test_scanner.py`, `test_backtester.py`) are unchanged.

---

## Files Changed

| File | Change |
|---|---|
| `src/data_service.py` | Full rewrite — yfinance replaces polygon |
| `src/scanner.py` | Remove `request_delay`, remove `POLYGON_API_KEY` from `__main__` |
| `src/backtester.py` | Remove `POLYGON_API_KEY` from `__main__` |
| `requirements.txt` | `polygon-api-client` → `yfinance` |
| `tests/test_data_service.py` | Update mocks |
| `.env.example` | Remove `POLYGON_API_KEY` |
| `.github/workflows/scan.yml` | Remove `POLYGON_API_KEY` secret reference |

---

## What Improves

- All 19 watchlist tickers processed without rate limiting
- `FundamentalStrategy` fires for the first time (EPS growth + revenue growth now available)
- No API key required — scanner works out of the box
- Full scan completes in seconds instead of ~5 minutes

## What Stays the Same

- `DataService` interface (callers unchanged)
- Disk cache mechanism
- All strategy logic and scoring
- P/E condition (stays dormant — `sector_median_pe` is `None`)
- 23 tests all pass
