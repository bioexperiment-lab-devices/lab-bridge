import { useEffect, useState } from "react";
import { createTag, deleteTag, listTags, renameTag } from "../api";
import { Tag } from "../types";

interface Props { open: boolean; onClose: () => void; }

export function TagManager({ open, onClose }: Props) {
  const [tags, setTags] = useState<Tag[]>([]);
  const [newName, setNewName] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function refresh() { setTags((await listTags()).items); }
  useEffect(() => { if (open) refresh(); }, [open]);

  if (!open) return null;
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <header><h3>Tags</h3><button onClick={onClose}>Close</button></header>
        {error ? <div className="error">{error}</div> : null}
        <div className="tag-create-row">
          <input value={newName} onChange={e => setNewName(e.target.value)} placeholder="new tag name" />
          <button
            disabled={!newName.trim()}
            onClick={async () => {
              try { await createTag(newName.trim()); setNewName(""); setError(null); await refresh(); }
              catch (e: any) { setError(e.body?.detail ?? String(e)); }
            }}
          >Create</button>
        </div>
        <ul className="tag-list">
          {tags.map(t => (
            <li key={t.id}>
              {editingId === t.id ? (
                <>
                  <input value={editingName} onChange={e => setEditingName(e.target.value)} />
                  <button onClick={async () => {
                    try { await renameTag(t.id, editingName.trim()); setEditingId(null); setError(null); await refresh(); }
                    catch (e: any) { setError(e.body?.detail ?? String(e)); }
                  }}>Save</button>
                  <button onClick={() => setEditingId(null)}>Cancel</button>
                </>
              ) : (
                <>
                  <span className="tag-name">{t.name}</span>
                  <span className="tag-count">{t.firmware_count ?? 0}</span>
                  <button onClick={() => { setEditingId(t.id); setEditingName(t.name); }}>Rename</button>
                  <button onClick={async () => {
                    if (!confirm(`Delete tag "${t.name}"? This removes it from all firmware records.`)) return;
                    await deleteTag(t.id); await refresh();
                  }}>Delete</button>
                </>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
