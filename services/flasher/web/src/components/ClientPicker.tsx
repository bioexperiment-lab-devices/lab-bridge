import { useEffect, useState } from "react";
import { listClients } from "../api";
import { ClientEntry } from "../types";

interface Props {
  value: string | null;
  onChange: (name: string | null) => void;
}

export function ClientPicker({ value, onChange }: Props) {
  const [items, setItems] = useState<ClientEntry[]>([]);
  const [loading, setLoading] = useState(false);

  async function refresh() {
    setLoading(true);
    try { setItems((await listClients()).clients); }
    finally { setLoading(false); }
  }
  useEffect(() => { refresh(); }, []);

  return (
    <div className="client-picker">
      <label>
        Lab machine:
        <select
          value={value ?? ""}
          onChange={e => onChange(e.target.value || null)}
        >
          <option value="">(select…)</option>
          {items.map(c => (
            <option key={c.name} value={c.name} disabled={!c.online}>
              {c.name}{c.online ? "" : " — offline"}
            </option>
          ))}
        </select>
      </label>
      <button onClick={refresh} disabled={loading}>Retry probe</button>
    </div>
  );
}
