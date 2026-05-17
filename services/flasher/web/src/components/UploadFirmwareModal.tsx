import { useEffect, useMemo, useRef, useState } from "react";
import { createFirmware, listTags } from "../api";
import { FirmwareRecord, Tag } from "../types";
import {
  FlBadgeMulti,
  FlButton,
  FlHexInput,
  FlModal,
} from "./Fl";
import {
  asciiPreview,
  formatHexBytes,
  hexByteCount,
  isValidHex,
  normalizeHex,
} from "../hex";

interface Props {
  onClose: () => void;
  onCreated: (row: FirmwareRecord) => void;
  initialFirmware?: string;
  initialFilename?: string;
}

export function UploadFirmwareModal({ onClose, onCreated, initialFirmware = "", initialFilename }: Props) {
  const [name, setName] = useState(initialFilename?.replace(/\.hex$/, "") ?? "");
  const [description, setDescription] = useState("");
  const [tcmd, setTcmd] = useState("");
  const [eresp, setEresp] = useState("");
  const [firmware, setFirmware] = useState(initialFirmware);
  const [originalFilename, setOriginalFilename] = useState<string | null>(initialFilename ?? null);
  const [tags, setTags] = useState<Tag[]>([]);
  const [tagIds, setTagIds] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => { listTags().then(r => setTags(r.items)).catch(() => {}); }, []);

  const tcmdValid = tcmd === "" || isValidHex(tcmd);
  const erespValid = eresp === "" || isValidHex(eresp);

  const tagOptions = useMemo(() => tags.map(t => ({ value: t.id, label: t.name })), [tags]);

  async function onFile(file: File) {
    const text = await file.text();
    setFirmware(text);
    setOriginalFilename(file.name);
    if (!name) setName(file.name.replace(/\.hex$/, ""));
  }

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const row = await createFirmware({
        name,
        description,
        test_command: tcmd || null,
        expected_response: eresp || null,
        firmware,
        original_filename: originalFilename,
        tags: tagIds,
      });
      onCreated(row);
    } catch (e: any) {
      setError(e.body?.detail ?? String(e?.message ?? e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <FlModal
      title="Upload firmware"
      subtitle="creates a new record from a .hex file"
      onClose={onClose}
      width={520}
      footer={
        <>
          <FlButton onClick={onClose} disabled={busy}>Cancel</FlButton>
          <FlButton
            variant="primary"
            onClick={submit}
            disabled={busy || !firmware || !name.trim() || !tcmdValid || !erespValid}
          >
            {busy ? "Uploading…" : "Upload"}
          </FlButton>
        </>
      }
    >
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
        <div className="shp-field" style={{ gridTemplateColumns: "120px minmax(0, 1fr)" }}>
          <label className="shp-field__label">Firmware (.hex)</label>
          <div className="shp-field__col">
            <div className="shp-input-row">
              <FlButton small onClick={() => fileRef.current?.click()}>Choose file…</FlButton>
              <input
                ref={fileRef}
                type="file"
                accept=".hex"
                style={{ display: "none" }}
                onChange={e => e.target.files?.[0] && onFile(e.target.files[0])}
              />
              <span className="fl-mono fl-muted" style={{ fontSize: 11 }}>
                {originalFilename ?? "no file selected"}
              </span>
            </div>
            {firmware && (
              <span className="shp-field__hint">{firmware.length} chars loaded.</span>
            )}
          </div>
        </div>
        <FlHexInput
          label="test_command"
          labelWidth={120}
          value={formatHexBytes(tcmd)}
          bytes={hexByteCount(tcmd)}
          ascii={tcmd && tcmdValid ? asciiPreview(tcmd) : undefined}
          error={tcmd !== "" && !tcmdValid}
          editable
          placeholder="01 02 03"
          onChange={v => setTcmd(normalizeHex(v))}
        />
        <FlHexInput
          label="expected_response"
          labelWidth={120}
          value={formatHexBytes(eresp)}
          bytes={hexByteCount(eresp)}
          ascii={eresp && erespValid ? asciiPreview(eresp) : undefined}
          error={eresp !== "" && !erespValid}
          editable
          placeholder="01 02 03"
          onChange={v => setEresp(normalizeHex(v))}
        />
        <div className="shp-field" style={{ gridTemplateColumns: "120px minmax(0, 1fr)" }}>
          <label className="shp-field__label">Tags</label>
          <div className="shp-field__col">
            <FlBadgeMulti
              selected={tagIds}
              options={tagOptions}
              colorize
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
