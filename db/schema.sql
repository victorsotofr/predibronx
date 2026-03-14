-- PrediBronx schema

CREATE TABLE IF NOT EXISTS markets (
    id            TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    description   TEXT,
    end_date      TEXT NOT NULL,       -- ISO-8601 date
    category      TEXT,
    volume        REAL DEFAULT 0,
    liquidity     REAL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS decisions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id       TEXT NOT NULL REFERENCES markets(id),
    run_date        TEXT NOT NULL,      -- ISO-8601 date
    estimated_prob  REAL NOT NULL,      -- 0.0–1.0
    market_price    REAL NOT NULL,      -- YES price at decision time
    bet_direction   TEXT NOT NULL CHECK (bet_direction IN ('YES', 'NO')),
    bet_fraction    REAL NOT NULL,      -- 0.0–1.0, fraction of per-market budget
    confidence      INTEGER NOT NULL CHECK (confidence BETWEEN 0 AND 10),
    rationale       TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS outcomes (
    market_id    TEXT PRIMARY KEY REFERENCES markets(id),
    resolved_yes INTEGER,              -- 1 = YES, 0 = NO, NULL = unresolved
    resolved_at  TEXT                   -- ISO-8601 datetime
);

CREATE TABLE IF NOT EXISTS performance (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date          TEXT NOT NULL,
    brier_score       REAL,
    return_pct        REAL,
    cumulative_return REAL,
    num_decisions     INTEGER DEFAULT 0,
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_decisions_market   ON decisions(market_id);
CREATE INDEX IF NOT EXISTS idx_decisions_run_date ON decisions(run_date);
CREATE INDEX IF NOT EXISTS idx_performance_date   ON performance(run_date);
