import { ReactNode, createContext, useContext, useEffect, useState } from "react";
import { Topbar } from "./components/Topbar";
import { getCurrentFlash, getFlash } from "./api";
import { FlashRowDetail } from "./types";

interface FlashRunContext {
  runningFlashId: string | null;
  setRunningFlashId: (id: string | null) => void;
}

const FlashRunCtx = createContext<FlashRunContext | null>(null);

export function useFlashRun(): FlashRunContext {
  const ctx = useContext(FlashRunCtx);
  if (!ctx) throw new Error("useFlashRun must be used within <Shell>");
  return ctx;
}

export function Shell({ children }: { children: ReactNode }) {
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
    <FlashRunCtx.Provider value={{ runningFlashId, setRunningFlashId }}>
      <div className="fl-app">
        <Topbar />
        <main className="fl-body">{children}</main>
      </div>
    </FlashRunCtx.Provider>
  );
}
