import { useCallback, useEffect, useState } from "react";

export interface FlashDraft {
  client: string | null;
  port: string | null;
  sourceKind: "firmware" | "backups";
  sourceId: string | null;
  tcmd: string;
  eresp: string;
  runTest: boolean;
  skipBackup: boolean;
}

const DEFAULT_DRAFT: FlashDraft = {
  client: null,
  port: null,
  sourceKind: "firmware",
  sourceId: null,
  tcmd: "",
  eresp: "",
  runTest: true,
  skipBackup: false,
};

// Bump when the shape changes incompatibly so we discard old drafts.
const STORAGE_KEY = "flasher.flash-draft.v1";

function readDraft(): FlashDraft {
  if (typeof window === "undefined") return DEFAULT_DRAFT;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_DRAFT;
    const parsed = JSON.parse(raw);
    return { ...DEFAULT_DRAFT, ...sanitize(parsed) };
  } catch {
    return DEFAULT_DRAFT;
  }
}

function sanitize(input: any): Partial<FlashDraft> {
  if (!input || typeof input !== "object") return {};
  const out: Partial<FlashDraft> = {};
  if (input.client === null || typeof input.client === "string") out.client = input.client;
  if (input.port === null || typeof input.port === "string") out.port = input.port;
  if (input.sourceKind === "firmware" || input.sourceKind === "backups") out.sourceKind = input.sourceKind;
  if (input.sourceId === null || typeof input.sourceId === "string") out.sourceId = input.sourceId;
  if (typeof input.tcmd === "string") out.tcmd = input.tcmd;
  if (typeof input.eresp === "string") out.eresp = input.eresp;
  if (typeof input.runTest === "boolean") out.runTest = input.runTest;
  if (typeof input.skipBackup === "boolean") out.skipBackup = input.skipBackup;
  return out;
}

export function useFlashDraft(): [FlashDraft, (patch: Partial<FlashDraft>) => void] {
  const [draft, setDraftState] = useState<FlashDraft>(readDraft);

  // Persist on every change.
  useEffect(() => {
    try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(draft)); }
    catch { /* ignore quota / disabled storage */ }
  }, [draft]);

  const setDraft = useCallback((patch: Partial<FlashDraft>) => {
    setDraftState(prev => ({ ...prev, ...patch }));
  }, []);

  return [draft, setDraft];
}
