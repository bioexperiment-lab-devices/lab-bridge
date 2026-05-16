import { useEffect, useState } from "react";
import { listTags, promoteBackup } from "../api";
import { BackupRecord, FirmwareRecord, Tag } from "../types";

interface Props {
  backup: BackupRecord;
  onCreated: (firmware: FirmwareRecord) => void;
  onClose: () => void;
}

export function PromoteBackupModal({ backup, onCreated, onClose }: Props) {
  const [name, setName] = useState(backup.name);
  const [description, setDescription] = useState(backup.description);
  const [copyPair, setCopyPair] = useState(true);
  const [tags, setTags] = useState<Tag[]>([]);
  const [tagIds, setTagIds] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { listTags().then(r => setTags(r.items)); }, []);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <h3>Promote to firmware</h3>
        <form onSubmit={async (e) => {
          e.preventDefault();
          try {
            const fw = await promoteBackup(backup.id, {
              name, description, copy_test_pair: copyPair, tags: tagIds,
            });
            onCreated(fw);
          } catch (e: any) { setError(e.body?.detail ?? String(e)); }
        }}>
          <label>Name <input required value={name} onChange={e => setName(e.target.value)} /></label>
          <label>Description <textarea value={description} onChange={e => setDescription(e.target.value)} /></label>
          <label>
            <input type="checkbox" checked={copyPair} onChange={e => setCopyPair(e.target.checked)} />
            Copy test pair
          </label>
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
          {error ? <div className="error">{error}</div> : null}
          <div className="actions">
            <button type="submit">Create firmware</button>
            <button type="button" onClick={onClose}>Cancel</button>
          </div>
        </form>
      </div>
    </div>
  );
}
