import { useState } from "react";
import { FlashRowDetail } from "../types";

interface Props {
  row: FlashRowDetail;
}

function outcomeColor(outcome: string | null): "green" | "amber" | "red" {
  if (outcome === "success") return "green";
  if (outcome === "failed_no_recovery" || outcome === "error") return "red";
  return "amber";
}

export function ResultView({ row }: Props) {
  const [rawOpen, setRawOpen] = useState(false);

  const color = outcomeColor(row.outcome ?? row.status);
  const label = row.outcome ?? row.status;

  return (
    <section className="result-view">
      <div className={`badge badge-${color}`}>{label}</div>
      {row.error_code ? <h2>{row.error_code}</h2> : null}
      {row.error_detail ? <p>{row.error_detail}</p> : null}
      <dl className="flash-meta">
        <dt>Client</dt><dd>{row.client}</dd>
        <dt>Port</dt><dd>{row.port_name}</dd>
        <dt>Firmware</dt><dd>{row.firmware_name}</dd>
        <dt>Started</dt><dd>{row.started_at}</dd>
        {row.finished_at ? <><dt>Finished</dt><dd>{row.finished_at}</dd></> : null}
        {row.duration_ms != null ? <><dt>Duration</dt><dd>{row.duration_ms} ms</dd></> : null}
        {row.backup_id ? <><dt>Backup ID</dt><dd>{row.backup_id}</dd></> : null}
      </dl>
      {row.result ? (
        <details open={rawOpen} onToggle={(e) => setRawOpen((e.target as HTMLDetailsElement).open)}>
          <summary>Raw result JSON</summary>
          <pre>{JSON.stringify(row.result, null, 2)}</pre>
        </details>
      ) : null}
    </section>
  );
}
