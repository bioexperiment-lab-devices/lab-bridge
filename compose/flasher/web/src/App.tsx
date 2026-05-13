import { useEffect, useState } from 'react'
import { ClientPicker } from './components/ClientPicker'
import { PortTable } from './components/PortTable'

export function App() {
  const [client, setClient] = useState<string | null>(null)
  const [port, setPort] = useState<string | null>(null)

  // Switching client must clear downstream state.
  useEffect(() => {
    setPort(null)
  }, [client])

  return (
    <main className="container">
      <h1>lab-bridge flasher</h1>
      <ClientPicker selected={client} onSelect={setClient} />
      {client && (
        <PortTable
          clientName={client}
          selectedPort={port}
          onSelect={setPort}
        />
      )}
    </main>
  )
}
