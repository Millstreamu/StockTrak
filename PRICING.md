# Pricing Providers & Cache

The portfolio tool resolves last-traded prices through the `PriceProvider` protocol defined in `portfolio_tool.core.pricing`. A resilient fallback chain is bundled so a single outage will not block price refreshes.

## Provider order & normalisation

1. **Primary – yfinance** (default) fetches end-of-day closes from Yahoo Finance. Empty responses, HTTP failures and "decrypt" errors are logged and trigger the fallback chain.
2. **Secondary – yahooquery** mirrors Yahoo Finance via the yahooquery client.
3. **Optional – Market Index data API** requests read-only JSON endpoints at `https://data-api.marketindex.com.au/`. Enable explicitly and expect schema changes.
4. **Tertiary – Alpha Vantage** uses the `TIME_SERIES_DAILY_ADJUSTED` endpoint when an API key is configured.

Symbols are normalised automatically for Australian users. When `pricing.normalize_asx_suffix = true` and your `timezone` starts with `Australia/`, an unsuffixed ticker such as `CSL` is transparently retried as `CSL.AX` before moving to the next provider. Quotes are always returned under the original symbol for cache/storage consistency.

> ⚠️ All bundled integrations rely on unofficial/community data feeds. The official ASX market price feed requires licensed vendor access; use that for guaranteed low-latency data.

## Cache behaviour

- Quotes are cached in the `price_cache` table with a configurable TTL. Set `pricing.price_ttl_minutes` (default 15 minutes) to control refresh cadence.
- When a request arrives:
  - If a cached quote is fresh (`ttl_expires_at` in the future) it is returned without hitting the network.
  - If the cache is stale and `offline_mode = false`, the provider chain is queried and the cache is refreshed.
  - If every provider fails or `offline_mode = true`, the most recent cached quote is returned, marked `is_stale = true`, and a warning is logged.
- The `price-refresh` CLI command forces a refresh for specific tickers.

## Configuration

New pricing settings live under the `[pricing]` table in `~/.portfolio_tool/config.toml`:

```toml
[pricing]
provider_primary = "yfinance"
fallbacks = ["yahooquery", "marketindex", "alphavantage"]
price_ttl_minutes = 15
normalize_asx_suffix = true
include_marketindex = false  # opt-in; experimental

[alpha_vantage]
api_key = ""
```

- Set `pricing.provider_primary` to change the first provider in the chain.
- Reorder or trim `pricing.fallbacks` to suit your data sources.
- Flip `pricing.include_marketindex` to `true` to opt-in to the Market Index experiment. The endpoint is undocumented, may change without notice, and should be used at your own risk.
- Provide `alpha_vantage.api_key` to activate the Alpha Vantage fallback. Symbols targeting the ASX are automatically queried as `SYMBOL.AX`.

Any other provider implementing the `PriceProvider` protocol can be registered in `portfolio_tool.providers.fallback_provider.FallbackPriceProvider`.
