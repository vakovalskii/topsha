import { useState, useEffect } from 'react'
import { Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { useT } from './i18n'
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
  const { t } = useT()
  
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
          <NavLink to="/" end>{t('nav.dashboard')}</NavLink>
          <NavLink to="/services">{t('nav.services')}</NavLink>
          <NavLink to="/config">{t('nav.config')}</NavLink>
          <NavLink to="/prompt">{t('nav.prompt')}</NavLink>
          <NavLink to="/security">{t('nav.security')}</NavLink>
          <NavLink to="/tools">{t('nav.tools')}</NavLink>
          <NavLink to="/mcp">{t('nav.mcp')}</NavLink>
          <NavLink to="/skills">{t('nav.skills')}</NavLink>
          <NavLink to="/tasks">{t('nav.tasks')}</NavLink>
          <NavLink to="/users">{t('nav.users')}</NavLink>
          <NavLink to="/logs">{t('nav.logs')}</NavLink>
        </nav>
        <div className="sidebar-footer">
          {t('footer.version')}
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
