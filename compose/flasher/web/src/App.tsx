import { useState } from 'react'
import { ClientPicker } from './components/ClientPicker'

export function App() {
  const [client, setClient] = useState<string | null>(null)

  return (
    <main className="container">
      <h1>lab-bridge flasher</h1>
      <ClientPicker selected={client} onSelect={setClient} />
      {client && <p>Picked: <code>{client}</code></p>}
    </main>
  )
}
