# Pricing Providers & Cache

The portfolio tool resolves last-traded prices through a provider abstraction defined in `portfolio_tool.core.pricing`. Two providers are bundled:

- **Yahoo Finance (yfinance)** – default provider using the community yfinance package.
- **YahooQuery** – optional alternative using the yahooquery client.

> ⚠️ Both integrations call unofficial Yahoo Finance endpoints which may change without notice. The application remains functional offline by falling back to cached values stored in SQLite.

## Cache Behaviour

- Quotes are cached in the `price_cache` table with a configurable TTL (`price_ttl_minutes`, default 15 minutes).
- When a request arrives:
  - If a cached quote is fresh (`ttl_expires_at` in the future), it is returned without a network call.
  - If the cache is stale and `offline_mode = false`, the provider is queried and the cache is refreshed.
  - If the provider fails or `offline_mode = true`, the most recent cached quote is returned and marked `is_stale = true`.
- The `price-refresh` CLI command forces a refresh for specific tickers.

## Switching Providers

Update `~/.portfolio_tool/config.toml` (or use `portfolio config set`) to change provider:

```toml
price_provider = "yahooquery"
```

Any provider implementing the `PriceProvider` protocol can be registered in `portfolio_tool.__main__.py`.
