import type {
  ClientsResponse,
  FlashJob,
  FlashRequestBody,
  PortsResponse,
} from './types'

const BASE = '/flash/api'

async function jsonOrThrow<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    const message =
      (typeof body === 'object' && body !== null && 'error' in body
        ? `${body.error}: ${body.detail ?? ''}`
        : '') || `${response.status} ${response.statusText}`
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

export async function fetchClients(): Promise<ClientsResponse> {
  return jsonOrThrow(await fetch(`${BASE}/clients`))
}

export async function fetchPorts(clientName: string): Promise<PortsResponse> {
  return jsonOrThrow(
    await fetch(`${BASE}/clients/${encodeURIComponent(clientName)}/ports`),
  )
}

export async function startFlash(body: FlashRequestBody): Promise<{ job_id: string }> {
  return jsonOrThrow(
    await fetch(`${BASE}/flash`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  )
}

export async function fetchFlashJob(jobId: string): Promise<FlashJob> {
  return jsonOrThrow(await fetch(`${BASE}/flash/${encodeURIComponent(jobId)}`))
}

export async function fetchCurrentFlash(): Promise<FlashJob | null> {
  const body = await jsonOrThrow<FlashJob | Record<string, never>>(
    await fetch(`${BASE}/flash/current`),
  )
  if ('job_id' in body) return body as FlashJob
  return null
}
