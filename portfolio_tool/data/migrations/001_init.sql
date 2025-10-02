-- Initialize core tables for the portfolio repository.
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dt TEXT NOT NULL,
    type TEXT NOT NULL,
    symbol TEXT NOT NULL,
    qty REAL NOT NULL,
    price REAL NOT NULL,
    fees REAL DEFAULT 0,
    broker_ref TEXT,
    notes TEXT,
    exchange TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_transactions_symbol_dt
    ON transactions(symbol, dt);

CREATE TABLE IF NOT EXISTS lots (
    lot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    acquired_at TEXT NOT NULL,
    qty_remaining REAL NOT NULL,
    cost_base_total REAL NOT NULL,
    threshold_date TEXT,
    source_txn_id INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_lots_symbol_acquired
    ON lots(symbol, acquired_at);

CREATE TABLE IF NOT EXISTS disposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sell_txn_id INTEGER NOT NULL,
    lot_id INTEGER NOT NULL,
    qty REAL NOT NULL,
    proceeds REAL NOT NULL,
    cost_base_alloc REAL NOT NULL,
    gain_loss REAL NOT NULL,
    eligible_for_discount INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_disposals_sell
    ON disposals(sell_txn_id);

CREATE INDEX IF NOT EXISTS idx_disposals_lot
    ON disposals(lot_id);

CREATE TABLE IF NOT EXISTS price_cache (
    symbol TEXT PRIMARY KEY,
    asof TEXT NOT NULL,
    price REAL NOT NULL,
    source TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    stale INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS actionables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    symbol TEXT,
    message TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    snoozed_until TEXT,
    context TEXT
);

CREATE INDEX IF NOT EXISTS idx_actionables_status
    ON actionables(status);

CREATE INDEX IF NOT EXISTS idx_actionables_symbol
    ON actionables(symbol);
