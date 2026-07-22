import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { exportUrl, getMeeting } from '../api'

export default function MeetingDetail() {
  const { id } = useParams()
  const [meeting, setMeeting] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError('')
      try {
        const data = await getMeeting(id)
        if (!cancelled) setMeeting(data)
      } catch (err) {
        if (!cancelled) setError(err.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [id])

  if (loading) {
    return (
      <div className="panel">
        <div className="loading">
          <div className="spinner" />
          Loading meeting…
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="panel">
        <div className="error">{error}</div>
        <p>
          <Link to="/meetings">Back to meetings</Link>
        </p>
      </div>
    )
  }

  if (!meeting) return null

  const tags = meeting.tags?.length ? meeting.tags : meeting.topics || []

  return (
    <>
      <section className="hero">
        <h1>{meeting.title}</h1>
        <p className="meta">
          {meeting.date ? new Date(meeting.date).toLocaleString() : ''}
        </p>
      </section>

      <div className="toolbar">
        <div className="actions">
          <a className="btn btn-ghost" href={exportUrl(id, 'markdown')}>
            Download Markdown
          </a>
          <a className="btn btn-ghost" href={exportUrl(id, 'json')}>
            Download JSON
          </a>
        </div>
        <Link className="btn btn-primary" to="/">
          New meeting
        </Link>
      </div>

      {!!tags.length && (
        <div className="tags" style={{ marginBottom: '1rem' }}>
          {tags.map((tag) => (
            <span className="tag" key={tag}>
              {tag}
            </span>
          ))}
        </div>
      )}

      <div className="result-grid">
        <section className="panel section">
          <h2>Summary</h2>
          <p>{meeting.summary || 'No summary yet.'}</p>
        </section>

        <section className="panel section">
          <h2>Decisions</h2>
          {meeting.decisions?.length ? (
            <ul>
              {meeting.decisions.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : (
            <p className="meta">No decisions captured.</p>
          )}
        </section>

        <section className="panel section">
          <h2>Key points</h2>
          {meeting.key_points?.length ? (
            <ul>
              {meeting.key_points.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : (
            <p className="meta">No key points captured.</p>
          )}
        </section>

        <section className="panel section">
          <h2>Action items</h2>
          {meeting.action_items?.length ? (
            <table>
              <thead>
                <tr>
                  <th>Owner</th>
                  <th>Description</th>
                  <th>Due date</th>
                </tr>
              </thead>
              <tbody>
                {meeting.action_items.map((item) => (
                  <tr key={item.id || `${item.owner}-${item.description}`}>
                    <td>{item.owner || '—'}</td>
                    <td>{item.description}</td>
                    <td>{item.due_date || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="meta">No action items captured.</p>
          )}
        </section>
      </div>

      <section className="panel section" style={{ marginTop: '1rem' }}>
        <h2>Transcript</h2>
        <div className="transcript">{meeting.transcript || 'Empty transcript.'}</div>
      </section>
    </>
  )
}
