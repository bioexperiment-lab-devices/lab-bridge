import { useEffect, useMemo, useState } from "react";
import { listTags, promoteBackup } from "../api";
import { BackupRecord, FirmwareRecord, Tag } from "../types";
import { FlBadgeMulti, FlButton, FlModal, toneForTag } from "./Fl";

interface Props {
  backup: BackupRecord;
  onCreated: (firmware: FirmwareRecord) => void;
  onClose: () => void;
}

export function PromoteBackupModal({ backup, onCreated, onClose }: Props) {
  const [name, setName] = useState(backup.name);
  const [description, setDescription] = useState(backup.description);
  const [copyPair, setCopyPair] = useState(Boolean(backup.test_command));
  const [tags, setTags] = useState<Tag[]>([]);
  const [tagIds, setTagIds] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { listTags().then(r => setTags(r.items)).catch(() => {}); }, []);

  const tagOptions = useMemo(() => tags.map(t => ({ value: t.id, label: t.name })), [tags]);
  const idToName = useMemo(() => {
    const m = new Map<string, string>();
    tags.forEach(t => m.set(t.id, t.name));
    return m;
  }, [tags]);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const fw = await promoteBackup(backup.id, {
        name,
        description,
        copy_test_pair: copyPair,
        tags: tagIds,
      });
      onCreated(fw);
    } catch (e: any) {
      setError(e.body?.detail ?? String(e?.message ?? e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <FlModal
      title="Promote backup to firmware"
      subtitle={backup.name}
      onClose={onClose}
      width={500}
      footer={
        <>
          <FlButton onClick={onClose} disabled={busy}>Cancel</FlButton>
          <FlButton variant="primary" onClick={submit} disabled={busy || !name.trim()}>
            {busy ? "Creating…" : "Create firmware"}
          </FlButton>
        </>
      }
    >
      <p style={{ marginTop: 0, marginBottom: 12, fontSize: 12.5, color: "var(--text)" }}>
        Creating a firmware record lets this backup be flashed onto <b>other</b> devices and tagged like any normal firmware.
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <div className="shp-field" style={{ gridTemplateColumns: "120px minmax(0, 1fr)" }}>
          <label className="shp-field__label">Name</label>
          <div className="shp-field__col">
            <input className="shp-input" value={name} onChange={e => setName(e.target.value)} />
          </div>
        </div>
        <div className="shp-field" style={{ gridTemplateColumns: "120px minmax(0, 1fr)", alignItems: "start" }}>
          <label className="shp-field__label">Description</label>
          <div className="shp-field__col">
            <textarea
              className="shp-input"
              rows={2}
              style={{ height: "auto", padding: "6px 10px", resize: "vertical" }}
              value={description}
              onChange={e => setDescription(e.target.value)}
            />
          </div>
        </div>
        {backup.test_command && (
          <div className="shp-field" style={{ gridTemplateColumns: "120px minmax(0, 1fr)" }}>
            <label className="shp-field__label">Test pair</label>
            <div className="shp-field__col">
              <span
                className="shp-checkbox"
                data-checked={copyPair || undefined}
                onClick={() => setCopyPair(v => !v)}
              >
                <span className="shp-checkbox__box">{copyPair ? "✓" : ""}</span>
                <span>Copy test_command + expected_response from the backup</span>
              </span>
            </div>
          </div>
        )}
        <div className="shp-field" style={{ gridTemplateColumns: "120px minmax(0, 1fr)" }}>
          <label className="shp-field__label">Tags</label>
          <div className="shp-field__col">
            <FlBadgeMulti
              selected={tagIds}
              options={tagOptions}
              toneFor={(id) => toneForTag(idToName.get(id) ?? "")}
              onAdd={id => setTagIds(s => s.includes(id) ? s : [...s, id])}
              onRemove={id => setTagIds(s => s.filter(x => x !== id))}
              addLabel="Add tag"
              emptyLabel="no tags"
            />
          </div>
        </div>
        {error && <div className="fl-errblock"><span className="fl-errblock__msg">{error}</span></div>}
      </div>
    </FlModal>
  );
}
