import { NavLink, Route, Routes } from 'react-router-dom'
import Home from './pages/Home'
import MeetingDetail from './pages/MeetingDetail'
import Meetings from './pages/Meetings'

export default function App() {
  return (
    <div className="app-shell">
      <header className="topnav">
        <div className="brand-lockup">
          <NavLink to="/" className="brand">
            Meeting <span>Assist</span>
          </NavLink>
          <div className="brand-sub">Audio or notes → clear minutes</div>
        </div>
        <nav className="nav-links">
          <NavLink to="/" end>
            New meeting
          </NavLink>
          <NavLink to="/meetings">Meetings</NavLink>
        </nav>
      </header>

      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/meetings" element={<Meetings />} />
        <Route path="/meetings/:id" element={<MeetingDetail />} />
      </Routes>
    </div>
  )
}
