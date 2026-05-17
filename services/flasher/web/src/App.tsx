import { useEffect, useState } from "react";
import { Topbar } from "./components/Topbar";
import { FlashTab } from "./tabs/FlashTab";
import { FirmwareTab } from "./tabs/FirmwareTab";
import { BackupsTab } from "./tabs/BackupsTab";
import { LogsTab } from "./tabs/LogsTab";
import { getCurrentFlash, getFlash } from "./api";
import { FlashRowDetail, TabId } from "./types";

export default function App() {
  const [tab, setTab] = useState<TabId>("flash");
  const [runningFlashId, setRunningFlashId] = useState<string | null>(null);
  const [, setBeat] = useState(0);

  useEffect(() => {
    (async () => {
      const body = await getCurrentFlash().catch(() => ({} as any));
      if ((body as FlashRowDetail).id && (body as FlashRowDetail).status === "running") {
        setRunningFlashId((body as FlashRowDetail).id);
      }
    })();
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

  return (
    <div className="fl-app">
      <Topbar active={tab} onChange={setTab} />
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
