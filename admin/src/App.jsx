import { useState, useEffect } from 'react'
import { Routes, Route, NavLink, useLocation } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Services from './pages/Services'
import Config from './pages/Config'
import Security from './pages/Security'
import Logs from './pages/Logs'
import Users from './pages/Users'
import Tools from './pages/Tools'
import MCP from './pages/MCP'
import Skills from './pages/Skills'
import Tasks from './pages/Tasks'
import Prompt from './pages/Prompt'

function App() {
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()
  
  // Close menu on route change
  useEffect(() => {
    setMenuOpen(false)
  }, [location])
  
  // Close menu on escape
  useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === 'Escape') setMenuOpen(false)
    }
    window.addEventListener('keydown', handleEsc)
    return () => window.removeEventListener('keydown', handleEsc)
  }, [])

  return (
    <div className="app">
      {/* Mobile header */}
      <header className="mobile-header">
        <h1>Topsha</h1>
        <button 
          className={`hamburger ${menuOpen ? 'active' : ''}`}
          onClick={() => setMenuOpen(!menuOpen)}
          aria-label="Toggle menu"
        >
          <span></span>
          <span></span>
          <span></span>
        </button>
      </header>
      
      {/* Overlay for mobile */}
      <div 
        className={`sidebar-overlay ${menuOpen ? 'visible' : ''}`}
        onClick={() => setMenuOpen(false)}
      />
      
      <aside className={`sidebar ${menuOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <h1>Topsha</h1>
        </div>
        <nav className="sidebar-nav">
          <NavLink to="/" end>📊 Dashboard</NavLink>
          <NavLink to="/services">🐳 Services</NavLink>
          <NavLink to="/config">⚙️ Config</NavLink>
          <NavLink to="/prompt">📝 Prompt</NavLink>
          <NavLink to="/security">🛡️ Security</NavLink>
          <NavLink to="/tools">🔧 Tools</NavLink>
          <NavLink to="/mcp">🔌 MCP</NavLink>
          <NavLink to="/skills">🎯 Skills</NavLink>
          <NavLink to="/tasks">⏰ Tasks</NavLink>
          <NavLink to="/users">👥 Users</NavLink>
          <NavLink to="/logs">📜 Logs</NavLink>
        </nav>
        <div className="sidebar-footer">
          AI Agent Framework v1.0
        </div>
      </aside>
      <main className="main">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/services" element={<Services />} />
          <Route path="/config" element={<Config />} />
          <Route path="/prompt" element={<Prompt />} />
          <Route path="/security" element={<Security />} />
          <Route path="/tools" element={<Tools />} />
          <Route path="/mcp" element={<MCP />} />
          <Route path="/skills" element={<Skills />} />
          <Route path="/tasks" element={<Tasks />} />
          <Route path="/users" element={<Users />} />
          <Route path="/logs" element={<Logs />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
