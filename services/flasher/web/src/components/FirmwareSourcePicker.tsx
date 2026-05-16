import { useEffect, useState } from "react";
import { listBackups, listFirmware, listTags } from "../api";
import { BackupRecord, FirmwareRecord, Tag } from "../types";
import { FirmwareUploadForm } from "./FirmwareUploadForm";
import { TagChip } from "./TagChip";

export type FlashSource =
  | { kind: "firmware"; record: FirmwareRecord }
  | { kind: "backup"; record: BackupRecord };

interface Props {
  value: FlashSource | null;
  onChange: (next: FlashSource | null) => void;
}

export function FirmwareSourcePicker({ value, onChange }: Props) {
  const [segment, setSegment] = useState<"firmware" | "backups">("firmware");
  const [firmwareItems, setFirmwareItems] = useState<FirmwareRecord[]>([]);
  const [backupItems, setBackupItems] = useState<BackupRecord[]>([]);
  const [q, setQ] = useState("");
  const [tags, setTags] = useState<Tag[]>([]);
  const [tagFilter, setTagFilter] = useState<string[]>([]);
  const [uploadOpen, setUploadOpen] = useState(false);

  async function refresh() {
    if (segment === "firmware") {
      setFirmwareItems((await listFirmware({
        q: q || undefined, tag: tagFilter, limit: 200,
      })).items);
    } else {
      setBackupItems((await listBackups({ q: q || undefined, limit: 200 })).items);
    }
  }
  useEffect(() => { refresh(); }, [segment, q, tagFilter.join(",")]);
  useEffect(() => { listTags().then(r => setTags(r.items)); }, []);

  return (
    <div className="firmware-source-picker">
      <div className="segment-bar">
        <button className={segment === "firmware" ? "active" : ""}
                onClick={() => setSegment("firmware")}>Firmware</button>
        <button className={segment === "backups" ? "active" : ""}
                onClick={() => setSegment("backups")}>Backups</button>
        <button onClick={() => setUploadOpen(true)}>+ Create new firmware</button>
      </div>
      <input className="search" placeholder="search by name"
             value={q} onChange={e => setQ(e.target.value)} />
      {segment === "firmware" ? (
        <div className="tag-filter-chips">
          {tags.map(t => (
            <TagChip key={t.id} tag={t}
                     selected={tagFilter.includes(t.id)}
                     onClick={() => setTagFilter(s =>
                       s.includes(t.id) ? s.filter(x => x !== t.id) : [...s, t.id])} />
          ))}
        </div>
      ) : null}
      <ul className="source-list">
        {segment === "firmware" ? firmwareItems.map(f => (
          <li key={f.id}
              className={value?.kind === "firmware" && value.record.id === f.id ? "active" : ""}
              onClick={() => onChange({ kind: "firmware", record: f })}>
            <div className="row-name">{f.name}</div>
            <div className="row-tags">{f.tags.map(t => <TagChip key={t.id} tag={t} />)}</div>
            <div className="row-meta">sha {f.sha256.slice(0,12)} · {f.size_bytes} B</div>
          </li>
        )) : backupItems.map(b => (
          <li key={b.id}
              className={value?.kind === "backup" && value.record.id === b.id ? "active" : ""}
              onClick={() => onChange({ kind: "backup", record: b })}>
            <div className="row-name">{b.name}</div>
            <div className="row-meta">
              {b.captured_at} · {b.client}/{b.port_name} · sha {b.sha256.slice(0,12)}
            </div>
          </li>
        ))}
      </ul>
      {value ? (
        <div className="selected-source">
          <strong>Selected:</strong> {value.kind} — {value.record.name}
          <button onClick={() => onChange(null)}>Clear</button>
        </div>
      ) : null}
      {uploadOpen ? (
        <div className="modal-backdrop" onClick={() => setUploadOpen(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3>Create new firmware</h3>
            <FirmwareUploadForm
              onCreated={row => {
                setUploadOpen(false);
                onChange({ kind: "firmware", record: row });
              }}
              onCancel={() => setUploadOpen(false)}
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}
