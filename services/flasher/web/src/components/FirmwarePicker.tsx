import { useState } from 'react'

const MAX_BYTES = 256 * 1024

interface FirmwareState {
  filename: string
  text: string
  sha256: string
  size: number
}

interface Props {
  firmware: FirmwareState | null
  onChange: (next: FirmwareState | null) => void
}

async function sha256Hex(text: string): Promise<string> {
  const buf = new TextEncoder().encode(text)
  const digest = await crypto.subtle.digest('SHA-256', buf)
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
}

export function FirmwarePicker({ firmware, onChange }: Props) {
  const [error, setError] = useState<string | null>(null)

  const onFile = async (file: File | null) => {
    setError(null)
    if (!file) {
      onChange(null)
      return
    }
    if (file.size > MAX_BYTES) {
      setError(
        `File is ${file.size} bytes; limit is 256 KiB (${MAX_BYTES}).`,
      )
      onChange(null)
      return
    }
    const text = await file.text()
    if (!text.trim()) {
      setError('File is empty.')
      onChange(null)
      return
    }
    const sha = await sha256Hex(text)
    onChange({ filename: file.name, text, sha256: sha, size: file.size })
  }

  return (
    <section className="step">
      <header>
        <h2>3. Firmware (.hex)</h2>
      </header>
      <input
        type="file"
        accept=".hex"
        onChange={(e) => onFile(e.target.files?.[0] ?? null)}
      />
      {error && <p className="error">{error}</p>}
      {firmware && (
        <dl className="firmware-meta">
          <dt>File</dt>
          <dd><code>{firmware.filename}</code></dd>
          <dt>Size</dt>
          <dd>{firmware.size.toLocaleString()} bytes</dd>
          <dt>SHA-256</dt>
          <dd title={firmware.sha256}>
            <code>{firmware.sha256.slice(0, 16)}…</code>
          </dd>
        </dl>
      )}
    </section>
  )
}

export type { FirmwareState }
