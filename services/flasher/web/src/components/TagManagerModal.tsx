import { useEffect, useState } from "react";
import { createTag, deleteTag, listTags, renameTag } from "../api";
import { Tag } from "../types";
import { FlButton, FlModal, FlTag, toneForTag } from "./Fl";

export function TagManagerModal({ onClose }: { onClose: () => void }) {
  const [tags, setTags] = useState<Tag[]>([]);
  const [newName, setNewName] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try { setTags((await listTags()).items); }
    catch (e: any) { setError(e.body?.detail ?? String(e?.message ?? e)); }
  }
  useEffect(() => { refresh(); }, []);

  return (
    <FlModal
      title="Tags"
      subtitle={`${tags.length} tag${tags.length === 1 ? "" : "s"}`}
      onClose={onClose}
      width={460}
      footer={<FlButton variant="primary" onClick={onClose}>Done</FlButton>}
    >
      {error && <div className="fl-errblock" style={{ marginBottom: 12 }}>
        <span className="fl-errblock__msg">{error}</span>
      </div>}
      <div className="shp-input-row" style={{ marginBottom: 12 }}>
        <input
          className="shp-input"
          placeholder="new tag name"
          value={newName}
          onChange={e => setNewName(e.target.value)}
          onKeyDown={async e => {
            if (e.key === "Enter" && newName.trim()) {
              try { await createTag(newName.trim()); setNewName(""); setError(null); await refresh(); }
              catch (err: any) { setError(err.body?.detail ?? String(err?.message ?? err)); }
            }
          }}
        />
        <FlButton
          variant="primary"
          disabled={!newName.trim()}
          onClick={async () => {
            try { await createTag(newName.trim()); setNewName(""); setError(null); await refresh(); }
            catch (err: any) { setError(err.body?.detail ?? String(err?.message ?? err)); }
          }}
        >
          Create
        </FlButton>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {tags.map(t => (
          <div
            key={t.id}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "8px 4px",
              borderBottom: "1px solid var(--border)",
            }}
          >
            {editingId === t.id ? (
              <>
                <input
                  className="shp-input"
                  value={editingName}
                  autoFocus
                  onChange={e => setEditingName(e.target.value)}
                />
                <FlButton small variant="primary" onClick={async () => {
                  try { await renameTag(t.id, editingName.trim()); setEditingId(null); setError(null); await refresh(); }
                  catch (err: any) { setError(err.body?.detail ?? String(err?.message ?? err)); }
                }}>Save</FlButton>
                <FlButton small onClick={() => setEditingId(null)}>Cancel</FlButton>
              </>
            ) : (
              <>
                <FlTag name={t.name} tone={toneForTag(t.name)} />
                <span className="fl-muted fl-mono" style={{ fontSize: 11 }}>
                  {t.firmware_count ?? 0} firmware
                </span>
                <span className="fl-spacer" />
                <FlButton small variant="ghost" onClick={() => { setEditingId(t.id); setEditingName(t.name); }}>
                  Rename
                </FlButton>
                <FlButton
                  small
                  variant="ghost"
                  onClick={async () => {
                    if (!confirm(`Delete tag "${t.name}"? This removes it from all firmware records.`)) return;
                    try { await deleteTag(t.id); await refresh(); }
                    catch (err: any) { setError(err.body?.detail ?? String(err?.message ?? err)); }
                  }}
                >
                  <span style={{ color: "var(--danger)" }}>Delete</span>
                </FlButton>
              </>
            )}
          </div>
        ))}
        {tags.length === 0 && (
          <div className="fl-muted fl-mono" style={{ fontSize: 11.5, padding: 12 }}>
            No tags yet.
          </div>
        )}
      </div>
    </FlModal>
  );
}
