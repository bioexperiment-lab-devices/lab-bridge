import { useEffect, useMemo, useState } from "react";
import {
  deleteFirmware,
  downloadFirmwareUrl,
  getFirmware,
  listFirmware,
  listFirmwareFlashes,
  listTags,
  patchFirmware,
} from "../api";
import {
  FlBadgeMulti,
  FlButton,
  FlOutc,
  FlPage,
  FlStatsCard,
  FlTag,
  outcomeTone,
} from "../components/Fl";
import {
  asciiPreview,
  formatHexBytes,
  hexByteCount,
  isValidHex,
  normalizeHex,
} from "../hex";
import { FirmwareRecord, FlashRowSummary, Tag } from "../types";
import { UploadFirmwareModal } from "../components/UploadFirmwareModal";
import { TagManagerModal } from "../components/TagManagerModal";
import { LogDetailDrawer } from "../components/LogDetailDrawer";
import { FlHexInput } from "../components/Fl";

export function FirmwareTab() {
  const [list, setList] = useState<FirmwareRecord[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [tagFilter, setTagFilter] = useState<string[]>([]);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [tagsOpen, setTagsOpen] = useState(false);
  const [openFlashId, setOpenFlashId] = useState<string | null>(null);

  async function refresh() {
    const r = await listFirmware({ q: search || undefined, tag: tagFilter, limit: 200 });
    setList(r.items);
  }
  useEffect(() => { refresh(); }, [search, tagFilter.join(",")]);
  useEffect(() => { listTags().then(r => setTags(r.items)).catch(() => {}); }, []);

  const totalBytes = list.reduce((acc, f) => acc + f.size_bytes, 0);

  return (
    <FlPage
      title="Firmware"
      subtitle={`${list.length} records · ${formatBytes(totalBytes)} total`}
      actions={
        <>
          <FlButton small onClick={() => setTagsOpen(true)}>Manage tags</FlButton>
          <FlButton
            small
            variant="primary"
            leading={<span style={{ fontWeight: 600, fontSize: 13, lineHeight: 1 }}>+</span>}
            onClick={() => setUploadOpen(true)}
          >
            Upload firmware
          </FlButton>
        </>
      }
    >
      <div className="fl-twopane">
        <div className="fl-pane">
          <div className="fl-pane__head">
            <div className="fl-pane__searchrow">
              <input
                className="shp-input"
                placeholder="search by name"
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
            </div>
            <div className="fl-pane__tags">
              {tags.map(t => (
                <FlTag
                  key={t.id}
                  name={t.name}
                  selected={tagFilter.includes(t.id)}
                  onClick={() => setTagFilter(s =>
                    s.includes(t.id) ? s.filter(x => x !== t.id) : [...s, t.id]
                  )}
                />
              ))}
            </div>
          </div>
          <div className="fl-pane__body">
            {list.length === 0 ? (
              <div className="fl-output__empty" style={{ padding: 32 }}>
                No firmware records match.
              </div>
            ) : list.map(f => (
              <div
                key={f.id}
                className="fl-row"
                data-selected={f.id === selectedId || undefined}
                onClick={() => setSelectedId(f.id)}
              >
                <span />
                <div className="fl-row__main">
                  <span className="fl-row__name">{f.name}</span>
                  {f.tags.length > 0 && (
                    <span className="fl-row__tags">
                      {f.tags.map(t => (
                        <FlTag key={t.id} name={t.name} />
                      ))}
                    </span>
                  )}
                  <span className="fl-row__meta">
                    {f.sha256.slice(0, 12)} · {f.size_bytes} B · flashes: <b>{f.stats.total}</b>
                  </span>
                </div>
                <div className="fl-row__actions" onClick={e => e.stopPropagation()}>
                  <a className="shp-btn shp-btn--ghost shp-btn--sm" href={downloadFirmwareUrl(f.id)} download>
                    Download
                  </a>
                  <FlButton
                    small
                    variant="ghost"
                    onClick={async () => {
                      const refs = f.stats.total;
                      const msg = refs === 0
                        ? `Delete firmware "${f.name}"?`
                        : `Delete firmware "${f.name}"? It was used in ${refs} flashes — replay on those rows will fail.`;
                      if (!confirm(msg)) return;
                      try {
                        await deleteFirmware(f.id);
                        if (selectedId === f.id) setSelectedId(null);
                        await refresh();
                      } catch (e: any) {
                        alert(e.body?.detail ?? String(e?.message ?? e));
                      }
                    }}
                  >
                    <span style={{ color: "var(--danger)" }}>Delete</span>
                  </FlButton>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="fl-pane">
          {selectedId ? (
            <FirmwareDetail
              firmwareId={selectedId}
              allTags={tags}
              onOpenFlash={setOpenFlashId}
              onSaved={refresh}
            />
          ) : (
            <DetailPlaceholder text="Select a firmware record on the left." />
          )}
        </div>
      </div>

      {uploadOpen && (
        <UploadFirmwareModal
          onClose={() => setUploadOpen(false)}
          onCreated={row => {
            setUploadOpen(false);
            setSelectedId(row.id);
            refresh();
          }}
        />
      )}
      {tagsOpen && <TagManagerModal onClose={() => { setTagsOpen(false); listTags().then(r => setTags(r.items)); refresh(); }} />}
      {openFlashId && <LogDetailDrawer flashId={openFlashId} onClose={() => setOpenFlashId(null)} />}
    </FlPage>
  );
}

export function DetailPlaceholder({ text }: { text: string }) {
  return (
    <div className="fl-detail__placeholder">
      <div className="fl-output__empty-icon">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="11" cy="11" r="7" />
          <path d="M20 20l-3.5-3.5" />
        </svg>
      </div>
      {text}
    </div>
  );
}

function FirmwareDetail({
  firmwareId,
  allTags,
  onOpenFlash,
  onSaved,
}: {
  firmwareId: string;
  allTags: Tag[];
  onOpenFlash: (id: string) => void;
  onSaved: () => void;
}) {
  const [row, setRow] = useState<FirmwareRecord | null>(null);
  const [flashes, setFlashes] = useState<FlashRowSummary[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [tcmd, setTcmd] = useState("");
  const [eresp, setEresp] = useState("");
  const [tagIds, setTagIds] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setError(null);
    try {
      const r = await getFirmware(firmwareId);
      setRow(r);
      resetForm(r);
      const f = await listFirmwareFlashes(firmwareId);
      setFlashes(f.items);
    } catch (e: any) {
      setError(e.body?.detail ?? String(e?.message ?? e));
    }
  }
  function resetForm(r: FirmwareRecord) {
    setName(r.name);
    setDescription(r.description);
    setTcmd(normalizeHex(r.test_command ?? ""));
    setEresp(normalizeHex(r.expected_response ?? ""));
    setTagIds(r.tags.map(t => t.id));
  }
  useEffect(() => { refresh(); }, [firmwareId]);

  const tagOptions = useMemo(
    () => allTags.map(t => ({ value: t.id, label: t.name })),
    [allTags],
  );

  if (!row) {
    return <div className="fl-detail__placeholder">{error ?? "Loading…"}</div>;
  }

  const tcmdValid = tcmd === "" || isValidHex(tcmd);
  const erespValid = eresp === "" || isValidHex(eresp);

  const dirty =
    name !== row.name ||
    description !== row.description ||
    tcmd !== normalizeHex(row.test_command ?? "") ||
    eresp !== normalizeHex(row.expected_response ?? "") ||
    JSON.stringify([...tagIds].sort()) !== JSON.stringify(row.tags.map(t => t.id).sort());

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await patchFirmware(firmwareId, {
        name,
        description,
        test_command: tcmd || null,
        expected_response: eresp || null,
        tags: tagIds,
      });
      await refresh();
      onSaved();
    } catch (e: any) {
      setError(e.body?.detail ?? String(e?.message ?? e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <div className="fl-detail__head">
        <h2 className="fl-detail__h">{row.name}</h2>
        <div className="fl-detail__sub">
          sha256 {row.sha256} · {row.size_bytes} B · created {row.created_at}
        </div>
      </div>
      <div className="fl-detail__body">
        <FlStatsCard
          total={row.stats.total}
          successes={row.stats.successes}
          rollbacks={row.stats.rollbacks}
          failures={row.stats.failures}
          lastFlashed={row.stats.last_flashed_at
            ? `${row.stats.last_flashed_at} · ${row.stats.last_flashed_client} · ${row.stats.last_flashed_port}`
            : null}
        />

        <div>
          <div className="fl-dh">Edit</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div className="shp-field" style={{ gridTemplateColumns: "140px minmax(0, 1fr)" }}>
              <label className="shp-field__label">Name</label>
              <div className="shp-field__col">
                <input className="shp-input" value={name} onChange={e => setName(e.target.value)} />
              </div>
            </div>
            <div className="shp-field" style={{ gridTemplateColumns: "140px minmax(0, 1fr)", alignItems: "start" }}>
              <label className="shp-field__label">Description</label>
              <div className="shp-field__col">
                <textarea
                  className="shp-input"
                  rows={2}
                  style={{ height: "auto", paddingTop: 6, paddingBottom: 6, resize: "vertical" }}
                  value={description}
                  onChange={e => setDescription(e.target.value)}
                />
              </div>
            </div>
            <FlHexInput
              label="test_command"
              labelWidth={140}
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
              labelWidth={140}
              value={formatHexBytes(eresp)}
              bytes={hexByteCount(eresp)}
              ascii={eresp && erespValid ? asciiPreview(eresp) : undefined}
              error={eresp !== "" && !erespValid}
              editable
              placeholder="01 02 03"
              onChange={v => setEresp(normalizeHex(v))}
            />
            <div className="shp-field" style={{ gridTemplateColumns: "140px minmax(0, 1fr)" }}>
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
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <FlButton small variant="ghost" disabled={!dirty || saving} onClick={() => resetForm(row)}>
                Revert
              </FlButton>
              <FlButton
                small
                variant="primary"
                disabled={!dirty || saving || !tcmdValid || !erespValid || !name.trim()}
                onClick={save}
              >
                {saving ? "Saving…" : "Save"}
              </FlButton>
            </div>
          </div>
        </div>

        <div>
          <div className="fl-dh">Flash history · {flashes.length}</div>
          {flashes.length === 0 ? (
            <div className="fl-muted fl-mono" style={{ fontSize: 11.5 }}>
              No flashes have used this firmware yet.
            </div>
          ) : (
            <div className="fl-hist-list">
              {flashes.map(h => (
                <div key={h.id} className="fl-hist" onClick={() => onOpenFlash(h.id)}>
                  <span className="fl-hist__time">{h.started_at}</span>
                  <span>{h.client}</span>
                  <span className="fl-hist__src">{h.port_name}</span>
                  <FlOutc outcome={h.outcome ?? h.status} tone={outcomeTone(h.outcome, h.status)} />
                  <span className="fl-hist__dur">{formatDuration(h.duration_ms)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function formatDuration(ms: number | null): string {
  if (ms == null) return "—";
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}
