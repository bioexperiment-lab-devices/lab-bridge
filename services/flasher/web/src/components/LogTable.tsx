import { useEffect, useState } from "react";
import { listFlashes } from "../api";
import { FlashFilters, FlashRowSummary } from "../types";

interface Props {
  filters: FlashFilters;
  onOpen: (flashId: string) => void;
}

export function LogTable({ filters, onOpen }: Props) {
  const [items, setItems] = useState<FlashRowSummary[]>([]);
  const [nextBefore, setNextBefore] = useState<string | null>(null);

  async function refresh() {
    const r = await listFlashes(filters, 50);
    setItems(r.items); setNextBefore(r.next_before);
  }
  useEffect(() => { refresh(); }, [JSON.stringify(filters)]);

  async function loadMore() {
    if (!nextBefore) return;
    const r = await listFlashes(filters, 50, nextBefore);
    setItems(prev => [...prev, ...r.items]); setNextBefore(r.next_before);
  }

  return (
    <div className="log-table">
      <table>
        <thead>
          <tr>
            <th>Started</th><th>Client</th><th>Port</th>
            <th>Source</th><th>Outcome</th><th>Duration</th><th>Note</th>
          </tr>
        </thead>
        <tbody>
          {items.map(r => (
            <tr key={r.id} onClick={() => onOpen(r.id)}>
              <td>{r.started_at}</td>
              <td>{r.client}</td>
              <td>{r.port_name}</td>
              <td>{r.source_kind}: {r.firmware_name}</td>
              <td>{r.outcome ?? r.status}</td>
              <td>{r.duration_ms != null ? `${(r.duration_ms/1000).toFixed(1)}s` : ""}</td>
              <td className="muted">{r.operator_note.slice(0, 60)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {nextBefore ? <button onClick={loadMore}>Load more</button> : null}
    </div>
  );
}
