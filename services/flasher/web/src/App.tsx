import { useEffect, useState } from "react";
import { TabBar } from "./components/TabBar";
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

  // On mount, see if there's already a running flash.
  useEffect(() => {
    (async () => {
      const body = await getCurrentFlash().catch(() => ({} as any));
      if ((body as FlashRowDetail).id && (body as FlashRowDetail).status === "running") {
        setRunningFlashId((body as FlashRowDetail).id);
      }
    })();
  }, []);

  // Polling: any time a running id is set, poll until terminal.
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
        // Network blips — keep polling. A 404 (e.g. the row was deleted) would
        // throw; recover by clearing the running id.
        setRunningFlashId(null);
      }
    }, 1500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [runningFlashId]);

  return (
    <div className="app">
      <TabBar active={tab} onChange={setTab} />
      <main>
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
