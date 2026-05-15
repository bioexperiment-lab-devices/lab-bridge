import { diffByteIndices } from '../hex'

interface Props {
  label: string
  canonical: string
  mismatches: number[]
}

export function HexRow({ label, canonical, mismatches }: Props) {
  const bytes: string[] = []
  for (let i = 0; i < canonical.length; i += 2) {
    bytes.push(canonical.slice(i, i + 2))
  }
  const mismatchSet = new Set(mismatches)
  return (
    <div className="hex-row">
      <span className="hex-row-label">{label}</span>
      <code className="hex-row-bytes">
        {bytes.length === 0
          ? '—'
          : bytes.map((b, i) => (
              <span key={i} className={mismatchSet.has(i) ? 'mismatch' : ''}>
                {b}
                {i + 1 < bytes.length ? ' ' : ''}
              </span>
            ))}
      </code>
    </div>
  )
}

export function HexDiff({ expected, received }: { expected: string; received: string }) {
  const e = expected.toLowerCase()
  const r = received.toLowerCase()
  const mismatches = diffByteIndices(e, r)
  return (
    <div className="hex-diff">
      <HexRow label="Expected" canonical={e} mismatches={mismatches} />
      <HexRow label="Received" canonical={r} mismatches={mismatches} />
      <p className="hex-diff-summary">
        {mismatches.length === 0
          ? 'Byte-for-byte match.'
          : `${mismatches.length} byte(s) differ.`}
      </p>
    </div>
  )
}
