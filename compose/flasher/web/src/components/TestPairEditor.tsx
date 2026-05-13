import { asciiPreview, formatHexBytes, hexByteCount, isValidHex, normalizeHex } from '../hex'

export interface TestPair {
  command: string
  expected_response: string
}

interface Props {
  enabled: boolean
  pair: TestPair
  onToggle: (enabled: boolean) => void
  onChange: (pair: TestPair) => void
}

function HexInput({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (canonical: string) => void
}) {
  const canonical = value
  const formatted = formatHexBytes(canonical)
  const valid = isValidHex(canonical)
  const empty = canonical.length === 0

  return (
    <div className="hex-input">
      <label>{label}</label>
      <input
        type="text"
        value={formatted}
        onChange={(e) => onChange(normalizeHex(e.target.value))}
        spellCheck={false}
        autoComplete="off"
        placeholder="01 02 03"
      />
      <div className="hex-meta">
        <span>{hexByteCount(canonical)} bytes</span>
        {!empty && !valid && <span className="error">invalid hex</span>}
        {!empty && valid && (
          <span className="ascii">ASCII: <code>{asciiPreview(canonical)}</code></span>
        )}
      </div>
    </div>
  )
}

export function TestPairEditor({ enabled, pair, onToggle, onChange }: Props) {
  return (
    <section className="step">
      <header>
        <h2>4. Post-flash test</h2>
        <label className="switch">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => onToggle(e.target.checked)}
          />
          {enabled ? 'On' : 'Off'}
        </label>
      </header>
      {enabled && (
        <div className="hex-pair">
          <HexInput
            label="test_command"
            value={pair.command}
            onChange={(v) => onChange({ ...pair, command: v })}
          />
          <HexInput
            label="expected_response"
            value={pair.expected_response}
            onChange={(v) => onChange({ ...pair, expected_response: v })}
          />
        </div>
      )}
      {!enabled && (
        <p className="muted-text">
          The flash will succeed on byte-verify alone. No payload will be sent
          to the device after programming.
        </p>
      )}
    </section>
  )
}
