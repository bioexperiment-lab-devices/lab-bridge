import { useEffect, useState } from "react";
import { getFlash, postFlash } from "../api";
import { ClientPicker } from "../components/ClientPicker";
import { FlashButton } from "../components/FlashButton";
import { FlashOptions } from "../components/FlashOptions";
import { FirmwareSourcePicker, FlashSource } from "../components/FirmwareSourcePicker";
import { PortTable } from "../components/PortTable";
import { ResultView } from "../components/ResultView";
import { RunningView } from "../components/RunningView";
import { TestPairEditor } from "../components/TestPairEditor";
import { FlashRowDetail, PortRow } from "../types";

interface Props {
  runningFlashId: string | null;
  setRunningFlashId: (id: string | null) => void;
}

export function FlashTab({ runningFlashId, setRunningFlashId }: Props) {
  const [client, setClient] = useState<string | null>(null);
  const [_ports, setPorts] = useState<PortRow[]>([]);
  const [selectedPort, setSelectedPort] = useState<string | null>(null);
  const [source, setSource] = useState<FlashSource | null>(null);
  const [tcmd, setTcmd] = useState("");
  const [eresp, setEresp] = useState("");
  const [runTest, setRunTest] = useState(true);
  const [skipBackup, setSkipBackup] = useState(false);
  const [savePairToRecord, setSavePairToRecord] = useState(false);
  const [latestFlash, setLatestFlash] = useState<FlashRowDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Reset test pair / save-back checkbox whenever the source changes.
  useEffect(() => {
    if (!source) { setTcmd(""); setEresp(""); setRunTest(true); setSavePairToRecord(false); return; }
    const r = source.record as any;
    setTcmd(r.test_command ?? "");
    setEresp(r.expected_response ?? "");
    setRunTest(Boolean(r.test_command));
    setSavePairToRecord(false);
  }, [source?.kind, source?.record.id]);

  // Whenever the running id changes (or polling reports terminal), fetch the
  // full flash row so the result view below has data.
  useEffect(() => {
    let cancelled = false;
    async function fetchOne(id: string) {
      try {
        const row = await getFlash(id);
        if (!cancelled) setLatestFlash(row);
      } catch { /* ignore */ }
    }
    if (runningFlashId) fetchOne(runningFlashId);
    // also re-poll latest at 1.5s while running so the result view appears as soon as it terminates
    const tick = window.setInterval(() => {
      if (runningFlashId) fetchOne(runningFlashId);
    }, 1500);
    return () => { cancelled = true; window.clearInterval(tick); };
  }, [runningFlashId]);

  const canFlash = client && selectedPort && source && (!runTest || (tcmd && eresp));

  async function onSubmit() {
    if (!canFlash || !source) return;
    setError(null);
    try {
      const body: any = {
        client, port: selectedPort,
        source: { kind: source.kind, id: source.record.id },
        skip_backup: skipBackup,
      };
      if (runTest) {
        body.test_override = { command: tcmd, expected_response: eresp };
        body.save_test_to_record = savePairToRecord && source.kind === "firmware";
      }
      const r = await postFlash(body);
      setRunningFlashId(r.job_id);
    } catch (e: any) {
      setError(e.body?.detail ?? String(e));
    }
  }

  const isRunning = latestFlash?.status === "running";

  return (
    <div className="tab-pane flash-tab">
      <section className="flash-form">
        <ClientPicker value={client} onChange={setClient} />
        {client ? (
          <PortTable client={client} value={selectedPort} onChange={setSelectedPort}
                     onPortsLoaded={setPorts} />
        ) : null}
        <FirmwareSourcePicker value={source} onChange={setSource} />
        {source ? (
          <>
            <TestPairEditor
              command={tcmd} expectedResponse={eresp}
              onCommandChange={v => { setTcmd(v); }}
              onExpectedChange={v => { setEresp(v); }}
              runTest={runTest} onRunTestChange={setRunTest}
            />
            {source.kind === "firmware" ? (
              <label>
                <input type="checkbox" checked={savePairToRecord}
                       onChange={e => setSavePairToRecord(e.target.checked)} />
                Save edits to record
              </label>
            ) : null}
          </>
        ) : null}
        <FlashOptions skipBackup={skipBackup} onSkipBackupChange={setSkipBackup} />
        <FlashButton disabled={!canFlash} onClick={onSubmit} />
        {error ? <div className="error">{error}</div> : null}
      </section>

      <section className="flash-output">
        {latestFlash ? (
          isRunning ? (
            <RunningView started={latestFlash.started_at}
                         client={latestFlash.client}
                         port={latestFlash.port_name}
                         firmwareName={latestFlash.firmware_name} />
          ) : (
            <ResultView row={latestFlash} />
          )
        ) : null}
      </section>
    </div>
  );
}
