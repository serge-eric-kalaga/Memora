CREATE TABLE IF NOT EXISTS config_history(
  id TEXT PRIMARY KEY, actor TEXT NOT NULL, old_data TEXT NOT NULL,
  new_data TEXT NOT NULL, created REAL NOT NULL
);
INSERT OR IGNORE INTO schema_version VALUES(2);
