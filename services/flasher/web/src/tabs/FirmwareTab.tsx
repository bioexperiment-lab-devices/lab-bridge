import { useState } from "react";
import { FirmwareDetail } from "../components/FirmwareDetail";
import { FirmwareList } from "../components/FirmwareList";
import { FirmwareUploadForm } from "../components/FirmwareUploadForm";
import { TagManager } from "../components/TagManager";
import { LogDetailDrawer } from "../components/LogDetailDrawer";

export function FirmwareTab() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [tagsOpen, setTagsOpen] = useState(false);
  const [openFlashId, setOpenFlashId] = useState<string | null>(null);

  return (
    <div className="tab-pane firmware-tab two-pane">
      <header className="pane-header">
        <button onClick={() => setUploadOpen(true)}>Upload firmware</button>
        <button onClick={() => setTagsOpen(true)}>Manage tags</button>
      </header>
      <div className="two-pane-body">
        <div className="pane-left">
          <FirmwareList onSelect={r => setSelectedId(r.id)} selectedId={selectedId} />
        </div>
        <div className="pane-right">
          {selectedId
            ? <FirmwareDetail firmwareId={selectedId} onOpenFlash={setOpenFlashId} />
            : <p className="muted">Select a firmware record on the left.</p>}
        </div>
      </div>
      {uploadOpen ? (
        <div className="modal-backdrop" onClick={() => setUploadOpen(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3>Upload firmware</h3>
            <FirmwareUploadForm
              onCreated={row => { setUploadOpen(false); setSelectedId(row.id); }}
              onCancel={() => setUploadOpen(false)}
            />
          </div>
        </div>
      ) : null}
      <TagManager open={tagsOpen} onClose={() => setTagsOpen(false)} />
      {openFlashId ? (
        <LogDetailDrawer flashId={openFlashId} onClose={() => setOpenFlashId(null)} />
      ) : null}
    </div>
  );
}
