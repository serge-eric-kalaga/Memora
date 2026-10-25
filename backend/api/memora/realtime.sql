-- Transport only: no content, tokens or passwords in PostgreSQL notifications.
-- NOTIFY is delivered only after the transaction commits. Reconnection always
-- reloads current authorized data; notifications are not the source of truth.
CREATE OR REPLACE FUNCTION memora.notify_change() RETURNS trigger AS $$
DECLARE
    item jsonb;
    mid text;
    owner_uid text;
BEGIN
    IF TG_OP = 'UPDATE' AND NEW IS NOT DISTINCT FROM OLD THEN RETURN NEW; END IF;
    IF TG_OP = 'DELETE' THEN item := to_jsonb(OLD); ELSE item := to_jsonb(NEW); END IF;
    IF TG_TABLE_NAME = 'meetings' THEN
        mid := item->>'id';
        owner_uid := (item->>'data')::jsonb->>'owner_uid';
    ELSE
        mid := item->>'meeting';
        owner_uid := item->>'owner_uid';
        IF owner_uid IS NULL AND mid IS NOT NULL THEN
            SELECT data::jsonb->>'owner_uid' INTO owner_uid FROM memora.meetings WHERE id = mid;
        END IF;
    END IF;
    IF mid IS NOT NULL THEN
        PERFORM pg_notify('memora_m_' || md5(mid), 'refresh');
    END IF;
    IF owner_uid IS NOT NULL THEN
        PERFORM pg_notify('memora_u_' || md5(owner_uid), 'refresh');
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS memora_changed ON memora.meetings;
CREATE TRIGGER memora_changed AFTER INSERT OR UPDATE OR DELETE ON memora.meetings
FOR EACH ROW EXECUTE FUNCTION memora.notify_change();

DROP TRIGGER IF EXISTS memora_changed ON memora.transcripts;
CREATE TRIGGER memora_changed AFTER INSERT OR UPDATE OR DELETE ON memora.transcripts
FOR EACH ROW EXECUTE FUNCTION memora.notify_change();

DROP TRIGGER IF EXISTS memora_changed ON memora.reports;
CREATE TRIGGER memora_changed AFTER INSERT OR UPDATE OR DELETE ON memora.reports
FOR EACH ROW EXECUTE FUNCTION memora.notify_change();

DROP TRIGGER IF EXISTS memora_changed ON memora.jobs;
CREATE TRIGGER memora_changed AFTER INSERT OR UPDATE OR DELETE ON memora.jobs
FOR EACH ROW EXECUTE FUNCTION memora.notify_change();

DROP TRIGGER IF EXISTS memora_changed ON memora.shares;
CREATE TRIGGER memora_changed AFTER INSERT OR UPDATE OR DELETE ON memora.shares
FOR EACH ROW EXECUTE FUNCTION memora.notify_change();

DROP TRIGGER IF EXISTS memora_changed ON memora.chunks;
CREATE TRIGGER memora_changed AFTER INSERT OR UPDATE OR DELETE ON memora.chunks
FOR EACH ROW EXECUTE FUNCTION memora.notify_change();

DROP TRIGGER IF EXISTS memora_changed ON memora.chats;
CREATE TRIGGER memora_changed AFTER INSERT OR UPDATE OR DELETE ON memora.chats
FOR EACH ROW EXECUTE FUNCTION memora.notify_change();

DROP TRIGGER IF EXISTS memora_changed ON memora.notifications;
CREATE TRIGGER memora_changed AFTER INSERT OR UPDATE OR DELETE ON memora.notifications
FOR EACH ROW EXECUTE FUNCTION memora.notify_change();

DROP TRIGGER IF EXISTS memora_changed ON memora.mail;
CREATE TRIGGER memora_changed AFTER INSERT OR UPDATE OR DELETE ON memora.mail
FOR EACH ROW EXECUTE FUNCTION memora.notify_change();

DROP TRIGGER IF EXISTS memora_changed ON memora.report_reviews;
CREATE TRIGGER memora_changed AFTER INSERT OR UPDATE OR DELETE ON memora.report_reviews
FOR EACH ROW EXECUTE FUNCTION memora.notify_change();

DROP TRIGGER IF EXISTS memora_changed ON memora.transcript_edits;
CREATE TRIGGER memora_changed AFTER INSERT OR UPDATE OR DELETE ON memora.transcript_edits
FOR EACH ROW EXECUTE FUNCTION memora.notify_change();

DROP TRIGGER IF EXISTS memora_changed ON memora.account_tombstones;
CREATE TRIGGER memora_changed AFTER INSERT OR UPDATE OR DELETE ON memora.account_tombstones
FOR EACH ROW EXECUTE FUNCTION memora.notify_change();
