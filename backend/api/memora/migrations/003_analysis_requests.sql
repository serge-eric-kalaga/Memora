CREATE TABLE IF NOT EXISTS analysis_requests(
  meeting TEXT NOT NULL, request_id TEXT NOT NULL, job TEXT NOT NULL,
  PRIMARY KEY(meeting,request_id),
  FOREIGN KEY(meeting) REFERENCES meetings(id) ON DELETE CASCADE,
  FOREIGN KEY(job) REFERENCES jobs(id) ON DELETE CASCADE
);
INSERT OR IGNORE INTO schema_version VALUES(3);
