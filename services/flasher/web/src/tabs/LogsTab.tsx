import { useEffect, useMemo, useRef, useState } from "react";
import { listClients, listFirmware, listFlashes } from "../api";
import {
  FlBadgeMulti,
  FlButton,
  FlDateInput,
  FlDropdown,
  FlOutc,
  FlPage,
  outcomeTone,
} from "../components/Fl";
import { LogDetailDrawer } from "../components/LogDetailDrawer";
import {
  ClientEntry,
  FirmwareRecord,
  FlashFilters,
  FlashRowSummary,
} from "../types";

const OUTCOMES = [
  "success",
  "rolled_back_verify_failed",
  "rolled_back_test_failed",
  "failed_preflight",
  "failed_backup",
  "failed_no_recovery",
  "error",
  "interrupted",
];

export function LogsTab() {
  const [filters, setFilters] = useState<FlashFilters>({});
  const [openFlashId, setOpenFlashId] = useState<string | null>(null);

  return (
    <FlPage title="Logs" subtitle="every flash run — most recent first">
      <LogFilters value={filters} onChange={setFilters} />
      <LogTable filters={filters} onOpen={setOpenFlashId} selectedId={openFlashId} />
      {openFlashId && <LogDetailDrawer flashId={openFlashId} onClose={() => setOpenFlashId(null)} />}
    </FlPage>
  );
}

