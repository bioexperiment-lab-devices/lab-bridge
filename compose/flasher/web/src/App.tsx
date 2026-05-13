import { useCallback, useEffect, useState } from 'react'
import { fetchCurrentFlash, startFlash } from './api'
import { isValidHex } from './hex'
import { ClientPicker } from './components/ClientPicker'
import { PortTable } from './components/PortTable'
import { FirmwarePicker, type FirmwareState } from './components/FirmwarePicker'
import { TestPairEditor, type TestPair } from './components/TestPairEditor'
import { FlashOptions } from './components/FlashOptions'
import { FlashButton } from './components/FlashButton'
import { RunningView } from './components/RunningView'
import { ResultView } from './components/ResultView'
import type { FlashDone, FlashErrored, FlashJob, FlashRunning } from './types'

type WizardState =
  | { kind: 'wizard' }
  | { kind: 'running'; job: FlashRunning; firmwareFilename: string }
  | { kind: 'result'; job: FlashDone | FlashErrored }

export function App() {
  const [client, setClient] = useState<string | null>(null)
  const [port, setPort] = useState<string | null>(null)
  const [firmware, setFirmware] = useState<FirmwareState | null>(null)
  const [testEnabled, setTestEnabled] = useState(true)
  const [testPair, setTestPair] = useState<TestPair>({ command: '', expected_response: '' })
  const [skipBackup, setSkipBackup] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [state, setState] = useState<WizardState>({ kind: 'wizard' })

  // Recover from a page refresh while a flash is running.
  useEffect(() => {
    fetchCurrentFlash().then((job) => {
      if (!job) return
      if (job.status === 'running') {
        setState({ kind: 'running', job, firmwareFilename: '(in progress)' })
      } else {
        setState({ kind: 'result', job })
      }
    })
  }, [])

  useEffect(() => {
    setPort(null)
    setFirmware(null)
  }, [client])

  const flashReady =
    client !== null &&
    port !== null &&
    firmware !== null &&
    (!testEnabled || (isValidHex(testPair.command) && isValidHex(testPair.expected_response)))

  const onFlash = useCallback(async () => {
    if (!client || !port || !firmware) return
    setError(null)
    try {
      const { job_id } = await startFlash({
        client,
        port,
        firmware: firmware.text,
        test: testEnabled
          ? { command: testPair.command, expected_response: testPair.expected_response }
          : null,
        skip_backup: skipBackup,
      })
      setState({
        kind: 'running',
        job: {
          job_id,
          status: 'running',
          client,
          port,
          started_at: new Date().toISOString(),
          elapsed_ms: 0,
        },
        firmwareFilename: firmware.filename,
      })
    } catch (e) {
      setError((e as Error).message)
    }
  }, [client, port, firmware, testEnabled, testPair, skipBackup])

  const onComplete = useCallback((job: FlashJob) => {
    if (job.status === 'running') return
    setState({ kind: 'result', job })
  }, [])

  // Back to the wizard with EVERY field preserved — the operator can tweak
  // one thing and click Flash again.
  const onRetry = useCallback(() => {
    setState({ kind: 'wizard' })
  }, [])

  const onFlashAnother = useCallback(() => {
    setFirmware(null)
    setTestPair({ command: '', expected_response: '' })
    setState({ kind: 'wizard' })
  }, [])

  const onDoneReset = useCallback(() => {
    setClient(null)
    setPort(null)
    setFirmware(null)
    setTestEnabled(true)
    setTestPair({ command: '', expected_response: '' })
    setSkipBackup(false)
    setState({ kind: 'wizard' })
  }, [])

  if (state.kind === 'running') {
    return (
      <main className="container">
        <h1>lab-bridge flasher</h1>
        <RunningView
          jobId={state.job.job_id}
          clientName={state.job.client}
          portName={state.job.port}
          firmwareFilename={state.firmwareFilename}
          onComplete={onComplete}
        />
      </main>
    )
  }

  if (state.kind === 'result') {
    return (
      <main className="container">
        <h1>lab-bridge flasher</h1>
        <ResultView
          job={state.job}
          onRetry={onRetry}
          onFlashAnother={onFlashAnother}
          onDone={onDoneReset}
        />
      </main>
    )
  }

  return (
    <main className="container">
      <h1>lab-bridge flasher</h1>
      <ClientPicker selected={client} onSelect={setClient} />
      {client && (
        <PortTable clientName={client} selectedPort={port} onSelect={setPort} />
      )}
      {client && port && (
        <FirmwarePicker firmware={firmware} onChange={setFirmware} />
      )}
      {client && port && firmware && (
        <TestPairEditor
          enabled={testEnabled}
          pair={testPair}
          onToggle={setTestEnabled}
          onChange={setTestPair}
        />
      )}
      {client && port && firmware && (
        <FlashOptions skipBackup={skipBackup} onChange={setSkipBackup} />
      )}
      {client && (
        <FlashButton enabled={flashReady} clientName={client} onClick={onFlash} />
      )}
      {error && <p className="error">{error}</p>}
    </main>
  )
}
