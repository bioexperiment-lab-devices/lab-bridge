import { useEffect, useState } from "react";
import { listClients, listFirmware } from "../api";
import { ClientEntry, FirmwareRecord, FlashFilters } from "../types";

const OUTCOMES = [
  "success", "rolled_back_verify_failed", "rolled_back_test_failed",
  "failed_preflight", "failed_backup", "failed_no_recovery",
  "error", "interrupted",
];

interface Props {
  value: FlashFilters;
  onChange: (next: FlashFilters) => void;
}

export function LogFilters({ value, onChange }: Props) {
  const [clients, setClients] = useState<ClientEntry[]>([]);
  const [firmware, setFirmware] = useState<FirmwareRecord[]>([]);

  useEffect(() => { listClients().then(r => setClients(r.clients)); }, []);
  useEffect(() => { listFirmware({ limit: 500 }).then(r => setFirmware(r.items)); }, []);

  return (
    <div className="log-filters">
      <fieldset>
        <legend>Client</legend>
        {clients.map(c => (
          <label key={c.name}>
            <input type="checkbox"
                   checked={(value.client ?? []).includes(c.name)}
                   onChange={e => onChange({
                     ...value,
                     client: e.target.checked
                       ? [...(value.client ?? []), c.name]
                       : (value.client ?? []).filter(x => x !== c.name),
                   })} />
            {c.name}{c.online ? "" : " (offline)"}
          </label>
        ))}
      </fieldset>
      <fieldset>
        <legend>Outcome</legend>
        {OUTCOMES.map(o => (
          <label key={o}>
            <input type="checkbox"
                   checked={(value.outcome ?? []).includes(o)}
                   onChange={e => onChange({
                     ...value,
                     outcome: e.target.checked
                       ? [...(value.outcome ?? []), o]
                       : (value.outcome ?? []).filter(x => x !== o),
                   })} />
            {o}
          </label>
        ))}
      </fieldset>
      <fieldset>
        <legend>Source</legend>
        <select value={value.source_kind ?? ""}
                onChange={e => onChange({
                  ...value,
                  source_kind: (e.target.value || undefined) as any,
                  source_id: undefined,
                })}>
          <option value="">(any)</option>
          <option value="firmware">firmware</option>
          <option value="backup">backup</option>
        </select>
        {value.source_kind === "firmware" ? (
          <select value={value.source_id ?? ""}
                  onChange={e => onChange({ ...value, source_id: e.target.value || undefined })}>
            <option value="">(any firmware)</option>
            {firmware.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}
          </select>
        ) : null}
      </fieldset>
      <fieldset>
        <legend>Date range</legend>
        <label>Since <input type="date" value={value.since?.slice(0, 10) ?? ""}
                            onChange={e => onChange({
                              ...value,
                              since: e.target.value ? `${e.target.value}T00:00:00Z` : undefined,
                            })} /></label>
        <label>Until <input type="date" value={value.until?.slice(0, 10) ?? ""}
                            onChange={e => onChange({
                              ...value,
                              until: e.target.value ? `${e.target.value}T23:59:59Z` : undefined,
                            })} /></label>
      </fieldset>
      <button onClick={() => onChange({})}>Clear all</button>
    </div>
  );
}
