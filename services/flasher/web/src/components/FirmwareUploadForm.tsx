import { useEffect, useState } from "react";
import { createFirmware, listTags } from "../api";
import { FirmwareRecord, Tag } from "../types";

interface Props {
  initialFirmware?: string;
  initialFilename?: string;
  onCreated: (row: FirmwareRecord) => void;
  onCancel?: () => void;
}

export function FirmwareUploadForm({ initialFirmware = "", initialFilename, onCreated, onCancel }: Props) {
  const [name, setName] = useState(initialFilename?.replace(/\.hex$/, "") ?? "");
  const [description, setDescription] = useState("");
  const [tcmd, setTcmd] = useState("");
  const [eresp, setEresp] = useState("");
  const [firmware, setFirmware] = useState(initialFirmware);
  const [originalFilename, setOriginalFilename] = useState(initialFilename ?? null);
  const [tags, setTags] = useState<Tag[]>([]);
  const [chosenTagIds, setChosenTagIds] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { listTags().then(r => setTags(r.items)); }, []);

  async function onFile(file: File) {
    const text = await file.text();
    setFirmware(text);
    setOriginalFilename(file.name);
    if (!name) setName(file.name.replace(/\.hex$/, ""));
  }

  return (
    <form
      className="firmware-upload-form"
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        setError(null);
        try {
          const row = await createFirmware({
            name, description,
            test_command: tcmd || null,
            expected_response: eresp || null,
            firmware,
            original_filename: originalFilename,
            tags: chosenTagIds,
          });
          onCreated(row);
        } catch (e: any) { setError(e.body?.detail ?? String(e)); }
        finally { setBusy(false); }
      }}
    >
      <label>Name <input required value={name} onChange={e => setName(e.target.value)} /></label>
      <label>Description <textarea value={description} onChange={e => setDescription(e.target.value)} /></label>
      <label>Firmware (.hex)
        <input type="file" accept=".hex" onChange={e => e.target.files?.[0] && onFile(e.target.files[0])} />
      </label>
      {firmware ? <p className="muted">{firmware.length} chars loaded.</p> : null}
      <label>Test command (hex, optional) <input value={tcmd} onChange={e => setTcmd(e.target.value)} /></label>
      <label>Expected response (hex, optional) <input value={eresp} onChange={e => setEresp(e.target.value)} /></label>
      <fieldset>
        <legend>Tags</legend>
        {tags.map(t => (
          <label key={t.id}>
            <input
              type="checkbox"
              checked={chosenTagIds.includes(t.id)}
              onChange={e => setChosenTagIds(s =>
                e.target.checked ? [...s, t.id] : s.filter(x => x !== t.id))}
            />
            {t.name}
          </label>
        ))}
      </fieldset>
      {error ? <div className="error">{error}</div> : null}
      <div className="actions">
        <button type="submit" disabled={busy || !firmware || !name.trim()}>Upload</button>
        {onCancel ? <button type="button" onClick={onCancel}>Cancel</button> : null}
      </div>
    </form>
  );
}
