import { ReactNode, createContext, useContext, useEffect, useRef, useState } from "react";
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
  const topbarRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    (async () => {
      const body = await getCurrentFlash().catch(() => ({} as any));
      if ((body as FlashRowDetail).id && (body as FlashRowDetail).status === "running") {
        setRunningFlashId((body as FlashRowDetail).id);
      }
    })();
  }, []);

  // Track topbar height so --rail-top-offset stays accurate when the topbar
  // wraps on narrow viewports. The CSS fallback covers the un-mounted moment.
  useEffect(() => {
    const el = topbarRef.current ?? document.querySelector<HTMLElement>(".fl-topbar");
    if (!el) return;
    topbarRef.current = el;
    const apply = () => {
      document.body.style.setProperty("--rail-top-offset", `${el.getBoundingClientRect().height}px`);
    };
    apply();
    const obs = new ResizeObserver(apply);
    obs.observe(el);
    return () => obs.disconnect();
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
