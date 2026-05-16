import { useEffect, useState } from "react";
import { getBackup, listBackupFlashes, patchBackup } from "../api";
import { BackupRecord, FlashRowSummary } from "../types";
import { StatsCard } from "./StatsCard";

interface Props {
  backupId: string;
  onOpenFlash: (flashId: string) => void;
}

export function BackupDetail({ backupId, onOpenFlash }: Props) {
  const [row, setRow] = useState<BackupRecord | null>(null);
  const [flashes, setFlashes] = useState<FlashRowSummary[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [tcmd, setTcmd] = useState("");
  const [eresp, setEresp] = useState("");

  async function refresh() {
    const r = await getBackup(backupId);
    setRow(r);
    setName(r.name); setDescription(r.description);
    setTcmd(r.test_command ?? ""); setEresp(r.expected_response ?? "");
    setFlashes((await listBackupFlashes(backupId)).items);
  }
  useEffect(() => { refresh(); }, [backupId]);
  if (!row) return <div>Loading…</div>;

  return (
    <div className="record-detail">
      <h3>{row.name}</h3>
      <p className="muted">
        sha256 {row.sha256} · {row.size_bytes} B · captured {row.captured_at}
      </p>
      <dl className="meta-grid">
        <dt>Client</dt><dd>{row.client}</dd>
        <dt>Port</dt><dd>{row.port_name}</dd>
        <dt>VID:PID</dt><dd>{row.vid}:{row.pid}</dd>
        <dt>Serial #</dt><dd>{row.serial_number || "—"}</dd>
        <dt>Product</dt><dd>{row.product || "—"}</dd>
        <dt>SerialHop path</dt><dd>{row.serialhop_saved_path}</dd>
      </dl>
      <StatsCard stats={row.stats} />
      <form onSubmit={async (e) => {
        e.preventDefault();
        await patchBackup(backupId, {
          name, description,
          test_command: tcmd || null,
          expected_response: eresp || null,
        });
        await refresh();
      }}>
        <label>Name <input value={name} onChange={e => setName(e.target.value)} /></label>
        <label>Description <textarea value={description} onChange={e => setDescription(e.target.value)} /></label>
        <label>Test command <input value={tcmd} onChange={e => setTcmd(e.target.value)} /></label>
        <label>Expected response <input value={eresp} onChange={e => setEresp(e.target.value)} /></label>
        <button type="submit">Save</button>
      </form>
      <h4>Used by flashes</h4>
      <ul className="flash-mini-list">
        {flashes.map(f => (
          <li key={f.id} onClick={() => onOpenFlash(f.id)}>
            {f.started_at} · {f.client} · {f.port_name} · {f.outcome ?? f.status}
          </li>
        ))}
      </ul>
    </div>
  );
}
