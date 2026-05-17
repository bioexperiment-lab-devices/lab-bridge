import { Link } from "@tanstack/react-router";

interface TabDef {
  to: "/" | "/firmware" | "/backups" | "/logs";
  label: string;
  exact?: boolean;
}

const TABS: TabDef[] = [
  { to: "/", label: "Flash", exact: true },
  { to: "/firmware", label: "Firmware" },
  { to: "/backups", label: "Backups" },
  { to: "/logs", label: "Logs" },
];

export function Topbar() {
  return (
    <header className="fl-topbar">
      <div className="fl-brand">
        <span className="fl-brand__mark">F</span>
        Flasher
      </div>
      <nav className="fl-topbar__tabs" role="tablist">
        {TABS.map(t => (
          <Link
            key={t.to}
            to={t.to}
            role="tab"
            className="fl-tab"
            activeOptions={{ exact: t.exact ?? false }}
            activeProps={{ "data-active": "true" } as any}
          >
            {t.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
