import { Routes, Route, NavLink } from 'react-router-dom'
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
  return (
    <div className="app">
      <aside className="sidebar">
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
