import { useEffect, useMemo, useState } from "react";
import {
  getFlash,
  listClients,
  patchFlashNote,
  replayFlash,
} from "../api";
import { ClientEntry, FlashRowDetail } from "../types";
import {
  FlButton,
  FlDropdown,
  FlHexDiff,
  FlJSON,
  FlOutcome,
  FlStageStrip,
  STAGE_ORDER,
  StageName,
  StageState,
  outcomeTone,
} from "./Fl";
import { normalizeHex } from "../hex";

interface Props {
  flashId: string;
  onClose: () => void;
}

function stageStatesFromResult(result: any): Partial<Record<StageName, StageState>> {
  const out: Partial<Record<StageName, StageState>> = {};
  if (!result) return out;
  const stages = (result.stages || result) as any;
  if (Array.isArray(stages)) {
    for (const s of stages) {
      if (!s?.name) continue;
      const name = s.name as StageName;
      if (!(STAGE_ORDER as readonly string[]).includes(name)) continue;
      const status = s.status as string;
      out[name] = (status === "ok" || status === "failed" || status === "skipped" || status === "active")
        ? (status as StageState)
        : "na";
    }
  } else if (stages && typeof stages === "object") {
    for (const name of STAGE_ORDER) {
      const entry = stages[name];
      if (!entry) continue;
      const status = (entry.status ?? entry) as string;
      if (status === "ok" || status === "failed" || status === "skipped" || status === "active") {
        out[name] = status as StageState;
      }
    }
  }
  return out;
}

function bytesArray(canonical: string): string[] {
  const c = normalizeHex(canonical);
  const out: string[] = [];
  for (let i = 0; i < c.length; i += 2) out.push(c.slice(i, i + 2).toUpperCase());
  return out;
}

function diffIndices(a: string, b: string): number[] {
  const ax = normalizeHex(a);
  const bx = normalizeHex(b);
  const out: number[] = [];
  const n = Math.min(ax.length, bx.length) / 2;
  for (let i = 0; i < n; i++) {
    if (ax.slice(i * 2, i * 2 + 2) !== bx.slice(i * 2, i * 2 + 2)) out.push(i);
  }
  const longer = Math.max(ax.length, bx.length) / 2;
  for (let i = n; i < longer; i++) out.push(i);
  return out;
}

