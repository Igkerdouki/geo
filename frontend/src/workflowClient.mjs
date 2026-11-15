export const API = import.meta.env?.VITE_API_URL || '/api'
export async function api(path, options = {}) {
  const response = await fetch(API + path, { ...options, headers: { 'Content-Type': 'application/json', ...options.headers } })
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(typeof data.detail === 'string' ? data.detail : `Request failed (${response.status}). Check inputs and service availability.`)
  }
  return response.json()
}
export async function readNDJSON(reader, onEvent) {
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done })
    const lines = buffer.split('\n'); buffer = lines.pop()
    for (const line of lines) if (line.trim()) onEvent(JSON.parse(line))
    if (done) break
  }
  if (buffer.trim()) onEvent(JSON.parse(buffer))
}
export async function streamInvestigation(body, onEvent, signal) {
  const response = await fetch(API + '/workflows/investigate/stream', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal })
  if (!response.ok) { const error = await response.json().catch(() => ({})); throw new Error(typeof error.detail === 'string' ? error.detail : 'Unable to start investigation.') }
  let result
  await readNDJSON(response.body.getReader(), event => {
    onEvent(event)
    if (event.type === 'result') result = event.result
    if (event.type === 'error') throw new Error(event.message)
  })
  if (!result) throw new Error('Connection ended before the investigation completed.')
  return result
}
export function downloadJSON(value, name) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }))
  const link = document.createElement('a'); link.href = url; link.download = name; link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
export function simulationFromWorkflow(result) {
  const evidence = result?.evidence || []
  return [...evidence].reverse().find(e => e.status === 'complete' && ['simulate_spray_event', 'simulate_grid'].includes(e.tool))?.result || null
}
