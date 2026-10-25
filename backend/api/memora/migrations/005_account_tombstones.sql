-- Durable security barrier before cross-store account cleanup. Never remove on ID reuse.
CREATE TABLE IF NOT EXISTS account_tombstones(owner_uid TEXT PRIMARY KEY, deleted_at REAL NOT NULL);
INSERT OR IGNORE INTO schema_version VALUES(5);
