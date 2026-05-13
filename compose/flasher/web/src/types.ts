export interface ClientSummary {
  name: string
  port: number
}

export interface ClientsResponse {
  clients: ClientSummary[]
}

export interface PortInfo {
  name: string
  is_usb: boolean
  vid: string
  pid: string
  serial_number: string
  product: string
  discovered: boolean
  device_id: string
}

export interface PortsResponse {
  ports: PortInfo[]
}

export type StageStatus = 'ok' | 'failed' | 'skipped' | 'n/a'

export interface StageEntry {
  status: StageStatus
  duration_ms?: number
  error?: string
  first_mismatch_offset?: string
  verify_status?: 'ok' | 'failed'
}

export type Outcome =
  | 'success'
  | 'rolled_back_verify_failed'
  | 'rolled_back_test_failed'
  | 'failed_preflight'
  | 'failed_backup'
  | 'failed_no_recovery'

export interface FlashStages {
  preflight: StageEntry
  backup: StageEntry
  erase: StageEntry
  program: StageEntry
  verify: StageEntry
  test: StageEntry
  rollback: StageEntry
}

export interface BackupInfo {
  hex: string
  saved_path: string
  sha256: string
  size_bytes: number
  scope: 'flash_only'
}

export interface TestResult {
  sent: string
  expected: string
  received: string
  match: boolean
}

export interface FlashResult {
  outcome: Outcome
  port: string
  stages: FlashStages
  backup?: BackupInfo
  test_result?: TestResult
  recovery_hint?: string
}

export interface FlashRunning {
  job_id: string
  status: 'running'
  client: string
  port: string
  started_at: string
  elapsed_ms: number
}

export interface FlashDone {
  job_id: string
  status: 'done'
  client: string
  port: string
  started_at: string
  result: FlashResult
}

export interface FlashErrored {
  job_id: string
  status: 'error'
  client: string
  port: string
  started_at: string
  error_code: string
  detail: string
}

export type FlashJob = FlashRunning | FlashDone | FlashErrored

export interface FlashRequestBody {
  client: string
  port: string
  firmware: string
  test: { command: string; expected_response: string } | null
}
