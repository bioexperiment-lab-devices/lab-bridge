// Phase 7 stub — Phase 9 rewrites this to consume the new picker and
// render running/result views always-below-the-form.

interface FlashTabProps {
  runningFlashId: string | null;
  setRunningFlashId: (id: string | null) => void;
}

export function FlashTab({ runningFlashId, setRunningFlashId: _setRunningFlashId }: FlashTabProps) {
  return (
    <div className="tab-pane">
      <h2>Flash</h2>
      <p>Form goes here (Phase 9). Running flash id: {runningFlashId ?? "none"}.</p>
    </div>
  );
}
