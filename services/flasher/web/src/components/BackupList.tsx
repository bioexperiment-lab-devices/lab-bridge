import { useEffect, useState } from "react";
import { bulkDeleteBackups, deleteBackup, downloadBackupUrl, listBackups, listClients } from "../api";
import { BackupRecord, ClientEntry } from "../types";

interface Props {
  onSelect: (row: BackupRecord) => void;
  onPromote: (row: BackupRecord) => void;
  selectedId: string | null;
}

export function BackupList({ onSelect, onPromote, selectedId }: Props) {
  const [items, setItems] = useState<BackupRecord[]>([]);
  const [clients, setClients] = useState<ClientEntry[]>([]);
  const [clientFilter, setClientFilter] = useState<string | "">("");
  const [q, setQ] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  async function refresh() {
    const r = await listBackups({ client: clientFilter || undefined, q: q || undefined, limit: 200 });
    setItems(r.items); setSelectedIds(new Set());
  }
  useEffect(() => { refresh(); }, [clientFilter, q]);
  useEffect(() => { listClients().then(r => setClients(r.clients)); }, []);

  return (
    <div className="record-list">
      <div className="filter-bar">
        <input placeholder="search by name" value={q} onChange={e => setQ(e.target.value)} />
        <select value={clientFilter} onChange={e => setClientFilter(e.target.value)}>
          <option value="">(any client)</option>
          {clients.map(c => <option key={c.name} value={c.name}>{c.name}</option>)}
        </select>
        <button
          disabled={selectedIds.size === 0}
          onClick={async () => {
            if (!confirm(`Delete ${selectedIds.size} backups?`)) return;
            const result = await bulkDeleteBackups(Array.from(selectedIds));
            if (result.refused.length) alert(
              `Refused:\n${result.refused.map(r => `${r.id}: ${r.reason}`).join("\n")}`,
            );
            await refresh();
          }}
        >Delete selected ({selectedIds.size})</button>
      </div>
      <ul>
        {items.map(row => (
          <li key={row.id} className={selectedId === row.id ? "active" : ""}
              onClick={() => onSelect(row)}>
            <input type="checkbox" checked={selectedIds.has(row.id)}
                   onClick={e => e.stopPropagation()}
                   onChange={e => setSelectedIds(s => {
                     const n = new Set(s);
                     if (e.target.checked) n.add(row.id); else n.delete(row.id);
                     return n;
                   })} />
            <div className="row-name">{row.name}</div>
            <div className="row-meta">
              {row.captured_at} · {row.client} · {row.port_name} ·
              {row.product ?? `${row.vid}:${row.pid}`} ·
              sha {row.sha256.slice(0, 12)} ·
              flashes: {row.stats.total}
            </div>
            <div className="row-actions">
              <a href={downloadBackupUrl(row.id)} download>Download</a>
              <button onClick={e => { e.stopPropagation(); onPromote(row); }}>Promote</button>
              <button onClick={async e => {
                e.stopPropagation();
                if (!confirm(`Delete backup "${row.name}"?`)) return;
                try { await deleteBackup(row.id); await refresh(); }
                catch (e: any) { alert(e.body?.detail ?? String(e)); }
              }}>Delete</button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
