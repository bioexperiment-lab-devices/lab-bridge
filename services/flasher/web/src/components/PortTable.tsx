// @ts-nocheck — Phase 9 will rewrite this component with updated types/api
import { useCallback, useEffect, useState } from 'react'
import { fetchPorts } from '../api'
import type { PortInfo } from '../types'

interface Props {
  clientName: string
  selectedPort: string | null
  onSelect: (port: string | null) => void
}

export function PortTable({ clientName, selectedPort, onSelect }: Props) {
  const [ports, setPorts] = useState<PortInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchPorts(clientName)
      setPorts(data.ports)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [clientName])

  useEffect(() => {
    load()
  }, [load])

  return (
    <section className="step">
      <header>
        <h2>2. Serial port</h2>
        <button type="button" onClick={load} disabled={loading}>
          Refresh
        </button>
      </header>
      {loading && <p>Loading…</p>}
      {error && <p className="error">Failed to load ports: {error}</p>}
      {!loading && !error && ports.length === 0 && (
        <p>No serial ports reported by {clientName}.</p>
      )}
      {!loading && !error && ports.length > 0 && (
        <table className="ports">
          <thead>
            <tr>
              <th></th>
              <th>Port</th>
              <th>Product</th>
              <th>VID:PID</th>
              <th>Serial</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {ports.map((p) => (
              <tr
                key={p.name}
                className={`${p.is_usb ? '' : 'muted'} ${
                  selectedPort === p.name ? 'selected' : ''
                }`}
                onClick={() => onSelect(p.name)}
              >
                <td>
                  <input
                    type="radio"
                    name="port"
                    checked={selectedPort === p.name}
                    onChange={() => onSelect(p.name)}
                  />
                </td>
                <td><code>{p.name}</code></td>
                <td>{p.product || '—'}</td>
                <td>
                  {p.vid && p.pid ? <code>{p.vid}:{p.pid}</code> : '—'}
                </td>
                <td>
                  {p.serial_number ? <code>{p.serial_number}</code> : '—'}
                </td>
                <td>
                  {p.discovered ? `In use — ${p.device_id}` : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
