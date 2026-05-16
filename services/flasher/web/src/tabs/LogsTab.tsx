import { useState } from "react";
import { LogDetailDrawer } from "../components/LogDetailDrawer";
import { LogFilters } from "../components/LogFilters";
import { LogTable } from "../components/LogTable";
import { FlashFilters } from "../types";

export function LogsTab() {
  const [filters, setFilters] = useState<FlashFilters>({});
  const [openFlashId, setOpenFlashId] = useState<string | null>(null);
  return (
    <div className="tab-pane logs-tab">
      <LogFilters value={filters} onChange={setFilters} />
      <LogTable filters={filters} onOpen={setOpenFlashId} />
      {openFlashId ? (
        <LogDetailDrawer flashId={openFlashId} onClose={() => setOpenFlashId(null)} />
      ) : null}
    </div>
  );
}
