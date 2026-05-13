import { useState } from 'react'
import { HexDiff } from './HexDiff'
import { StageStrip } from './StageStrip'
import type { FlashDone, FlashErrored, Outcome } from '../types'

type Props = {
  job: FlashDone | FlashErrored
  onFlashAnother: () => void
  onDone: () => void
}

function outcomeBadge(outcome: Outcome | 'error'): { label: string; color: 'green' | 'amber' | 'red' } {
  if (outcome === 'success') return { label: 'success', color: 'green' }
  if (outcome === 'failed_no_recovery') return { label: outcome, color: 'red' }
  if (outcome === 'error') return { label: 'error', color: 'red' }
  return { label: outcome, color: 'amber' }
}

export function ResultView({ job, onFlashAnother, onDone }: Props) {
  const [rawOpen, setRawOpen] = useState(false)

  if (job.status === 'error') {
    const badge = outcomeBadge('error')
    return (
      <section className="result-view">
        <div className={`badge badge-${badge.color}`}>{badge.label}</div>
        <h2>{job.error_code}</h2>
        <p>{job.detail}</p>
        <details open={rawOpen} onToggle={(e) => setRawOpen((e.target as HTMLDetailsElement).open)}>
          <summary>Raw JSON</summary>
          <pre>{JSON.stringify(job, null, 2)}</pre>
        </details>
        <div className="actions">
          <button type="button" onClick={onFlashAnother}>Flash another</button>
          <button type="button" onClick={onDone}>Done</button>
        </div>
      </section>
    )
  }

  const result = job.result
  const badge = outcomeBadge(result.outcome)
  return (
    <section className="result-view">
      <div className={`badge badge-${badge.color}`}>{result.outcome}</div>
      {result.recovery_hint && (
        <p className="recovery-hint">⚠ {result.recovery_hint}</p>
      )}
      <StageStrip stages={result.stages} />

      {result.test_result && (
        <HexDiff
          expected={result.test_result.expected}
          received={result.test_result.received}
        />
      )}

      {result.backup && (
        <dl className="backup-meta">
          <dt>Backup saved to</dt>
          <dd><code>{result.backup.saved_path}</code></dd>
          <dt>SHA-256</dt>
          <dd><code>{result.backup.sha256.slice(0, 32)}…</code></dd>
          <dt>Size</dt>
          <dd>{result.backup.size_bytes.toLocaleString()} bytes (Intel HEX text)</dd>
          <dt>Scope</dt>
          <dd>{result.backup.scope} (EEPROM not captured)</dd>
        </dl>
      )}

      <details open={rawOpen} onToggle={(e) => setRawOpen((e.target as HTMLDetailsElement).open)}>
        <summary>Raw JSON</summary>
        <pre>{JSON.stringify(result, null, 2)}</pre>
      </details>

      <div className="actions">
        <button type="button" onClick={onFlashAnother}>Flash another</button>
        <button type="button" onClick={onDone}>Done</button>
      </div>
    </section>
  )
}
