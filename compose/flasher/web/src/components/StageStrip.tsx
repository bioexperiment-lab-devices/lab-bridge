import type { FlashStages, StageEntry } from '../types'

const STAGE_ORDER: (keyof FlashStages)[] = [
  'preflight',
  'backup',
  'erase',
  'program',
  'verify',
  'test',
  'rollback',
]

function chipClass(entry: StageEntry): string {
  return `chip chip-${entry.status.replace('/', '-')}`
}

function tooltip(entry: StageEntry): string {
  const parts: string[] = [entry.status]
  if (entry.duration_ms !== undefined) parts.push(`${entry.duration_ms} ms`)
  if (entry.error) parts.push(entry.error)
  return parts.join(' · ')
}

export function StageStrip({ stages }: { stages: FlashStages }) {
  return (
    <div className="stage-strip">
      {STAGE_ORDER.map((name) => {
        const entry = stages[name]
        return (
          <span key={name} className={chipClass(entry)} title={tooltip(entry)}>
            {name}
          </span>
        )
      })}
    </div>
  )
}
