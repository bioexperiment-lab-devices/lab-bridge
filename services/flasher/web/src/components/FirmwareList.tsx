import { useEffect, useState } from "react";
import { deleteFirmware, downloadFirmwareUrl, listFirmware, listTags } from "../api";
import { FirmwareRecord, Tag } from "../types";
import { TagChip } from "./TagChip";

interface Props {
  onSelect: (row: FirmwareRecord) => void;
  selectedId: string | null;
}

export function FirmwareList({ onSelect, selectedId }: Props) {
  const [items, setItems] = useState<FirmwareRecord[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [tagFilter, setTagFilter] = useState<string[]>([]);
  const [q, setQ] = useState("");

  async function refresh() {
    const r = await listFirmware({ tag: tagFilter, q: q || undefined, limit: 200 });
    setItems(r.items);
  }
  useEffect(() => { refresh(); }, [tagFilter.join(","), q]);
  useEffect(() => { listTags().then(r => setTags(r.items)); }, []);

  return (
    <div className="record-list">
      <div className="filter-bar">
        <input placeholder="search by name" value={q} onChange={e => setQ(e.target.value)} />
        <div className="tag-filter-chips">
          {tags.map(t => (
            <TagChip
              key={t.id} tag={t}
              selected={tagFilter.includes(t.id)}
              onClick={() => setTagFilter(s =>
                s.includes(t.id) ? s.filter(x => x !== t.id) : [...s, t.id])}
            />
          ))}
        </div>
      </div>
      <ul>
        {items.map(row => (
          <li key={row.id} className={selectedId === row.id ? "active" : ""}
              onClick={() => onSelect(row)}>
            <div className="row-name">{row.name}</div>
            <div className="row-tags">{row.tags.map(t => <TagChip key={t.id} tag={t} />)}</div>
            <div className="row-meta">
              {row.sha256.slice(0, 12)} · {row.size_bytes} B · flashes: {row.stats.total}
            </div>
            <div className="row-actions">
              <a href={downloadFirmwareUrl(row.id)} download>Download</a>
              <button onClick={async (e) => {
                e.stopPropagation();
                const refs = row.stats.total;
                if (!confirm(
                  refs === 0
                    ? `Delete firmware "${row.name}"?`
                    : `Delete firmware "${row.name}"? It was used in ${refs} flashes — replay on those rows will fail.`
                )) return;
                try { await deleteFirmware(row.id); await refresh(); }
                catch (e: any) { alert(e.body?.detail ?? String(e)); }
              }}>Delete</button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
