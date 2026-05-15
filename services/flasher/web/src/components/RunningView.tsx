import { useEffect, useState } from 'react'
import { fetchFlashJob } from '../api'
import type { FlashJob } from '../types'

interface Props {
  jobId: string
  clientName: string
  portName: string
  firmwareFilename: string
  onComplete: (job: FlashJob) => void
}

function formatElapsed(ms: number): string {
  const total = Math.floor(ms / 1000)
  const mm = String(Math.floor(total / 60)).padStart(2, '0')
  const ss = String(total % 60).padStart(2, '0')
  return `${mm}:${ss}`
}

export function RunningView({
  jobId,
  clientName,
  portName,
  firmwareFilename,
  onComplete,
}: Props) {
  const [elapsedMs, setElapsedMs] = useState(0)

  useEffect(() => {
    const start = Date.now()
    const tick = setInterval(() => setElapsedMs(Date.now() - start), 1000)
    return () => clearInterval(tick)
  }, [])

  useEffect(() => {
    let cancelled = false
    const poll = async () => {
      while (!cancelled) {
        try {
          const job = await fetchFlashJob(jobId)
          if (cancelled) return
          if (job.status !== 'running') {
            onComplete(job)
            return
          }
        } catch {
          // Soft-ignore one-off poll failures; next interval may recover.
        }
        await new Promise((r) => setTimeout(r, 1500))
      }
    }
    poll()
    return () => {
      cancelled = true
    }
  }, [jobId, onComplete])

  return (
    <section className="running-view">
      <h2>Flashing…</h2>
      <p className="running-meta">
        <code>{clientName}</code> · <code>{portName}</code> · {firmwareFilename}
      </p>
      <div className="progress-bar" aria-label="flashing in progress">
        <div className="progress-bar-inner" />
      </div>
      <p className="elapsed">Elapsed {formatElapsed(elapsedMs)}</p>
      <p className="muted-text">
        Typical 15–30 s; up to ~60 s in worst case.
      </p>
    </section>
  )
}
