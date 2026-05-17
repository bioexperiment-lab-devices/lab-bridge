import { ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "@tanstack/react-router";
import {
  getBackup,
  getFirmware,
  getFlash,
  listBackups,
  listClients,
  listFirmware,
  listPorts,
  listTags,
  postFlash,
} from "../api";
import { useFlashRun } from "../Shell";
import { useFlashDraft } from "../hooks/useFlashDraft";
import {
  FlButton,
  FlDropdown,
  FlHexDiff,
  FlHexInput,
  FlJSON,
  FlOutcome,
  FlPage,
  FlSeg,
  FlStageStrip,
  FlStep,
  FlSwitch,
  FlTag,
  FlToggleLabel,
  STAGE_ORDER,
  StageName,
  StageState,
  outcomeTone,
} from "../components/Fl";
import {
  asciiPreview,
  formatHexBytes,
  hexByteCount,
  isValidHex,
  normalizeHex,
} from "../hex";
import {
  BackupRecord,
  ClientEntry,
  FirmwareRecord,
  FlashRowDetail,
  PortRow,
  Tag,
} from "../types";

type FlashSource =
  | { kind: "firmware"; record: FirmwareRecord }
  | { kind: "backup"; record: BackupRecord };

function formatElapsed(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const mm = String(Math.floor(total / 60)).padStart(2, "0");
  const ss = String(total % 60).padStart(2, "0");
  return `${mm}:${ss}`;
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

function HexEditable({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string; // canonical
  onChange: (canonical: string) => void;
}) {
  const formatted = formatHexBytes(value);
  const empty = value.length === 0;
  const valid = isValidHex(value);
  const error = !empty && !valid;
  return (
    <FlHexInput
      label={label}
      value={formatted}
      bytes={hexByteCount(value)}
      ascii={empty || error ? undefined : asciiPreview(value)}
      error={error}
      editable
      placeholder="01 02 03"
      onChange={v => onChange(normalizeHex(v))}
    />
  );
}

export function FlashTab() {
  const { runningFlashId, setRunningFlashId } = useFlashRun();

  // ----- persisted form draft (survives reload) -----
  const [draft, setDraft] = useFlashDraft();

  // ----- form state -----
  const [client, setClient] = useState<string | null>(draft.client);
  const [clients, setClients] = useState<ClientEntry[]>([]);
  const [ports, setPorts] = useState<PortRow[]>([]);
  const [portsLoading, setPortsLoading] = useState(false);
  const [portsError, setPortsError] = useState<string | null>(null);
  const [selectedPort, setSelectedPort] = useState<string | null>(draft.port);
  const [sourceKind, setSourceKind] = useState<"firmware" | "backups">(draft.sourceKind);
  const [source, setSource] = useState<FlashSource | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [tags, setTags] = useState<Tag[]>([]);
  const [tagFilter, setTagFilter] = useState<string[]>([]);
  const [firmwareItems, setFirmwareItems] = useState<FirmwareRecord[]>([]);
  const [backupItems, setBackupItems] = useState<BackupRecord[]>([]);
  const [tcmd, setTcmd] = useState(draft.tcmd);
  const [eresp, setEresp] = useState(draft.eresp);
  const [runTest, setRunTest] = useState(draft.runTest);
  const [skipBackup, setSkipBackup] = useState(draft.skipBackup);
  const [savePairToRecord, setSavePairToRecord] = useState(false);
  const [latestFlash, setLatestFlash] = useState<FlashRowDetail | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // The source-change reset effect should skip the first time `source` becomes
  // non-null via rehydrate — the user's persisted test-pair edits would otherwise
  // get overwritten by the record's stored values on every page reload.
  const skipNextSourceReset = useRef(false);

  // ----- rehydrate the selected source from the draft id on mount -----
  useEffect(() => {
    const id = draft.sourceId;
    const kind = draft.sourceKind;
    if (!id) return;
    let cancelled = false;
    (async () => {
      try {
        if (kind === "firmware") {
          const record = await getFirmware(id);
          if (!cancelled) {
            skipNextSourceReset.current = true;
            setSource({ kind: "firmware", record });
          }
        } else {
          const record = await getBackup(id);
          if (!cancelled) {
            skipNextSourceReset.current = true;
            setSource({ kind: "backup", record });
          }
        }
      } catch {
        // Source no longer exists — clear the stale draft entry.
        setDraft({ sourceId: null });
      }
    })();
    return () => { cancelled = true; };
    // Run once on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ----- mirror form state back into draft -----
  useEffect(() => {
    setDraft({
      client,
      port: selectedPort,
      sourceKind,
      sourceId: source?.record.id ?? null,
      tcmd,
      eresp,
      runTest,
      skipBackup,
    });
  }, [client, selectedPort, sourceKind, source?.record.id, tcmd, eresp, runTest, skipBackup, setDraft]);

  // ----- data loaders -----
  useEffect(() => { listClients().then(r => setClients(r.clients)).catch(() => {}); }, []);
  useEffect(() => { listTags().then(r => setTags(r.items)).catch(() => {}); }, []);

  async function refreshPorts(name: string) {
    setPortsLoading(true);
    setPortsError(null);
    try {
      const r = await listPorts(name);
      setPorts(r.ports);
    } catch (e: any) {
      setPortsError(e.body?.detail ?? String(e?.message ?? e));
      setPorts([]);
    } finally {
      setPortsLoading(false);
    }
  }
  // Keep the persisted port when rehydrating; clear only on a real user change.
  const prevClient = useRef<string | null>(draft.client);
  useEffect(() => {
    if (prevClient.current !== client) {
      prevClient.current = client;
      setSelectedPort(null);
      setPorts([]);
    }
    if (client) refreshPorts(client);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client]);

  // ----- source list filtering -----
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        if (sourceKind === "firmware") {
          const r = await listFirmware({
            q: searchTerm || undefined,
            tag: tagFilter,
            limit: 200,
          });
          if (!cancelled) setFirmwareItems(r.items);
        } else {
          const r = await listBackups({
            q: searchTerm || undefined,
            limit: 200,
          });
          if (!cancelled) setBackupItems(r.items);
        }
      } catch {
        // ignore
      }
    }
    load();
    return () => { cancelled = true; };
  }, [sourceKind, searchTerm, tagFilter.join(",")]);

  // ----- reset test pair when source changes -----
  const sourceKey = source ? `${source.kind}:${source.record.id}` : null;
  useEffect(() => {
    if (skipNextSourceReset.current) {
      skipNextSourceReset.current = false;
      return;
    }
    if (!source) {
      setTcmd(""); setEresp(""); setRunTest(true); setSavePairToRecord(false);
      return;
    }
    const r = source.record as any;
    setTcmd(normalizeHex(r.test_command ?? ""));
    setEresp(normalizeHex(r.expected_response ?? ""));
    setRunTest(Boolean(r.test_command));
    setSavePairToRecord(false);
  }, [sourceKey]);

  // ----- poll active flash row while running -----
  useEffect(() => {
    let cancelled = false;
    async function fetchOne(id: string) {
      try {
        const row = await getFlash(id);
        if (!cancelled) setLatestFlash(row);
      } catch {
        // ignore
      }
    }
    if (runningFlashId) fetchOne(runningFlashId);
    const tick = window.setInterval(() => {
      if (runningFlashId) fetchOne(runningFlashId);
    }, 1500);
    return () => { cancelled = true; window.clearInterval(tick); };
  }, [runningFlashId]);

  // ----- derived state -----
  const sortedClients = useMemo(() => {
    const arr = [...clients];
    arr.sort((a, b) => Number(b.online) - Number(a.online) || a.name.localeCompare(b.name));
    return arr;
  }, [clients]);
  const onlineCount = clients.filter(c => c.online).length;

  const tcmdValid = tcmd === "" || isValidHex(tcmd);
  const erespValid = eresp === "" || isValidHex(eresp);
  const canFlash = !!(
    client && selectedPort && source &&
    (!runTest || (tcmd && eresp && tcmdValid && erespValid))
  );

  async function onSubmit() {
    if (!canFlash || !source || !client) return;
    setSubmitError(null);
    try {
      const body: any = {
        client,
        port: selectedPort,
        source: { kind: source.kind, id: source.record.id },
        skip_backup: skipBackup,
      };
      if (runTest) {
        body.test_override = { command: tcmd, expected_response: eresp };
        body.save_test_to_record = savePairToRecord && source.kind === "firmware";
      }
      const r = await postFlash(body);
      setRunningFlashId(r.job_id);
    } catch (e: any) {
      setSubmitError(e.body?.detail ?? String(e?.message ?? e));
    }
  }

  const isRunning = latestFlash?.status === "running";

  // ----- step 1: client -----
  const step1Sub = client || "select a host";
  const stepOne = (
    <FlStep
      num={1}
      title="Lab machine"
      state={client ? "done" : "active"}
      sub={step1Sub}
      actions={<FlButton small onClick={() => listClients().then(r => setClients(r.clients))}>Retry probe</FlButton>}
    >
      <div className="shp-field" style={{ gridTemplateColumns: "120px minmax(0, 1fr)" }}>
        <label className="shp-field__label">Client</label>
        <div className="shp-field__col">
          <div className="shp-input-row">
            <FlDropdown
              value={client ?? ""}
              width={320}
              mono
              placeholder="(select…)"
              onChange={v => setClient(v || null)}
              options={sortedClients.map(c => ({
                value: c.name,
                label: c.online ? c.name : `${c.name}  — offline`,
                disabled: !c.online,
              }))}
            />
            <span className="fl-muted fl-mono" style={{ fontSize: 11, whiteSpace: "nowrap" }}>
              {onlineCount} online
            </span>
          </div>
        </div>
      </div>
    </FlStep>
  );

  // ----- step 2: serial port -----
  const stepTwo = client && (
    <FlStep
      num={2}
      title="Serial port"
      state={selectedPort ? "done" : "active"}
      sub={selectedPort ?? (portsLoading ? "loading…" : `${ports.length} ports`)}
      actions={<FlButton small onClick={() => client && refreshPorts(client)} disabled={portsLoading}>Refresh</FlButton>}
    >
      {portsError ? (
        <div className="fl-errblock">
          <span className="fl-errblock__code">Probe failed</span>
          <span className="fl-errblock__msg">{portsError}</span>
        </div>
      ) : ports.length === 0 ? (
        <div className="shp-info-block shp-info-block--neutral">
          <span className="shp-info-block__icon">i</span>
          <span>{portsLoading ? "Loading ports…" : `No serial ports reported by ${client}.`}</span>
        </div>
      ) : (
        <div className="shp-table-wrap">
          <table className="shp-table shp-table--rowselect">
            <thead>
              <tr>
                <th>Port</th>
                <th>Product</th>
                <th>VID:PID</th>
                <th>Serial</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {ports.map(p => {
                const isSelected = p.name === selectedPort;
                const dim = !p.is_usb;
                const vidpid = p.vid && p.pid ? `${p.vid}:${p.pid}` : "";
                return (
                  <tr
                    key={p.name}
                    data-flash-selected={isSelected || undefined}
                    style={{ opacity: dim ? 0.55 : 1 }}
                    onClick={() => setSelectedPort(p.name)}
                  >
                    <td className="shp-strong">{p.name}</td>
                    <td>{p.product || <span className="shp-dim">—</span>}</td>
                    <td>{vidpid || <span className="shp-dim">—</span>}</td>
                    <td>{p.serial_number || <span className="shp-dim">—</span>}</td>
                    <td>
                      {p.discovered
                        ? <span className="fl-instatus" title={p.device_id || undefined}>{p.device_id || "in use"}</span>
                        : <span className="fl-instatus" data-tone="free">free</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </FlStep>
  );

  // ----- step 3: firmware source -----
  const sourceList = sourceKind === "firmware" ? firmwareItems : backupItems;
  const stepThree = selectedPort && (
    <FlStep
      num={3}
      title="Firmware source"
      state={source ? "done" : "active"}
      sub={source ? `${source.kind}: ${source.record.name}` : `pick a ${sourceKind === "firmware" ? "firmware" : "backup"} record`}
      actions={
        <>
          <FlSeg
            value={sourceKind}
            onChange={v => { setSourceKind(v); setSource(null); setTagFilter([]); setSearchTerm(""); }}
            options={[
              { value: "firmware", label: "Firmware" },
              { value: "backups", label: "Backups" },
            ]}
          />
        </>
      }
    >
      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <input
          className="shp-input"
          placeholder="search by name"
          value={searchTerm}
          onChange={e => setSearchTerm(e.target.value)}
          style={{ flex: "1 1 240px", maxWidth: 320 }}
        />
        {sourceKind === "firmware" && tags.length > 0 && (
          <div style={{ display: "flex", gap: 4, flexWrap: "wrap", alignItems: "center" }}>
            {tags.map(t => (
              <FlTag
                key={t.id}
                name={t.name}
                selected={tagFilter.includes(t.id)}
                onClick={() => setTagFilter(s =>
                  s.includes(t.id) ? s.filter(x => x !== t.id) : [...s, t.id]
                )}
              />
            ))}
          </div>
        )}
      </div>
      <div className="fl-srclist">
        {sourceList.length === 0 ? (
          <div className="fl-output__empty" style={{ padding: 32 }}>
            No {sourceKind === "firmware" ? "firmware records" : "backups"} match.
          </div>
        ) : sourceKind === "firmware" ? (
          (sourceList as FirmwareRecord[]).map(f => {
            const isSel = source?.kind === "firmware" && source.record.id === f.id;
            return (
              <div
                key={f.id}
                className="fl-src"
                data-selected={isSel || undefined}
                onClick={() => setSource({ kind: "firmware", record: f })}
              >
                <div className="fl-src__main">
                  <span className="fl-src__name">{f.name}</span>
                  {f.tags.length > 0 && (
                    <span className="fl-src__tags">
                      {f.tags.map(t => (
                        <FlTag key={t.id} name={t.name} />
                      ))}
                    </span>
                  )}
                  <span className="fl-src__meta">
                    sha <b>{f.sha256.slice(0, 12)}</b> · {f.size_bytes} B · flashes: <b>{f.stats.total}</b>
                  </span>
                </div>
              </div>
            );
          })
        ) : (
          (sourceList as BackupRecord[]).map(b => {
            const isSel = source?.kind === "backup" && source.record.id === b.id;
            return (
              <div
                key={b.id}
                className="fl-src"
                data-selected={isSel || undefined}
                onClick={() => setSource({ kind: "backup", record: b })}
              >
                <div className="fl-src__main">
                  <span className="fl-src__name">{b.name}</span>
                  <span className="fl-src__meta">
                    {b.captured_at} · <b>{b.client}</b>/{b.port_name} · sha <b>{b.sha256.slice(0, 12)}</b>
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>
      {source && (
        <div className="fl-srcpicked">
          <span className="fl-srcpicked__lbl">Selected · {source.kind}</span>
          <span className="fl-srcpicked__name">{source.record.name}</span>
          <span className="fl-spacer" />
          <FlButton small variant="ghost" onClick={() => setSource(null)}>Clear</FlButton>
        </div>
      )}
    </FlStep>
  );

  // ----- step 4: test -----
  const stepFour = source && (
    <FlStep
      num={4}
      title="Post-flash test"
      state="active"
      sub={runTest ? "device must reply with expected bytes" : "byte-verify only — no test payload"}
      actions={<FlSwitch on={runTest} onChange={setRunTest} />}
    >
      {runTest ? (
        <>
          <HexEditable label="test_command" value={tcmd} onChange={setTcmd} />
          <HexEditable label="expected_response" value={eresp} onChange={setEresp} />
          {source.kind === "firmware" && (
            <span
              className="shp-checkbox"
              data-checked={savePairToRecord || undefined}
              onClick={() => setSavePairToRecord(v => !v)}
            >
              <span className="shp-checkbox__box">{savePairToRecord ? "✓" : ""}</span>
              <span>Save edits to firmware record</span>
            </span>
          )}
        </>
      ) : (
        <div className="shp-info-block shp-info-block--neutral">
          <span className="shp-info-block__icon">i</span>
          <span>The flash will succeed on byte-verify alone. No payload will be sent to the device after programming.</span>
        </div>
      )}
    </FlStep>
  );

  // ----- step 5: options -----
  const stepFive = source && (
    <FlStep
      num={5}
      title="Options"
      state="active"
      sub={skipBackup ? "⚠ skip backup is ON" : "current flash will be backed up first"}
      actions={<FlToggleLabel on={skipBackup} label="Skip backup" onChange={setSkipBackup} />}
    >
      {skipBackup ? (
        <div className="shp-info-block">
          <span className="shp-info-block__icon">⚠</span>
          <span>The device's existing flash will <b>not</b> be saved. There will be no way to restore the previous firmware from the lab machine if this flash needs to be rolled back.</span>
        </div>
      ) : (
        <div className="shp-info-block shp-info-block--neutral">
          <span className="shp-info-block__icon">i</span>
          <span>The current device flash will be captured to disk on the lab machine before erasing. Adds <b>~8 s</b>.</span>
        </div>
      )}
    </FlStep>
  );

  const submitBar = source && (
    <div className="fl-submit-bar">
      <span className="fl-submit-bar__msg">
        Will release the device on <b>{selectedPort}</b> ({client}), then erase + program + verify{runTest && " + test"}.
      </span>
      <FlButton variant="primary" disabled={!canFlash || isRunning} onClick={onSubmit}>
        Disconnect device and flash
      </FlButton>
    </div>
  );

  const errBlock = submitError && (
    <div className="fl-errblock">
      <span className="fl-errblock__code">Server error</span>
      <span className="fl-errblock__msg">{submitError}</span>
    </div>
  );

  return (
    <FlPage
      title="Flash"
      subtitle="push compiled firmware to a USB-connected microcontroller"
    >
      <div className="fl-flash">
        <div className="fl-flash__col">
          {stepOne}
          {stepTwo}
          {stepThree}
          {stepFour}
          {stepFive}
          {errBlock}
          {submitBar}
        </div>
        <OutputPanel row={latestFlash} isRunning={isRunning} />
      </div>
    </FlPage>
  );
}

function OutputPanel({ row, isRunning }: { row: FlashRowDetail | null; isRunning: boolean }) {
  if (!row) return <OutputEmpty />;
  if (isRunning) return <OutputRunning row={row} />;
  if (row.outcome === "success") return <OutputSuccess row={row} />;
  return <OutputFailure row={row} />;
}

function OutputShell({ title, right, children }: { title: string; right?: ReactNode; children: ReactNode }) {
  return (
    <div className="fl-output">
      <div className="fl-output__head">
        <span className="fl-output__title">{title}</span>
        <span className="fl-spacer" />
        {right}
      </div>
      <div className="fl-output__body">{children}</div>
    </div>
  );
}

function OutputEmpty() {
  return (
    <div className="fl-output">
      <div className="fl-output__head">
        <span className="fl-output__title">Output</span>
        <span className="fl-spacer" />
        <span className="fl-muted fl-mono" style={{ fontSize: 11 }}>idle</span>
      </div>
      <div className="fl-output__empty">
        The Running view + Result will appear here after you submit.
      </div>
    </div>
  );
}

function useElapsed(startedAt: string) {
  const startMsRef = useRef(0);
  const [elapsedMs, setElapsedMs] = useState(0);
  useEffect(() => {
    const start = new Date(startedAt).getTime() || Date.now();
    startMsRef.current = start;
    const tick = () => setElapsedMs(Date.now() - start);
    tick();
    const t = window.setInterval(tick, 500);
    return () => window.clearInterval(t);
  }, [startedAt]);
  return elapsedMs;
}

function OutputRunning({ row }: { row: FlashRowDetail }) {
  const ms = useElapsed(row.started_at);
  const stages = stageStatesFromResult(row.result);
  // mark unset stages as 'active' for the first one not yet ok/failed.
  const computed: Partial<Record<StageName, StageState>> = { ...stages };
  let activated = false;
  for (const s of STAGE_ORDER) {
    if (computed[s] == null) {
      if (!activated) { computed[s] = "active"; activated = true; }
      else computed[s] = "na";
    }
  }
  return (
    <OutputShell
      title="Running"
      right={<span className="fl-muted fl-mono" style={{ fontSize: 11 }}>{formatElapsed(ms)} elapsed</span>}
    >
      <div>
        <div className="fl-running-title">Flashing…</div>
        <div className="fl-running-meta">
          <b>{row.client}</b> · <b>{row.port_name}</b> · {row.firmware_name}
        </div>
      </div>
      <div className="fl-progress" />
      <div style={{ display: "flex", alignItems: "baseline", gap: 8, flexWrap: "wrap" }}>
        <span className="fl-elapsed">{formatElapsed(ms)}</span>
        <span className="fl-muted fl-mono" style={{ fontSize: 11 }}>elapsed</span>
        <span className="fl-spacer" />
        <span className="fl-muted fl-mono" style={{ fontSize: 11 }}>typical 15–30s · max ~60s</span>
      </div>
      <FlStageStrip states={computed} />
      <div className="fl-muted fl-mono" style={{ fontSize: 11, lineHeight: 1.5 }}>
        A flash, once started, runs to completion. Rollback-on-failure is automatic. There is no Cancel.
      </div>
    </OutputShell>
  );
}

function OutputSuccess({ row }: { row: FlashRowDetail }) {
  const tone = outcomeTone(row.outcome, row.status);
  const stages = stageStatesFromResult(row.result);
  return (
    <OutputShell
      title="Result"
      right={<FlOutcome outcome={row.outcome ?? row.status} tone={tone} />}
    >
      <FlStageStrip states={stages} />
      <dl className="fl-dl">
        <dt>Client</dt><dd>{row.client}</dd>
        <dt>Port</dt><dd>{row.port_name}</dd>
        <dt>Firmware</dt><dd>{row.firmware_name} (sha {row.firmware_sha256.slice(0, 12)})</dd>
        <dt>Started</dt><dd>{row.started_at}</dd>
        {row.finished_at && <><dt>Finished</dt><dd>{row.finished_at}</dd></>}
        {row.duration_ms != null && <><dt>Duration</dt><dd>{row.duration_ms} ms</dd></>}
        {row.backup_id && (
          <>
            <dt>Backup ID</dt>
            <dd>
              <Link to="/backups/$id" params={{ id: row.backup_id }}>{row.backup_id}</Link>
            </dd>
          </>
        )}
      </dl>
      {row.result && (
        <details className="fl-details">
          <summary>Raw result JSON</summary>
          <FlJSON data={row.result} />
        </details>
      )}
    </OutputShell>
  );
}

function OutputFailure({ row }: { row: FlashRowDetail }) {
  const tone = outcomeTone(row.outcome, row.status);
  const stages = stageStatesFromResult(row.result);
  const testResult = row.result && (row.result as any).test_result;
  return (
    <OutputShell
      title="Result"
      right={<FlOutcome outcome={row.outcome ?? row.status} tone={tone} />}
    >
      {(row.error_code || row.error_detail) && (
        <div className="fl-errblock">
          {row.error_code && <span className="fl-errblock__code">{row.error_code}</span>}
          {row.error_detail && <span className="fl-errblock__msg">{row.error_detail}</span>}
        </div>
      )}
      <FlStageStrip states={stages} />
      {testResult?.expected != null && testResult?.received != null && (
        <FlHexDiff
          expected={hexBytesArray(testResult.expected)}
          received={hexBytesArray(testResult.received)}
          diffIdx={diffIndicesFromBytes(testResult.expected, testResult.received)}
        />
      )}
      <dl className="fl-dl">
        <dt>Client</dt><dd>{row.client}</dd>
        <dt>Port</dt><dd>{row.port_name}</dd>
        <dt>Firmware</dt><dd>{row.firmware_name} (sha {row.firmware_sha256.slice(0, 12)})</dd>
        <dt>Started</dt><dd>{row.started_at}</dd>
        {row.finished_at && <><dt>Finished</dt><dd>{row.finished_at}</dd></>}
        {row.duration_ms != null && <><dt>Duration</dt><dd>{row.duration_ms} ms</dd></>}
        {row.backup_id && (
          <>
            <dt>Backup ID</dt>
            <dd>
              <Link to="/backups/$id" params={{ id: row.backup_id }}>{row.backup_id}</Link>
            </dd>
          </>
        )}
      </dl>
      {row.result && (
        <details className="fl-details">
          <summary>Raw result JSON</summary>
          <FlJSON data={row.result} />
        </details>
      )}
    </OutputShell>
  );
}

function hexBytesArray(canonical: string): string[] {
  const c = normalizeHex(canonical);
  const out: string[] = [];
  for (let i = 0; i < c.length; i += 2) out.push(c.slice(i, i + 2).toUpperCase());
  return out;
}

function diffIndicesFromBytes(a: string, b: string): number[] {
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
