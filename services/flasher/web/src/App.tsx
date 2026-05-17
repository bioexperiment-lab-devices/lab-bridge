import { useEffect, useMemo, useState } from "react";
import { HealthTone, Topbar } from "./components/Topbar";
import { FlashTab } from "./tabs/FlashTab";
import { FirmwareTab } from "./tabs/FirmwareTab";
import { BackupsTab } from "./tabs/BackupsTab";
import { LogsTab } from "./tabs/LogsTab";
import { getCurrentFlash, getFlash, listClients } from "./api";
import { FlashRowDetail, TabId } from "./types";

const FLASHER_VERSION = "v0.9";

export default function App() {
  const [tab, setTab] = useState<TabId>("flash");
  const [runningFlashId, setRunningFlashId] = useState<string | null>(null);
  const [, setBeat] = useState(0);
  const [clientCount, setClientCount] = useState<{ online: number; total: number } | null>(null);

  useEffect(() => {
    (async () => {
      const body = await getCurrentFlash().catch(() => ({} as any));
      if ((body as FlashRowDetail).id && (body as FlashRowDetail).status === "running") {
        setRunningFlashId((body as FlashRowDetail).id);
      }
    })();
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function refresh() {
      try {
        const r = await listClients();
        if (cancelled) return;
        const online = r.clients.filter(c => c.online).length;
        setClientCount({ online, total: r.clients.length });
      } catch {
        // ignore
      }
    }
    refresh();
    const t = window.setInterval(refresh, 10_000);
    return () => { cancelled = true; window.clearInterval(t); };
  }, []);

  useEffect(() => {
    if (!runningFlashId) return;
    let cancelled = false;
    const timer = window.setInterval(async () => {
      try {
        const row = await getFlash(runningFlashId);
        if (cancelled) return;
        setBeat(b => b + 1);
        if (row.status !== "running") {
          setRunningFlashId(null);
        }
      } catch {
        setRunningFlashId(null);
      }
    }, 1500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [runningFlashId]);

  const health = useMemo<{ tone: HealthTone; label: string }>(() => {
    if (runningFlashId) return { tone: "busy", label: "flash in progress" };
    if (!clientCount) return { tone: "ok", label: "…" };
    if (clientCount.online === 0) {
      return { tone: "err", label: clientCount.total === 0 ? "no lab machines configured" : "all lab machines offline" };
    }
    if (clientCount.online < clientCount.total) {
      const offline = clientCount.total - clientCount.online;
      return { tone: "warn", label: `${offline} of ${clientCount.total} lab machines offline` };
    }
    return { tone: "ok", label: `all ${clientCount.total} lab machines online` };
  }, [runningFlashId, clientCount]);

  return (
    <div className="fl-app">
      <Topbar
        active={tab}
        onChange={setTab}
        health={health}
        version={FLASHER_VERSION}
      />
      <main className="fl-body">
        {tab === "flash" && (
          <FlashTab runningFlashId={runningFlashId} setRunningFlashId={setRunningFlashId} />
        )}
        {tab === "firmware" && <FirmwareTab />}
        {tab === "backups" && <BackupsTab />}
        {tab === "logs" && <LogsTab />}
      </main>
    </div>
  );
}
