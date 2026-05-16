// @ts-nocheck — legacy component; prop interface updated for Phase 9
import { useEffect, useState } from 'react'

interface Props {
  started: string
  client: string
  port: string
  firmwareName: string
}

function formatElapsed(ms: number): string {
  const total = Math.floor(ms / 1000)
  const mm = String(Math.floor(total / 60)).padStart(2, '0')
  const ss = String(total % 60).padStart(2, '0')
  return `${mm}:${ss}`
}

export function RunningView({ started, client, port, firmwareName }: Props) {
  const [elapsedMs, setElapsedMs] = useState(0)

  useEffect(() => {
    const startTime = new Date(started).getTime() || Date.now()
    const tick = setInterval(() => setElapsedMs(Date.now() - startTime), 1000)
    return () => clearInterval(tick)
  }, [started])

  return (
    <section className="running-view">
      <h2>Flashing…</h2>
      <p className="running-meta">
        <code>{client}</code> · <code>{port}</code> · {firmwareName}
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
