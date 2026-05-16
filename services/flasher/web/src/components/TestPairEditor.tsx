import { asciiPreview, formatHexBytes, hexByteCount, isValidHex, normalizeHex } from '../hex'

interface Props {
  command: string
  expectedResponse: string
  onCommandChange: (v: string) => void
  onExpectedChange: (v: string) => void
  runTest: boolean
  onRunTestChange: (v: boolean) => void
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

export function TestPairEditor({ command, expectedResponse, onCommandChange, onExpectedChange, runTest, onRunTestChange }: Props) {
  return (
    <section className="step">
      <header>
        <h2>4. Post-flash test</h2>
        <label className="switch">
          <input
            type="checkbox"
            checked={runTest}
            onChange={(e) => onRunTestChange(e.target.checked)}
          />
          {runTest ? 'On' : 'Off'}
        </label>
      </header>
      {runTest && (
        <div className="hex-pair">
          <HexInput
            label="test_command"
            value={command}
            onChange={onCommandChange}
          />
          <HexInput
            label="expected_response"
            value={expectedResponse}
            onChange={onExpectedChange}
          />
        </div>
      )}
      {!runTest && (
        <p className="muted-text">
          The flash will succeed on byte-verify alone. No payload will be sent
          to the device after programming.
        </p>
      )}
    </section>
  )
}
