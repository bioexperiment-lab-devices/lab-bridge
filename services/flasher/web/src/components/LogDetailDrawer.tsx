import { useEffect, useState } from "react";
import { getFlash, listClients, patchFlashNote, replayFlash } from "../api";
import { ClientEntry, FlashRowDetail } from "../types";
import { StageStrip } from "./StageStrip";
import { HexDiff } from "./HexDiff";

interface Props {
  flashId: string;
  onClose: () => void;
}

export function LogDetailDrawer({ flashId, onClose }: Props) {
  const [row, setRow] = useState<FlashRowDetail | null>(null);
  const [note, setNote] = useState("");
  const [clients, setClients] = useState<ClientEntry[]>([]);
  const [replayClient, setReplayClient] = useState<string>("");
  const [replayPort, setReplayPort] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    const r = await getFlash(flashId);
    setRow(r); setNote(r.operator_note);
    setReplayClient(r.client); setReplayPort(r.port_name);
  }
  useEffect(() => { refresh(); }, [flashId]);
  useEffect(() => { listClients().then(r => setClients(r.clients)); }, []);

  if (!row) return null;
  const stages = (row.result && (row.result as any).stages) || {};
  const testResult = row.result && (row.result as any).test_result;

  return (
    <aside className="drawer">
      <header><h3>Flash {row.id.slice(0, 8)}</h3><button onClick={onClose}>Close</button></header>
      <dl className="meta-grid">
        <dt>Started</dt><dd>{row.started_at}</dd>
        <dt>Status</dt><dd>{row.status} ({row.outcome ?? "—"})</dd>
        <dt>Client / port</dt><dd>{row.client} · {row.port_name}</dd>
        <dt>Firmware</dt><dd>{row.firmware_name} (sha {row.firmware_sha256.slice(0, 12)})</dd>
        <dt>Source kind</dt><dd>{row.source_kind}</dd>
      </dl>
      <StageStrip stages={stages} />
      {testResult ? (
        <HexDiff expected={testResult.expected} received={testResult.received} />
      ) : null}
      <details><summary>Raw JSON</summary><pre>{JSON.stringify(row.result ?? {}, null, 2)}</pre></details>
      <form onSubmit={async (e) => {
        e.preventDefault();
        try { await patchFlashNote(flashId, note); await refresh(); }
        catch (e: any) { setError(e.body?.detail ?? String(e)); }
      }}>
        <label>Operator note <textarea value={note} onChange={e => setNote(e.target.value)} /></label>
        <button type="submit">Save note</button>
        {error ? <div className="error">{error}</div> : null}
      </form>
      <h4>Repeat this flash</h4>
      <div className="replay-controls">
        <label>Client <select value={replayClient} onChange={e => setReplayClient(e.target.value)}>
          {clients.map(c => <option key={c.name} value={c.name} disabled={!c.online}>
            {c.name}{c.online ? "" : " (offline)"}
          </option>)}
        </select></label>
        <label>Port <input value={replayPort} onChange={e => setReplayPort(e.target.value)} /></label>
        <button onClick={async () => {
          try {
            await replayFlash(flashId, { client: replayClient, port: replayPort });
            onClose();
          } catch (e: any) {
            if (e.status === 410) alert("Source firmware/backup has been deleted — cannot replay.");
            else alert(e.body?.detail ?? String(e));
          }
        }}>Repeat</button>
      </div>
    </aside>
  );
}
