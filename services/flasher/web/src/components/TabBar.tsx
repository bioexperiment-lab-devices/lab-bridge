import { TabId } from "../types";

interface TabBarProps {
  active: TabId;
  onChange: (next: TabId) => void;
}

const TABS: { id: TabId; label: string }[] = [
  { id: "flash", label: "Flash" },
  { id: "firmware", label: "Firmware" },
  { id: "backups", label: "Backups" },
  { id: "logs", label: "Logs" },
];

export function TabBar({ active, onChange }: TabBarProps) {
  return (
    <nav className="tab-bar" role="tablist">
      {TABS.map(t => (
        <button
          key={t.id}
          role="tab"
          aria-selected={active === t.id}
          className={`tab-bar-button ${active === t.id ? "active" : ""}`}
          onClick={() => onChange(t.id)}
        >
          {t.label}
        </button>
      ))}
    </nav>
  );
}
