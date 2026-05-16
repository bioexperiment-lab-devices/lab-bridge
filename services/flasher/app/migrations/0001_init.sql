-- 0001_init.sql — full schema for the flasher library + history.

CREATE TABLE schema_version (
    version INTEGER NOT NULL
);
INSERT INTO schema_version (version) VALUES (0);

CREATE TABLE firmware (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    original_filename TEXT,
    test_command TEXT,
    expected_response TEXT,
    source_backup_id TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX idx_firmware_name ON firmware(name);
CREATE INDEX idx_firmware_sha256 ON firmware(sha256);

CREATE TABLE backups (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    sha256 TEXT NOT NULL UNIQUE,
    size_bytes INTEGER NOT NULL,
    client TEXT NOT NULL,
    port_name TEXT NOT NULL,
    vid TEXT,
    pid TEXT,
    serial_number TEXT,
    product TEXT,
    serialhop_saved_path TEXT,
    test_command TEXT,
    expected_response TEXT,
    source_flash_id TEXT NOT NULL,
    captured_at TEXT NOT NULL
);
CREATE INDEX idx_backups_captured_at ON backups(captured_at DESC);
CREATE INDEX idx_backups_client_port ON backups(client, port_name);

CREATE TABLE flashes (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    outcome TEXT,
    client TEXT NOT NULL,
    port_name TEXT NOT NULL,
    port_snapshot_json TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source_id TEXT NOT NULL,
    firmware_sha256 TEXT NOT NULL,
    firmware_name TEXT NOT NULL,
    test_command_used TEXT,
    expected_response_used TEXT,
    skip_backup INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    duration_ms INTEGER,
    result_json TEXT,
    error_code TEXT,
    error_detail TEXT,
    backup_id TEXT,
    operator_note TEXT NOT NULL DEFAULT ''
);
CREATE INDEX idx_flashes_started_at ON flashes(started_at DESC);
CREATE INDEX idx_flashes_source ON flashes(source_kind, source_id);
CREATE INDEX idx_flashes_status ON flashes(status);
CREATE INDEX idx_flashes_client ON flashes(client);
CREATE INDEX idx_flashes_outcome ON flashes(outcome);

CREATE TABLE tags (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE firmware_tags (
    firmware_id TEXT NOT NULL REFERENCES firmware(id) ON DELETE CASCADE,
    tag_id TEXT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (firmware_id, tag_id)
);
