// @ts-nocheck — legacy component; prop interface updated for Phase 9
import { useCallback, useEffect, useState } from 'react'
import { listPorts } from '../api'

interface Props {
  client: string
  value: string | null
  onChange: (port: string | null) => void
  onPortsLoaded?: (ports: any[]) => void
}

export function PortTable({ client, value, onChange, onPortsLoaded }: Props) {
  const [ports, setPorts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await listPorts(client)
      setPorts(data.ports)
      onPortsLoaded?.(data.ports)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [client])

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
        <p>No serial ports reported by {client}.</p>
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
                  value === p.name ? 'selected' : ''
                }`}
                onClick={() => onChange(p.name)}
              >
                <td>
                  <input
                    type="radio"
                    name="port"
                    checked={value === p.name}
                    onChange={() => onChange(p.name)}
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
