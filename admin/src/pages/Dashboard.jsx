import { useState, useEffect } from 'react'
import { getStats, getHealth, getServices } from '../api'

function Dashboard() {
  const [stats, setStats] = useState(null)
  const [services, setServices] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 10000)
    return () => clearInterval(interval)
  }, [])

  async function loadData() {
    try {
      const [statsData, servicesData] = await Promise.all([
        getStats().catch(() => ({})),
        getServices().catch(() => [])
      ])
      setStats(statsData)
      setServices(servicesData)
    } catch (e) {
      console.error('Failed to load dashboard:', e)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return <div className="loading"><div className="spinner"></div>Loading...</div>
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Dashboard</h1>
        <p className="page-subtitle">System overview and status</p>
      </div>

      {/* Stats */}
      <div className="grid grid-4">
        <div className="card stat">
          <div className="stat-value">{stats?.active_users || 0}</div>
          <div className="stat-label">Active Users</div>
        </div>
        <div className="card stat">
          <div className="stat-value">{stats?.active_sandboxes || 0}</div>
          <div className="stat-label">Active Sandboxes</div>
        </div>
        <div className="card stat">
          <div className="stat-value">{stats?.requests_today || 0}</div>
          <div className="stat-label">Requests Today</div>
        </div>
        <div className="card stat">
          <div className="stat-value">{stats?.tools_executed || 0}</div>
          <div className="stat-label">Tools Executed</div>
        </div>
      </div>

      {/* Services Status */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">Services</h2>
        </div>
        <table className="table">
          <thead>
            <tr>
              <th>Service</th>
              <th>Status</th>
              <th>Uptime</th>
              <th>Memory</th>
            </tr>
          </thead>
          <tbody>
            {services.map(s => (
              <tr key={s.name}>
                <td><strong>{s.name}</strong></td>
                <td>
                  <span className={`status ${s.status === 'running' ? 'online' : 'offline'}`}>
                    <span className="status-dot"></span>
                    {s.status}
                  </span>
                </td>
                <td>{s.uptime || '-'}</td>
                <td>{s.memory || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Recent Activity */}
      <div className="grid grid-2">
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Recent Requests</h2>
          </div>
          <div style={{ color: 'var(--text-dim)', fontSize: '14px' }}>
            {stats?.recent_requests?.length > 0 ? (
              stats.recent_requests.map((r, i) => (
                <div key={i} style={{ padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
                  <strong>@{r.username}</strong>: {r.message?.slice(0, 50)}...
                </div>
              ))
            ) : (
              <p>No recent activity</p>
            )}
          </div>
        </div>
        
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Security Events</h2>
          </div>
          <div style={{ color: 'var(--text-dim)', fontSize: '14px' }}>
            {stats?.security_events?.length > 0 ? (
              stats.security_events.map((e, i) => (
                <div key={i} style={{ padding: '8px 0', borderBottom: '1px solid var(--border)', color: 'var(--warning)' }}>
                  [{e.type}] {e.details?.slice(0, 50)}...
                </div>
              ))
            ) : (
              <p style={{ color: 'var(--success)' }}>✓ No security events</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default Dashboard
