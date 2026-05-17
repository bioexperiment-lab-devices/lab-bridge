import { TabId } from "../types";

interface Counts {
  flash?: number | null;
  firmware?: number | null;
  backups?: number | null;
  logs?: number | null;
}

const TABS: { id: TabId; label: string }[] = [
  { id: "flash", label: "Flash" },
  { id: "firmware", label: "Firmware" },
  { id: "backups", label: "Backups" },
  { id: "logs", label: "Logs" },
];

export function Topbar({
  active,
  onChange,
  counts = {},
}: {
  active: TabId;
  onChange: (next: TabId) => void;
  counts?: Counts;
}) {
  return (
    <header className="fl-topbar">
      <div className="fl-brand">
        <span className="fl-brand__mark">F</span>
        Flasher
      </div>
      <nav className="fl-topbar__tabs" role="tablist">
        {TABS.map(t => {
          const count = counts[t.id];
          return (
            <button
              key={t.id}
              role="tab"
              aria-selected={active === t.id}
              className="fl-tab"
              data-active={active === t.id || undefined}
              onClick={() => onChange(t.id)}
            >
              {t.label}
              {count != null && <span className="fl-tab__count">{count}</span>}
            </button>
          );
        })}
      </nav>
    </header>
  );
}