function LogFilters({ value, onChange }: { value: FlashFilters; onChange: (f: FlashFilters) => void }) {
  const [clients, setClients] = useState<ClientEntry[]>([]);
  const [firmware, setFirmware] = useState<FirmwareRecord[]>([]);

  useEffect(() => { listClients().then(r => setClients(r.clients)).catch(() => {}); }, []);
  useEffect(() => { listFirmware({ limit: 500 }).then(r => setFirmware(r.items)).catch(() => {}); }, []);

  const clientOptions = useMemo(() => clients.map(c => ({
    value: c.name,
    label: c.online ? c.name : `${c.name} (offline)`,
    disabled: false,
  })), [clients]);

  const outcomeOptions = OUTCOMES.map(o => ({ value: o, label: o }));

  const hasAnyFilter = Boolean(
    (value.client?.length ?? 0) > 0 ||
    (value.outcome?.length ?? 0) > 0 ||
    value.source_kind ||
    value.source_id ||
    value.since ||
    value.until,
  );

  const since = value.since?.slice(0, 10) ?? "";
  const until = value.until?.slice(0, 10) ?? "";

  return (
    <div className="fl-filters">
      <div className="fl-filters__head">
        <div className="fl-filters__title">Filters</div>
        {hasAnyFilter && (
          <button type="button" className="fl-filt__clear" onClick={() => onChange({})}>
            Clear all filters
          </button>
        )}
      </div>

      <div className="fl-filt">
        <div className="fl-filt__lbl">Client</div>
        <FlBadgeMulti
          selected={value.client ?? []}
          options={clientOptions}
          onAdd={v => onChange({ ...value, client: [...(value.client ?? []), v] })}
          onRemove={v => onChange({ ...value, client: (value.client ?? []).filter(x => x !== v) })}
          addLabel="Add client"
          emptyLabel="(any client)"
          mono
          bare
        />
      </div>

      <div className="fl-filt">
        <div className="fl-filt__lbl">Outcome</div>
        <FlBadgeMulti
          selected={value.outcome ?? []}
          options={outcomeOptions}
          onAdd={v => onChange({ ...value, outcome: [...(value.outcome ?? []), v] })}
          onRemove={v => onChange({ ...value, outcome: (value.outcome ?? []).filter(x => x !== v) })}
          addLabel="Add outcome"
          emptyLabel="(any outcome)"
          mono
          bare
        />
      </div>

      <div className="fl-filt">
        <div className="fl-filt__lbl">Source</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <FlDropdown
            value={value.source_kind ?? ""}
            placeholder="(any kind)"
            onChange={v => onChange({
              ...value,
              source_kind: (v || undefined) as FlashFilters["source_kind"],
              source_id: undefined,
            })}
            options={[
              { value: "", label: "(any kind)" },
              { value: "firmware", label: "firmware" },
              { value: "backup", label: "backup" },
            ]}
          />
          {value.source_kind === "firmware" && (
            <FlDropdown
              value={value.source_id ?? ""}
              placeholder="(any firmware)"
              onChange={v => onChange({ ...value, source_id: v || undefined })}
              options={[
                { value: "", label: "(any firmware)" },
                ...firmware.map(f => ({ value: f.id, label: f.name })),
              ]}
            />
          )}
        </div>
      </div>

      <div className="fl-filt">
        <div className="fl-filt__lbl">Date range</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <div className="fl-filt__date-row">
            <span>since</span>
            <FlDateInput
              value={since}
              onChange={v => onChange({ ...value, since: v ? `${v}T00:00:00Z` : undefined })}
            />
          </div>
          <div className="fl-filt__date-row">
            <span>until</span>
            <FlDateInput
              value={until}
              onChange={v => onChange({ ...value, until: v ? `${v}T23:59:59Z` : undefined })}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function LogTable({
  filters,
  selectedId,
  onOpen,
}: {
  filters: FlashFilters;
  selectedId: string | null;
  onOpen: (id: string) => void;
}) {
  const [items, setItems] = useState<FlashRowSummary[]>([]);
  const [nextBefore, setNextBefore] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [total, setTotal] = useState<number | null>(null);
  const loaderRef = useRef<HTMLTableRowElement>(null);

  const filtersKey = JSON.stringify(filters);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await listFlashes(filters, 50);
        if (cancelled) return;
        setItems(r.items);
        setNextBefore(r.next_before);
        setTotal(null);
      } catch {
        // ignore
      }
    })();
    return () => { cancelled = true; };
  }, [filtersKey]);

  async function loadMore() {
    if (!nextBefore || loadingMore) return;
    setLoadingMore(true);
    try {
      const r = await listFlashes(filters, 50, nextBefore);
      setItems(prev => [...prev, ...r.items]);
      setNextBefore(r.next_before);
    } finally {
      setLoadingMore(false);
    }
  }

  useEffect(() => {
    if (!nextBefore || !loaderRef.current) return;
    const obs = new IntersectionObserver(entries => {
      for (const e of entries) {
        if (e.isIntersecting) {
          loadMore();
          break;
        }
      }
    }, { rootMargin: "200px" });
    obs.observe(loaderRef.current);
    return () => obs.disconnect();
  }, [nextBefore, items.length]);

  return (
    <div className="fl-logs-wrap">
      <table className="fl-logs-table">
        <thead>
          <tr>
            <th className="col-time">Started</th>
            <th className="col-client">Client</th>
            <th className="col-port">Port</th>
            <th>Source</th>
            <th>Outcome</th>
            <th className="col-dur">Duration</th>
            <th>Note</th>
          </tr>
        </thead>
        <tbody>
          {items.length === 0 ? (
            <tr>
              <td colSpan={7} style={{
                textAlign: "center",
                padding: 24,
                fontFamily: "'IBM Plex Sans', system-ui, sans-serif",
                color: "var(--text-muted)",
              }}>
                No flashes match the current filters.
              </td>
            </tr>
          ) : items.map(r => (
            <tr
              key={r.id}
              data-selected={r.id === selectedId || undefined}
              onClick={() => onOpen(r.id)}
            >
              <td className="col-time">{r.started_at}</td>
              <td>{r.client}</td>
              <td>{r.port_name}</td>
              <td>
                <span className="fl-muted" style={{ fontSize: 10.5 }}>{r.source_kind}:</span>{" "}
                <span>{r.firmware_name}</span>
              </td>
              <td><FlOutc outcome={r.outcome ?? r.status} tone={outcomeTone(r.outcome, r.status)} /></td>
              <td className="col-dur">{r.duration_ms != null ? `${(r.duration_ms / 1000).toFixed(1)}s` : ""}</td>
              <td className="col-note">{r.operator_note}</td>
            </tr>
          ))}
          {nextBefore && (
            <tr className="fl-logs-loader" ref={loaderRef}>
              <td colSpan={7}>
                {loadingMore ? (
                  <>
                    <span className="fl-logs-loader__spinner" aria-hidden="true" />
                    <span>Loading more…</span>
                  </>
                ) : (
                  <FlButton small variant="ghost" onClick={loadMore}>Load more</FlButton>
                )}
              </td>
            </tr>
          )}
          {!nextBefore && items.length > 0 && (
            <tr className="fl-logs-loader">
              <td colSpan={7}>End of results · {items.length} flashes.</td>
            </tr>
          )}
        </tbody>
      </table>
      {total != null && <div style={{ display: "none" }}>{total}</div>}
    </div>
  );
}