export function LogDetailDrawer({ flashId, onClose }: Props) {
  const [row, setRow] = useState<FlashRowDetail | null>(null);
  const [note, setNote] = useState("");
  const [clients, setClients] = useState<ClientEntry[]>([]);
  const [replayClient, setReplayClient] = useState<string>("");
  const [replayPort, setReplayPort] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [savingNote, setSavingNote] = useState(false);
  const [replaying, setReplaying] = useState(false);

  async function refresh() {
    setError(null);
    try {
      const r = await getFlash(flashId);
      setRow(r);
      setNote(r.operator_note);
      setReplayClient(r.client);
      setReplayPort(r.port_name);
    } catch (e: any) {
      setError(e.body?.detail ?? String(e?.message ?? e));
    }
  }
  useEffect(() => { refresh(); }, [flashId]);
  useEffect(() => { listClients().then(r => setClients(r.clients)).catch(() => {}); }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const stages = useMemo(() => stageStatesFromResult(row?.result), [row?.result]);

  if (!row) {
    return (
      <div className="fl-drawer-scrim" onMouseDown={onClose}>
        <aside className="fl-drawer" onMouseDown={e => e.stopPropagation()}>
          <div className="fl-drawer__head">
            <h2 className="fl-drawer__title">Flash</h2>
            <button className="fl-drawer__close" onClick={onClose}>✕</button>
          </div>
          <div className="fl-drawer__body">
            <div className="fl-muted fl-mono" style={{ fontSize: 12 }}>{error ?? "Loading…"}</div>
          </div>
        </aside>
      </div>
    );
  }

  const tone = outcomeTone(row.outcome, row.status);
  const testResult = row.result && (row.result as any).test_result;
  const hasDiff = testResult?.expected != null && testResult?.received != null;
  const sourceDeleted = (row as any).source_deleted === true;

  return (
    <div className="fl-drawer-scrim" onMouseDown={onClose}>
      <aside className="fl-drawer" onMouseDown={e => e.stopPropagation()}>
        <div className="fl-drawer__head">
          <h2 className="fl-drawer__title">
            Flash <span style={{ color: "var(--text-muted)" }}>·</span>{" "}
            <span style={{ color: "var(--accent)" }}>{row.id.slice(0, 8)}</span>
          </h2>
          <FlOutcome outcome={row.outcome ?? row.status} tone={tone} />
          <button className="fl-drawer__close" onClick={onClose}>✕</button>
        </div>
        <div className="fl-drawer__body">
          <dl className="fl-dl" style={{ gridTemplateColumns: "110px 1fr" }}>
            <dt>Started</dt><dd>{row.started_at}</dd>
            <dt>Status</dt><dd>{row.status}{row.outcome ? ` (${row.outcome})` : ""}</dd>
            <dt>Client · port</dt><dd>{row.client} · {row.port_name}</dd>
            <dt>Firmware</dt><dd>{row.firmware_name} (sha {row.firmware_sha256.slice(0, 12)})</dd>
            <dt>Source kind</dt><dd>{row.source_kind}</dd>
            {row.duration_ms != null && <><dt>Duration</dt><dd>{(row.duration_ms / 1000).toFixed(1)}s</dd></>}
            {row.backup_id && <><dt>Backup ID</dt><dd>{row.backup_id}</dd></>}
          </dl>

          <div>
            <div className="fl-dh">Stages</div>
            <FlStageStrip states={stages} />
            <div className="fl-muted fl-mono" style={{ fontSize: 10.5, marginTop: 6, lineHeight: 1.5 }}>
              hover any chip for status · duration · error
            </div>
          </div>

          {(row.error_code || row.error_detail) && (
            <div className="fl-errblock">
              {row.error_code && <span className="fl-errblock__code">{row.error_code}</span>}
              {row.error_detail && <span className="fl-errblock__msg">{row.error_detail}</span>}
            </div>
          )}

          {hasDiff && (
            <div>
              <div className="fl-dh">Hex diff (test_result)</div>
              <FlHexDiff
                expected={bytesArray(testResult.expected)}
                received={bytesArray(testResult.received)}
                diffIdx={diffIndices(testResult.expected, testResult.received)}
              />
            </div>
          )}

          <details className="fl-details">
            <summary>Raw result JSON</summary>
            <FlJSON data={row.result ?? {}} />
          </details>

          <div>
            <div className="fl-dh">Operator note</div>
            <textarea
              className="shp-input"
              rows={3}
              style={{ height: "auto", padding: "8px 10px", resize: "vertical" }}
              value={note}
              onChange={e => setNote(e.target.value)}
            />
            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 6, gap: 6 }}>
              <FlButton
                small
                variant="primary"
                disabled={savingNote || note === row.operator_note}
                onClick={async () => {
                  setSavingNote(true);
                  setError(null);
                  try { await patchFlashNote(flashId, note); await refresh(); }
                  catch (e: any) { setError(e.body?.detail ?? String(e?.message ?? e)); }
                  finally { setSavingNote(false); }
                }}
              >
                {savingNote ? "Saving…" : "Save note"}
              </FlButton>
            </div>
          </div>

          <div>
            <div className="fl-dh">Repeat this flash</div>
            {sourceDeleted && (
              <div className="shp-info-block" style={{ marginBottom: 8 }}>
                <span className="shp-info-block__icon">⚠</span>
                <span>The source firmware/backup for this flash has been deleted. Replay will fail.</span>
              </div>
            )}
            <div className="shp-input-row" style={{ alignItems: "flex-end" }}>
              <div style={{ flex: 1, minWidth: 160 }}>
                <div className="fl-muted fl-mono" style={{ fontSize: 10.5, marginBottom: 2 }}>client</div>
                <FlDropdown
                  value={replayClient}
                  onChange={setReplayClient}
                  mono
                  options={clients.map(c => ({
                    value: c.name,
                    label: c.online ? c.name : `${c.name} (offline)`,
                    disabled: !c.online,
                  }))}
                />
              </div>
              <div style={{ flex: 1, minWidth: 160 }}>
                <div className="fl-muted fl-mono" style={{ fontSize: 10.5, marginBottom: 2 }}>port</div>
                <input
                  className="shp-input shp-input--mono"
                  value={replayPort}
                  onChange={e => setReplayPort(e.target.value)}
                />
              </div>
              <FlButton
                variant="primary"
                disabled={replaying || sourceDeleted || !replayClient || !replayPort}
                onClick={async () => {
                  setReplaying(true);
                  setError(null);
                  try {
                    await replayFlash(flashId, { client: replayClient, port: replayPort });
                    onClose();
                  } catch (e: any) {
                    if (e.status === 410) setError("Source firmware/backup has been deleted — cannot replay.");
                    else setError(e.body?.detail ?? String(e?.message ?? e));
                  } finally {
                    setReplaying(false);
                  }
                }}
              >
                {replaying ? "Repeating…" : "Repeat"}
              </FlButton>
            </div>
          </div>

          {error && <div className="fl-errblock"><span className="fl-errblock__msg">{error}</span></div>}
        </div>
      </aside>
    </div>
  );
}
