PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY);
        INSERT OR IGNORE INTO schema_version VALUES(1);
        CREATE TABLE IF NOT EXISTS meetings(id TEXT PRIMARY KEY, owner INTEGER NOT NULL, data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS transcripts(meeting TEXT, version INTEGER, data TEXT NOT NULL,
          author TEXT, created REAL, PRIMARY KEY(meeting,version), FOREIGN KEY(meeting) REFERENCES meetings(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS reports(id TEXT PRIMARY KEY, meeting TEXT, version INTEGER, data TEXT,
          created REAL, FOREIGN KEY(meeting) REFERENCES meetings(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, meeting TEXT, kind TEXT, version INTEGER,
          state TEXT, error TEXT, created REAL, finished REAL, FOREIGN KEY(meeting) REFERENCES meetings(id) ON DELETE CASCADE);
        CREATE UNIQUE INDEX IF NOT EXISTS active_job ON jobs(meeting,kind,version) WHERE state IN ('queued','running');
        CREATE TABLE IF NOT EXISTS shares(id TEXT PRIMARY KEY, meeting TEXT, data TEXT,
          FOREIGN KEY(meeting) REFERENCES meetings(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS chunks(meeting TEXT, seq INTEGER, digest TEXT, bytes INTEGER,
          PRIMARY KEY(meeting,seq), FOREIGN KEY(meeting) REFERENCES meetings(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS chats(id TEXT PRIMARY KEY, meeting TEXT, actor TEXT, version INTEGER,
          data TEXT, created REAL, FOREIGN KEY(meeting) REFERENCES meetings(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS notifications(id TEXT PRIMARY KEY, owner INTEGER, meeting TEXT, data TEXT, seen INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS mail(id TEXT PRIMARY KEY, owner INTEGER, recipient TEXT, subject TEXT, body TEXT, state TEXT, error TEXT);
        CREATE TABLE IF NOT EXISTS config(id INTEGER PRIMARY KEY, data TEXT);
        CREATE TABLE IF NOT EXISTS audit(id TEXT PRIMARY KEY, actor TEXT, meeting TEXT, action TEXT, created REAL);
        CREATE TABLE IF NOT EXISTS limits(key TEXT PRIMARY KEY, window INTEGER, count INTEGER);
