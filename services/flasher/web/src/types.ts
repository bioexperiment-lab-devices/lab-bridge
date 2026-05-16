export interface ClientEntry {
  name: string;
  port: number;
  online: boolean;
}

export interface PortRow {
  name: string;
  is_usb: boolean;
  vid: string;
  pid: string;
  serial_number: string;
  product: string;
  discovered: boolean;
  device_id: string;
}

export interface Tag { id: string; name: string; created_at: string; firmware_count?: number; }

export interface FlashStats {
  total: number;
  successes: number;
  rollbacks: number;
  failures: number;
  last_flashed_at: string | null;
  last_flashed_client: string | null;
  last_flashed_port: string | null;
}

export interface FirmwareRecord {
  id: string;
  name: string;
  description: string;
  sha256: string;
  size_bytes: number;
  original_filename: string | null;
  test_command: string | null;
  expected_response: string | null;
  source_backup_id: string | null;
  created_at: string;
  tags: Tag[];
  stats: FlashStats;
}

export interface BackupRecord {
  id: string;
  name: string;
  description: string;
  sha256: string;
  size_bytes: number;
  client: string;
  port_name: string;
  vid: string | null;
  pid: string | null;
  serial_number: string | null;
  product: string | null;
  serialhop_saved_path: string | null;
  test_command: string | null;
  expected_response: string | null;
  source_flash_id: string;
  captured_at: string;
  stats: FlashStats;
}

export type FlashStatus = "running" | "done" | "error" | "interrupted";

export interface FlashRowSummary {
  id: string;
  status: FlashStatus;
  outcome: string | null;
  client: string;
  port_name: string;
  source_kind: "firmware" | "backup";
  source_id: string;
  firmware_name: string;
  firmware_sha256: string;
  started_at: string;
  duration_ms: number | null;
  operator_note: string;
}

export interface FlashRowDetail extends FlashRowSummary {
  port_snapshot: Record<string, string>;
  test_command_used: string | null;
  expected_response_used: string | null;
  skip_backup: boolean;
  finished_at: string | null;
  result: any | null;
  error_code: string | null;
  error_detail: string | null;
  backup_id: string | null;
}

export interface FlashFilters {
  client?: string[];
  outcome?: string[];
  source_kind?: "firmware" | "backup";
  source_id?: string;
  since?: string;
  until?: string;
}

export type TabId = "flash" | "firmware" | "backups" | "logs";
