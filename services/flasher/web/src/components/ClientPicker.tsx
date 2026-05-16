// @ts-nocheck — Phase 9 will rewrite this component with updated types/api
import { useCallback, useEffect, useState } from 'react'
import { fetchClients } from '../api'
import type { ClientSummary } from '../types'

interface Props {
  selected: string | null
  onSelect: (name: string | null) => void
}

export function ClientPicker({ selected, onSelect }: Props) {
  const [clients, setClients] = useState<ClientSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchClients()
      setClients(data.clients)
      // If the previously-selected machine went offline, clear selection.
      if (selected && !data.clients.some((c) => c.name === selected)) {
        onSelect(null)
      }
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [selected, onSelect])

  useEffect(() => {
    load()
  }, [load])

  return (
    <section className="step">
      <header>
        <h2>1. Lab machine</h2>
        <button type="button" onClick={load} disabled={loading}>
          Refresh
        </button>
      </header>
      {loading && <p>Loading…</p>}
      {error && <p className="error">Failed to load clients: {error}</p>}
      {!loading && !error && clients.length === 0 && (
        <p>No lab machines are currently online.</p>
      )}
      {!loading && !error && clients.length > 0 && (
        <select
          value={selected ?? ''}
          onChange={(e) => onSelect(e.target.value || null)}
        >
          <option value="">— pick a machine —</option>
          {clients.map((c) => (
            <option key={c.name} value={c.name}>
              {c.name} (port {c.port})
            </option>
          ))}
        </select>
      )}
    </section>
  )
}
