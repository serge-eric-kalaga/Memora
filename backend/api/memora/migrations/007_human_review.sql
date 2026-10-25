CREATE TABLE IF NOT EXISTS report_reviews(
 id TEXT PRIMARY KEY, meeting TEXT NOT NULL, report TEXT NOT NULL,
 category TEXT NOT NULL CHECK(category IN ('actions','decisions')),
 item_index INTEGER NOT NULL CHECK(item_index>=0), revision INTEGER NOT NULL CHECK(revision>=1),
 transcript_version INTEGER NOT NULL, author TEXT NOT NULL, editor_name TEXT,
 created REAL NOT NULL, data TEXT NOT NULL,
 UNIQUE(report,category,item_index,revision),
 FOREIGN KEY(meeting) REFERENCES meetings(id) ON DELETE CASCADE,
 FOREIGN KEY(report) REFERENCES reports(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS report_review_history ON report_reviews(report,category,item_index,revision);
CREATE TABLE IF NOT EXISTS transcript_edits(
 meeting TEXT NOT NULL, version INTEGER NOT NULL, kind TEXT NOT NULL,
 author TEXT NOT NULL, editor_name TEXT, created REAL NOT NULL, data TEXT NOT NULL,
 PRIMARY KEY(meeting,version),
 FOREIGN KEY(meeting,version) REFERENCES transcripts(meeting,version) ON DELETE CASCADE
);
INSERT OR IGNORE INTO schema_version VALUES(7);
