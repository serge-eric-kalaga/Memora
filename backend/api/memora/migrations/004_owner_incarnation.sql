-- store.init performs additive ALTER TABLE mail ADD COLUMN owner_uid TEXT when absent.
-- Existing meeting JSON owner_uid and mail owner_uid remain NULL/unset by default.
-- Bind legacy ownership only through the explicit reviewed memora-bind-owners.py tool.
CREATE INDEX IF NOT EXISTS mail_owner_uid ON mail(owner_uid);
INSERT OR IGNORE INTO schema_version VALUES(4);
