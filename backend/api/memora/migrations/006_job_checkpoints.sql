-- store.init adds jobs.phase, source_version and result_report_id when absent.
-- source: original job.version; report: committed source_version; complete: report persisted.
-- job.version remains the original request/idempotence key, never overwritten by ASR.
INSERT OR IGNORE INTO schema_version VALUES(6);
