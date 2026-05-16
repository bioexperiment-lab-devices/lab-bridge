import { useEffect, useState } from "react";
import { getFirmware, listFirmwareFlashes, listTags, patchFirmware } from "../api";
import { FirmwareRecord, FlashRowSummary, Tag } from "../types";
import { StatsCard } from "./StatsCard";

interface Props {
  firmwareId: string;
  onOpenFlash: (flashId: string) => void;
}

export function FirmwareDetail({ firmwareId, onOpenFlash }: Props) {
  const [row, setRow] = useState<FirmwareRecord | null>(null);
  const [flashes, setFlashes] = useState<FlashRowSummary[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [tcmd, setTcmd] = useState("");
  const [eresp, setEresp] = useState("");
  const [tagIds, setTagIds] = useState<string[]>([]);

  async function refresh() {
    const r = await getFirmware(firmwareId);
    setRow(r);
    setName(r.name); setDescription(r.description);
    setTcmd(r.test_command ?? ""); setEresp(r.expected_response ?? "");
    setTagIds(r.tags.map(t => t.id));
    const f = await listFirmwareFlashes(firmwareId);
    setFlashes(f.items);
  }
  useEffect(() => { refresh(); }, [firmwareId]);
  useEffect(() => { listTags().then(r => setTags(r.items)); }, []);

  if (!row) return <div>Loading…</div>;
  return (
    <div className="record-detail">
      <h3>{row.name}</h3>
      <p className="muted">sha256 {row.sha256} · {row.size_bytes} B · created {row.created_at}</p>
      <StatsCard stats={row.stats} />
      <form onSubmit={async (e) => {
        e.preventDefault();
        await patchFirmware(firmwareId, {
          name, description,
          test_command: tcmd || null,
          expected_response: eresp || null,
          tags: tagIds,
        });
        await refresh();
      }}>
        <label>Name <input value={name} onChange={e => setName(e.target.value)} /></label>
        <label>Description <textarea value={description} onChange={e => setDescription(e.target.value)} /></label>
        <label>Test command <input value={tcmd} onChange={e => setTcmd(e.target.value)} /></label>
        <label>Expected response <input value={eresp} onChange={e => setEresp(e.target.value)} /></label>
        <fieldset>
          <legend>Tags</legend>
          {tags.map(t => (
            <label key={t.id}>
              <input type="checkbox" checked={tagIds.includes(t.id)}
                     onChange={e => setTagIds(s => e.target.checked
                       ? [...s, t.id] : s.filter(x => x !== t.id))} />
              {t.name}
            </label>
          ))}
        </fieldset>
        <button type="submit">Save</button>
      </form>
      <h4>Flash history</h4>
      <ul className="flash-mini-list">
        {flashes.map(f => (
          <li key={f.id} onClick={() => onOpenFlash(f.id)}>
            {f.started_at} · {f.client} · {f.port_name} · {f.outcome ?? f.status}
            {f.duration_ms ? ` · ${(f.duration_ms / 1000).toFixed(1)}s` : ""}
          </li>
        ))}
      </ul>
    </div>
  );
}
