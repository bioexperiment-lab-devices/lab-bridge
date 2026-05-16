import { useState } from "react";
import { BackupDetail } from "../components/BackupDetail";
import { BackupList } from "../components/BackupList";
import { LogDetailDrawer } from "../components/LogDetailDrawer";
import { PromoteBackupModal } from "../components/PromoteBackupModal";
import { BackupRecord } from "../types";

export function BackupsTab() {
  const [selected, setSelected] = useState<BackupRecord | null>(null);
  const [promoting, setPromoting] = useState<BackupRecord | null>(null);
  const [openFlashId, setOpenFlashId] = useState<string | null>(null);

  return (
    <div className="tab-pane backups-tab two-pane">
      <div className="two-pane-body">
        <div className="pane-left">
          <BackupList
            onSelect={setSelected}
            onPromote={setPromoting}
            selectedId={selected?.id ?? null}
          />
        </div>
        <div className="pane-right">
          {selected
            ? <BackupDetail backupId={selected.id} onOpenFlash={setOpenFlashId} />
            : <p className="muted">Select a backup on the left.</p>}
        </div>
      </div>
      {promoting ? (
        <PromoteBackupModal
          backup={promoting}
          onClose={() => setPromoting(null)}
          onCreated={() => setPromoting(null)}
        />
      ) : null}
      {openFlashId ? (
        <LogDetailDrawer flashId={openFlashId} onClose={() => setOpenFlashId(null)} />
      ) : null}
    </div>
  );
}
