const API_BASE = import.meta.env.VITE_API_BASE || ''

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options)
  const contentType = response.headers.get('content-type') || ''
  const isJson = contentType.includes('application/json')
  const body = isJson ? await response.json() : await response.text()

  if (!response.ok) {
    const detail =
      typeof body === 'object' && body?.detail
        ? typeof body.detail === 'string'
          ? body.detail
          : JSON.stringify(body.detail)
        : response.statusText
    throw new Error(detail || `Request failed (${response.status})`)
  }

  return body
}

export function listMeetings() {
  return request('/api/meetings')
}

export function searchMeetings(q) {
  return request(`/api/meetings/search?q=${encodeURIComponent(q)}`)
}

export function getMeeting(id) {
  return request(`/api/meetings/${id}`)
}

export async function uploadAudio({ file, title }) {
  const form = new FormData()
  form.append('file', file)
  if (title) form.append('title', title)
  return request('/api/meetings/upload', { method: 'POST', body: form })
}

export function submitNotes({ text, title }) {
  return request('/api/meetings/notes', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, title: title || null }),
  })
}

export function exportUrl(id, format) {
  return `${API_BASE}/api/meetings/${id}/export?format=${format}`
}
