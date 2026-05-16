import {
  BackupRecord,
  ClientEntry,
  FirmwareRecord,
  FlashFilters,
  FlashRowDetail,
  FlashRowSummary,
  PortRow,
  Tag,
} from "./types";

const BASE = "/flash/api";

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(BASE + path, { ...init, headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) } });
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw Object.assign(new Error(body.error ?? `HTTP ${r.status}`), { status: r.status, body });
  }
  return r.json() as Promise<T>;
}

// Clients
export const listClients = () => http<{ clients: ClientEntry[] }>("/clients");
export const listPorts = (name: string) => http<{ ports: PortRow[] }>(`/clients/${encodeURIComponent(name)}/ports`);

// Firmware
export const listFirmware = (params: { tag?: string[]; q?: string; limit?: number; before?: string } = {}) => {
  const qs = new URLSearchParams();
  (params.tag ?? []).forEach(t => qs.append("tag", t));
  if (params.q) qs.set("q", params.q);
  if (params.limit) qs.set("limit", String(params.limit));
  if (params.before) qs.set("before", params.before);
  const s = qs.toString();
  return http<{ items: FirmwareRecord[]; next_before: string | null }>("/firmware" + (s ? `?${s}` : ""));
};
export const getFirmware = (id: string) => http<FirmwareRecord>(`/firmware/${id}`);
export const createFirmware = (body: any) => http<FirmwareRecord>("/firmware", { method: "POST", body: JSON.stringify(body) });
export const patchFirmware = (id: string, body: any) => http<FirmwareRecord>(`/firmware/${id}`, { method: "PATCH", body: JSON.stringify(body) });
export const deleteFirmware = (id: string) => http<{ status: string }>(`/firmware/${id}`, { method: "DELETE" });
export const downloadFirmwareUrl = (id: string) => `${BASE}/firmware/${id}/download`;
export const listFirmwareFlashes = (id: string, limit = 50, before?: string) => {
  const qs = new URLSearchParams({ limit: String(limit) });
  if (before) qs.set("before", before);
  return http<{ items: FlashRowSummary[]; next_before: string | null }>(`/firmware/${id}/flashes?${qs}`);
};

// Backups
export const listBackups = (params: { client?: string; q?: string; limit?: number; before?: string } = {}) => {
  const qs = new URLSearchParams();
  if (params.client) qs.set("client", params.client);
  if (params.q) qs.set("q", params.q);
  if (params.limit) qs.set("limit", String(params.limit));
  if (params.before) qs.set("before", params.before);
  const s = qs.toString();
  return http<{ items: BackupRecord[]; next_before: string | null }>("/backups" + (s ? `?${s}` : ""));
};
export const getBackup = (id: string) => http<BackupRecord>(`/backups/${id}`);
export const patchBackup = (id: string, body: any) => http<BackupRecord>(`/backups/${id}`, { method: "PATCH", body: JSON.stringify(body) });
export const deleteBackup = (id: string) => http<{ status: string }>(`/backups/${id}`, { method: "DELETE" });
export const bulkDeleteBackups = (ids: string[]) => http<{ deleted: number; refused: { id: string; reason: string }[] }>("/backups/bulk-delete", { method: "POST", body: JSON.stringify({ ids }) });
export const promoteBackup = (id: string, body: any) => http<FirmwareRecord>(`/backups/${id}/promote`, { method: "POST", body: JSON.stringify(body) });
export const downloadBackupUrl = (id: string) => `${BASE}/backups/${id}/download`;
export const listBackupFlashes = (id: string, limit = 50, before?: string) => {
  const qs = new URLSearchParams({ limit: String(limit) });
  if (before) qs.set("before", before);
  return http<{ items: FlashRowSummary[]; next_before: string | null }>(`/backups/${id}/flashes?${qs}`);
};

// Tags
export const listTags = () => http<{ items: Tag[] }>("/tags");
export const createTag = (name: string) => http<Tag>("/tags", { method: "POST", body: JSON.stringify({ name }) });
export const renameTag = (id: string, name: string) => http<Tag>(`/tags/${id}`, { method: "PATCH", body: JSON.stringify({ name }) });
export const deleteTag = (id: string) => http<{ status: string }>(`/tags/${id}`, { method: "DELETE" });

// Flashes
export const postFlash = (body: any) => http<{ job_id: string }>("/flash", { method: "POST", body: JSON.stringify(body) });
export const getFlash = (id: string) => http<FlashRowDetail>(`/flash/${id}`);
export const getCurrentFlash = () => http<FlashRowDetail | {}>("/flash/current");
export const listFlashes = (filters: FlashFilters = {}, limit = 50, before?: string) => {
  const qs = new URLSearchParams();
  (filters.client ?? []).forEach(c => qs.append("client", c));
  (filters.outcome ?? []).forEach(o => qs.append("outcome", o));
  if (filters.source_kind) qs.set("source_kind", filters.source_kind);
  if (filters.source_id) qs.set("source_id", filters.source_id);
  if (filters.since) qs.set("since", filters.since);
  if (filters.until) qs.set("until", filters.until);
  qs.set("limit", String(limit));
  if (before) qs.set("before", before);
  return http<{ items: FlashRowSummary[]; next_before: string | null }>(`/flashes?${qs}`);
};
export const patchFlashNote = (id: string, note: string) => http<{ note: string }>(`/flashes/${id}/note`, { method: "PATCH", body: JSON.stringify({ note }) });
export const replayFlash = (id: string, body: { client?: string; port?: string } = {}) => http<{ job_id: string }>(`/flashes/${id}/replay`, { method: "POST", body: JSON.stringify(body) });
