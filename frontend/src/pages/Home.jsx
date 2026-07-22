import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { submitNotes, uploadAudio } from '../api'

export default function Home() {
  const navigate = useNavigate()
  const [mode, setMode] = useState('audio')
  const [title, setTitle] = useState('')
  const [file, setFile] = useState(null)
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function onSubmit(event) {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      let result
      if (mode === 'audio') {
        if (!file) throw new Error('Choose an audio file to upload.')
        result = await uploadAudio({ file, title: title.trim() || undefined })
      } else {
        if (!text.trim()) throw new Error('Paste meeting notes before submitting.')
        result = await submitNotes({ text: text.trim(), title: title.trim() || undefined })
      }
      navigate(`/meetings/${result.meeting_id}`)
    } catch (err) {
      setError(err.message || 'Something went wrong.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <section className="hero">
        <h1>Turn meetings into minutes.</h1>
        <p>
          Upload audio or paste notes. Meeting Assist transcribes, then Claude drafts
          a summary, decisions, and action items.
        </p>
      </section>

      <section className="panel">
        <div className="tabs" role="tablist">
          <button
            type="button"
            className={`tab ${mode === 'audio' ? 'active' : ''}`}
            onClick={() => setMode('audio')}
          >
            Upload audio
          </button>
          <button
            type="button"
            className={`tab ${mode === 'text' ? 'active' : ''}`}
            onClick={() => setMode('text')}
          >
            Paste notes
          </button>
        </div>

        <form onSubmit={onSubmit}>
          <div className="field">
            <label htmlFor="title">Title (optional)</label>
            <input
              id="title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Weekly standup"
            />
          </div>

          {mode === 'audio' ? (
            <div className={`file-drop ${file ? 'has-file' : ''}`}>
              <strong>{file ? file.name : 'Drop in a meeting recording'}</strong>
              <div className="meta">mp3, wav, m4a, mp4, webm…</div>
              <input
                type="file"
                accept="audio/*,video/mp4,.mp3,.wav,.m4a,.webm,.ogg,.flac"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
            </div>
          ) : (
            <div className="field">
              <label htmlFor="notes">Meeting notes</label>
              <textarea
                id="notes"
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Paste transcript or rough notes…"
              />
            </div>
          )}

          <div className="actions" style={{ marginTop: '1rem' }}>
            <button className="btn btn-primary" type="submit" disabled={loading}>
              {loading ? 'Working…' : 'Generate minutes'}
            </button>
          </div>

          {loading && (
            <div className="loading">
              <div className="spinner" />
              {mode === 'audio'
                ? 'Transcribing with Whisper, then summarizing with Claude…'
                : 'Summarizing with Claude…'}
            </div>
          )}
          {error && <div className="error">{error}</div>}
        </form>
      </section>
    </>
  )
}
