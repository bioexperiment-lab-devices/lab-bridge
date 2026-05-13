import { useEffect, useState } from 'react'
import { ClientPicker } from './components/ClientPicker'
import { PortTable } from './components/PortTable'
import { FirmwarePicker, type FirmwareState } from './components/FirmwarePicker'

export function App() {
  const [client, setClient] = useState<string | null>(null)
  const [port, setPort] = useState<string | null>(null)
  const [firmware, setFirmware] = useState<FirmwareState | null>(null)

  useEffect(() => {
    setPort(null)
    setFirmware(null)
  }, [client])

  return (
    <main className="container">
      <h1>lab-bridge flasher</h1>
      <ClientPicker selected={client} onSelect={setClient} />
      {client && (
        <PortTable clientName={client} selectedPort={port} onSelect={setPort} />
      )}
      {client && port && (
        <FirmwarePicker firmware={firmware} onChange={setFirmware} />
      )}
    </main>
  )
}
