import { useEffect, useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import {
  bulkDeleteBackups,
  deleteBackup,
  downloadBackupUrl,
  getBackup,
  listBackupFlashes,
  listBackups,
  listClients,
  patchBackup,
} from "../api";
import {
  FlButton,
  FlDropdown,
  FlOutc,
  FlPage,
  FlStatsCard,
  outcomeTone,
} from "../components/Fl";
import { BackupRecord, ClientEntry, FlashRowSummary } from "../types";
import { DetailPlaceholder } from "./FirmwareTab";
import { PromoteBackupModal } from "../components/PromoteBackupModal";
import { LogDetailDrawer } from "../components/LogDetailDrawer";

export function BackupsTab({ selectedId }: { selectedId: string | null }) {
  const navigate = useNavigate();
  const [list, setList] = useState<BackupRecord[]>([]);
  const [clients, setClients] = useState<ClientEntry[]>([]);
  const [search, setSearch] = useState("");
  const [clientFilter, setClientFilter] = useState<string>("");
  const [bulk, setBulk] = useState<Set<string>>(new Set());
  const [promoting, setPromoting] = useState<BackupRecord | null>(null);
  const [openFlashId, setOpenFlashId] = useState<string | null>(null);

  const selectBackup = (id: string | null) => {
    if (id) navigate({ to: "/backups/$id", params: { id } });
    else navigate({ to: "/backups" });
  };

  async function refresh() {
    const r = await listBackups({
      client: clientFilter || undefined,
      q: search || undefined,
      limit: 200,
    });
    setList(r.items);
    setBulk(new Set());
  }
  useEffect(() => { refresh(); }, [search, clientFilter]);
  useEffect(() => { listClients().then(r => setClients(r.clients)).catch(() => {}); }, []);

  const totalBytes = list.reduce((acc, b) => acc + b.size_bytes, 0);

  return (
    <FlPage
      title="Backups"
      subtitle={`${list.length} records · ${formatBytes(totalBytes)} total`}
    >
      <div className="fl-twopane">
        <div className="fl-pane">
          <div className="fl-pane__head">
            <div className="fl-pane__searchrow">
              <input
                className="shp-input"
                placeholder="search by name"
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
              <FlDropdown
                value={clientFilter}
                width={160}
                placeholder="(any client)"
                onChange={v => setClientFilter(v)}
                options={[
                  { value: "", label: "(any client)" },
                  ...clients.map(c => ({ value: c.name, label: c.name })),
                ]}
              />
            </div>
            <div className="fl-pane__searchrow">
              <span className="fl-muted fl-mono" style={{ fontSize: 11 }}>
                {list.length} backups · {bulk.size} selected
              </span>
              <span className="fl-spacer" />
              <FlButton
                small
                variant="danger"
                disabled={bulk.size === 0}
                onClick={async () => {
                  if (!confirm(`Delete ${bulk.size} backups?`)) return;
                  const result = await bulkDeleteBackups(Array.from(bulk));
                  if (result.refused.length) {
                    alert(`Refused:\n${result.refused.map(r => `${r.id}: ${r.reason}`).join("\n")}`);
                  }
                  await refresh();
                }}
              >
                Delete selected ({bulk.size})
              </FlButton>
            </div>
          </div>
          <div className="fl-pane__body">
            {list.length === 0 ? (
              <div className="fl-output__empty" style={{ padding: 32 }}>
                No backups match.
              </div>
            ) : list.map(b => {
              const checked = bulk.has(b.id);
              return (
                <div
                  key={b.id}
                  className="fl-row"
                  data-selected={b.id === selectedId || undefined}
                  onClick={() => selectBackup(b.id)}
                >
                  <span
                    className="shp-checkbox"
                    data-checked={checked || undefined}
                    style={{ paddingTop: 2 }}
                    onClick={e => {
                      e.stopPropagation();
                      setBulk(s => {
                        const n = new Set(s);
                        if (n.has(b.id)) n.delete(b.id); else n.add(b.id);
                        return n;
                      });
                    }}
                  >
                    <span className="shp-checkbox__box">{checked ? "✓" : ""}</span>
                  </span>
                  <div className="fl-row__main">
                    <span className="fl-row__name">{b.name}</span>
                    <span className="fl-row__meta">
                      {b.captured_at} · <b>{b.client}</b> · {b.port_name}
                    </span>
                    <span className="fl-row__meta">
                      {b.product || (b.vid && b.pid ? `${b.vid}:${b.pid}` : "—")} · sha <b>{b.sha256.slice(0, 12)}</b> · flashes: <b>{b.stats.total}</b>
                    </span>
                  </div>
                  <div className="fl-row__actions" onClick={e => e.stopPropagation()}>
                    <a className="shp-btn shp-btn--ghost shp-btn--sm" href={downloadBackupUrl(b.id)} download>
                      Download
                    </a>
                    <FlButton
                      small
                      variant="ghost"
                      onClick={async () => {
                        if (!confirm(`Delete backup "${b.name}"?`)) return;
                        try {
                          await deleteBackup(b.id);
                          if (selectedId === b.id) selectBackup(null);
                          await refresh();
                        } catch (e: any) {
                          alert(e.body?.detail ?? String(e?.message ?? e));
                        }
                      }}
                    >
                      <span style={{ color: "var(--danger)" }}>Delete</span>
                    </FlButton>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="fl-pane">
          {selectedId ? (
            <BackupDetail
              backupId={selectedId}
              onPromote={setPromoting}
              onOpenFlash={setOpenFlashId}
              onSaved={refresh}
            />
          ) : (
            <DetailPlaceholder text="Select a backup on the left." />
          )}
        </div>
      </div>

      {promoting && (
        <PromoteBackupModal
          backup={promoting}
          onClose={() => setPromoting(null)}
          onCreated={firmware => {
            setPromoting(null);
            navigate({ to: "/firmware/$id", params: { id: firmware.id } });
          }}
        />
      )}
      {openFlashId && <LogDetailDrawer flashId={openFlashId} onClose={() => setOpenFlashId(null)} />}
    </FlPage>
  );
}

function BackupDetail({
  backupId,
  onPromote,
  onOpenFlash,
  onSaved,
}: {
  backupId: string;
  onPromote: (b: BackupRecord) => void;
  onOpenFlash: (id: string) => void;
  onSaved: () => void;
}) {
  const [row, setRow] = useState<BackupRecord | null>(null);
  const [flashes, setFlashes] = useState<FlashRowSummary[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setError(null);
    try {
      const r = await getBackup(backupId);
      setRow(r);
      setName(r.name); setDescription(r.description);
      setFlashes((await listBackupFlashes(backupId)).items);
    } catch (e: any) {
      setError(e.body?.detail ?? String(e?.message ?? e));
    }
  }
  useEffect(() => { refresh(); }, [backupId]);

  if (!row) return <div className="fl-detail__placeholder">{error ?? "Loading…"}</div>;

  const dirty = name !== row.name || description !== row.description;

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await patchBackup(backupId, { name, description });
      await refresh();
      onSaved();
    } catch (e: any) {
      setError(e.body?.detail ?? String(e?.message ?? e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <div className="fl-detail__head">
        <div style={{ display: "flex", alignItems: "flex-start", gap: 20, flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 4 }}>
            <h2 className="fl-detail__h">{row.name}</h2>
            <div className="fl-detail__sub">
              sha256 {row.sha256} · {row.size_bytes} B · captured {row.captured_at}
            </div>
            {row.source_flash_id && (
              <div className="fl-detail__sub">
                captured during flash{" "}
                <Link
                  to="/logs"
                  search={{ open: row.source_flash_id } as any}
                >
                  {row.source_flash_id}
                </Link>
              </div>
            )}
          </div>
          <FlButton
            small
            variant="primary"
            onClick={() => onPromote(row)}
            leading={<span style={{ fontWeight: 600, fontSize: 13, lineHeight: 1 }}>↑</span>}
          >
            Promote to firmware
          </FlButton>
        </div>
      </div>
      <div className="fl-detail__body">
        <div>
          <div className="fl-dh">Device metadata</div>
          <dl className="fl-dl" style={{ gridTemplateColumns: "110px 1fr" }}>
            <dt>Client</dt><dd>{row.client}</dd>
            <dt>Port</dt><dd>{row.port_name}</dd>
            <dt>VID:PID</dt><dd>{row.vid && row.pid ? `${row.vid}:${row.pid}` : "—"}</dd>
            <dt>Serial #</dt><dd>{row.serial_number || "—"}</dd>
            <dt>Product</dt><dd>{row.product || "—"}</dd>
            <dt>SerialHop path</dt><dd>{row.serialhop_saved_path || "—"}</dd>
          </dl>
        </div>

        <FlStatsCard
          total={row.stats.total}
          successes={row.stats.successes}
          rollbacks={row.stats.rollbacks}
          failures={row.stats.failures}
          lastFlashed={row.stats.last_flashed_at
            ? `${row.stats.last_flashed_at} · ${row.stats.last_flashed_client} · ${row.stats.last_flashed_port}`
            : null}
        />

        <div>
          <div className="fl-dh">Edit</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div className="shp-field" style={{ gridTemplateColumns: "140px minmax(0, 1fr)" }}>
              <label className="shp-field__label">Name</label>
              <div className="shp-field__col">
                <input className="shp-input" value={name} onChange={e => setName(e.target.value)} />
              </div>
            </div>
            <div className="shp-field" style={{ gridTemplateColumns: "140px minmax(0, 1fr)", alignItems: "start" }}>
              <label className="shp-field__label">Description</label>
              <div className="shp-field__col">
                <textarea
                  className="shp-input"
                  rows={2}
                  style={{ height: "auto", paddingTop: 6, paddingBottom: 6, resize: "vertical" }}
                  value={description}
                  onChange={e => setDescription(e.target.value)}
                />
              </div>
            </div>
            {error && <div className="fl-errblock"><span className="fl-errblock__msg">{error}</span></div>}
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <FlButton small variant="ghost" disabled={!dirty || saving} onClick={() => { setName(row.name); setDescription(row.description); }}>
                Revert
              </FlButton>
              <FlButton small variant="primary" disabled={!dirty || saving || !name.trim()} onClick={save}>
                {saving ? "Saving…" : "Save"}
              </FlButton>
            </div>
          </div>
        </div>

        <div>
          <div className="fl-dh">Used by flashes · {flashes.length}</div>
          {flashes.length === 0 ? (
            <div className="fl-muted fl-mono" style={{ fontSize: 11.5 }}>
              No flashes have used this backup as their source yet.
            </div>
          ) : (
            <div className="fl-hist-list">
              {flashes.map(h => (
                <div key={h.id} className="fl-hist" onClick={() => onOpenFlash(h.id)}>
                  <span className="fl-hist__time">{h.started_at}</span>
                  <span>{h.client}</span>
                  <span className="fl-hist__src">{h.port_name}</span>
                  <FlOutc outcome={h.outcome ?? h.status} tone={outcomeTone(h.outcome, h.status)} />
                  <span className="fl-hist__dur">{h.duration_ms != null ? `${(h.duration_ms / 1000).toFixed(1)}s` : "—"}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(2)} MB`;
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`;
}
