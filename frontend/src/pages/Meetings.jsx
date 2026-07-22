import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listMeetings, searchMeetings } from '../api'

export default function Meetings() {
  const [meetings, setMeetings] = useState([])
  const [q, setQ] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function loadAll() {
    setLoading(true)
    setError('')
    try {
      const data = await listMeetings()
      setMeetings(Array.isArray(data) ? data : data.meetings || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadAll()
  }, [])

  async function onSearch(event) {
    event.preventDefault()
    if (!q.trim()) {
      loadAll()
      return
    }
    setLoading(true)
    setError('')
    try {
      const data = await searchMeetings(q.trim())
      setMeetings(data.meetings || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <section className="hero">
        <h1>Meetings</h1>
        <p>Browse past minutes or search across transcripts.</p>
      </section>

      <section className="panel">
        <form className="toolbar" onSubmit={onSearch}>
          <div className="search-row">
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search transcripts, titles, summaries…"
            />
            <button className="btn btn-primary" type="submit">
              Search
            </button>
            <button className="btn btn-ghost" type="button" onClick={loadAll}>
              Clear
            </button>
          </div>
        </form>

        {loading && (
          <div className="loading">
            <div className="spinner" />
            Loading meetings…
          </div>
        )}
        {error && <div className="error">{error}</div>}

        {!loading && !error && meetings.length === 0 && (
          <div className="empty">
            No meetings yet. <Link to="/">Create one</Link>.
          </div>
        )}

        <ul className="meeting-list">
          {meetings.map((meeting) => (
            <li key={meeting.id}>
              <Link to={`/meetings/${meeting.id}`}>
                <h3>{meeting.title}</h3>
                <div className="meta">
                  {meeting.date ? new Date(meeting.date).toLocaleString() : ''}
                  {meeting.summary ? ` · ${meeting.summary.slice(0, 120)}` : ''}
                </div>
                {!!meeting.tags?.length && (
                  <div className="tags">
                    {meeting.tags.map((tag) => (
                      <span className="tag" key={tag}>
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </>
  )
}
