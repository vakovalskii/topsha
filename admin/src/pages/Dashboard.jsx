import { useState, useEffect } from 'react'
import { getStats, getHealth, getServices, fetchApi } from '../api'
import { useT } from '../i18n'

function Dashboard() {
  const { t } = useT()
  const [stats, setStats] = useState(null)
  const [services, setServices] = useState([])
  const [systemMetrics, setSystemMetrics] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 5000) // More frequent for metrics
    return () => clearInterval(interval)
  }, [])

  async function loadData() {
    try {
      const [statsData, servicesData, metricsData] = await Promise.all([
        getStats().catch(() => ({})),
        getServices().catch(() => []),
        fetchApi('/system/metrics').catch(() => null)
      ])
      setStats(statsData)
      setServices(servicesData)
      setSystemMetrics(metricsData)
    } catch (e) {
      console.error('Failed to load dashboard:', e)
    } finally {
      setLoading(false)
    }
  }
  
  // Format bytes to human readable
  function formatBytes(bytes, decimals = 1) {
    if (!bytes) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(decimals)) + ' ' + sizes[i]
  }
  
  // Format network speed
  function formatSpeed(bytesPerSec) {
    if (!bytesPerSec) return '0 B/s'
    return formatBytes(bytesPerSec) + '/s'
  }

  if (loading) {
    return <div className="loading"><div className="spinner"></div>{t('common.loading')}</div>
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">{t('dashboard.title')}</h1>
        <p className="page-subtitle">{t('dashboard.subtitle')}</p>
      </div>

      {/* System Metrics */}
      {systemMetrics && (
        <div className="grid grid-4" style={{ marginBottom: '8px' }}>
          <div className="card stat">
            <div className="stat-value" style={{ 
              color: systemMetrics.cpu_percent > 80 ? 'var(--danger)' : 
                     systemMetrics.cpu_percent > 50 ? 'var(--warning)' : 'var(--success)'
            }}>
              {systemMetrics.cpu_percent?.toFixed(1) || 0}%
            </div>
            <div className="stat-label">{t('dashboard.cpu')}</div>
            <div style={{ marginTop: '8px', height: '4px', background: 'var(--bg-input)', borderRadius: '2px', overflow: 'hidden' }}>
              <div style={{ 
                width: `${systemMetrics.cpu_percent || 0}%`, 
                height: '100%', 
                background: systemMetrics.cpu_percent > 80 ? 'var(--danger)' : 
                           systemMetrics.cpu_percent > 50 ? 'var(--warning)' : 'var(--success)',
                transition: 'width 0.3s ease'
              }} />
            </div>
          </div>
          <div className="card stat">
            <div className="stat-value" style={{ 
              color: systemMetrics.memory_percent > 80 ? 'var(--danger)' : 
                     systemMetrics.memory_percent > 50 ? 'var(--warning)' : 'var(--success)'
            }}>
              {systemMetrics.memory_percent?.toFixed(1) || 0}%
            </div>
            <div className="stat-label">{t('dashboard.memory_label')}</div>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '4px' }}>
              {formatBytes(systemMetrics.memory_used)} / {formatBytes(systemMetrics.memory_total)}
            </div>
            <div style={{ marginTop: '4px', height: '4px', background: 'var(--bg-input)', borderRadius: '2px', overflow: 'hidden' }}>
              <div style={{ 
                width: `${systemMetrics.memory_percent || 0}%`, 
                height: '100%', 
                background: systemMetrics.memory_percent > 80 ? 'var(--danger)' : 
                           systemMetrics.memory_percent > 50 ? 'var(--warning)' : 'var(--success)',
                transition: 'width 0.3s ease'
              }} />
            </div>
          </div>
          <div className="card stat">
            <div className="stat-value" style={{ 
              color: systemMetrics.disk_percent > 90 ? 'var(--danger)' : 
                     systemMetrics.disk_percent > 70 ? 'var(--warning)' : 'var(--success)'
            }}>
              {systemMetrics.disk_percent?.toFixed(1) || 0}%
            </div>
            <div className="stat-label">{t('dashboard.disk')}</div>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '4px' }}>
              {formatBytes(systemMetrics.disk_used)} / {formatBytes(systemMetrics.disk_total)}
            </div>
            <div style={{ marginTop: '4px', height: '4px', background: 'var(--bg-input)', borderRadius: '2px', overflow: 'hidden' }}>
              <div style={{ 
                width: `${systemMetrics.disk_percent || 0}%`, 
                height: '100%', 
                background: systemMetrics.disk_percent > 90 ? 'var(--danger)' : 
                           systemMetrics.disk_percent > 70 ? 'var(--warning)' : 'var(--success)',
                transition: 'width 0.3s ease'
              }} />
            </div>
          </div>
          <div className="card stat">
            <div className="stat-value" style={{ fontSize: '24px', color: 'var(--accent)' }}>
              ↓{formatSpeed(systemMetrics.network_recv_rate)}
            </div>
            <div className="stat-label">{t('dashboard.network')}</div>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '4px' }}>
              ↑{formatSpeed(systemMetrics.network_sent_rate)}
            </div>
          </div>
        </div>
      )}

      {/* Agent Stats */}
      <div className="grid grid-4">
        <div className="card stat">
          <div className="stat-value">{stats?.active_users || 0}</div>
          <div className="stat-label">{t('dashboard.active_users')}</div>
        </div>
        <div className="card stat">
          <div className="stat-value">{stats?.active_sandboxes || 0}</div>
          <div className="stat-label">{t('dashboard.active_sandboxes')}</div>
        </div>
        <div className="card stat">
          <div className="stat-value">{stats?.requests_today || 0}</div>
          <div className="stat-label">{t('dashboard.requests_today')}</div>
        </div>
        <div className="card stat">
          <div className="stat-value">{stats?.tools_executed || 0}</div>
          <div className="stat-label">{t('dashboard.tools_executed')}</div>
        </div>
      </div>

      {/* Services Status */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">{t('dashboard.services_table')}</h2>
        </div>
        <table className="table">
          <thead>
            <tr>
              <th>{t('dashboard.col_service')}</th>
              <th>{t('dashboard.col_status')}</th>
              <th>{t('dashboard.col_uptime')}</th>
              <th>{t('dashboard.col_memory')}</th>
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
            <h2 className="card-title">{t('dashboard.recent_requests')}</h2>
          </div>
          <div style={{ color: 'var(--text-dim)', fontSize: '14px' }}>
            {stats?.recent_requests?.length > 0 ? (
              stats.recent_requests.map((r, i) => (
                <div key={i} style={{ padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
                  <strong>@{r.username}</strong>: {r.message?.slice(0, 50)}...
                </div>
              ))
            ) : (
              <p>{t('dashboard.no_activity')}</p>
            )}
          </div>
        </div>
        
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">{t('dashboard.security_events')}</h2>
          </div>
          <div style={{ color: 'var(--text-dim)', fontSize: '14px' }}>
            {stats?.security_events?.length > 0 ? (
              stats.security_events.map((e, i) => (
                <div key={i} style={{ padding: '8px 0', borderBottom: '1px solid var(--border)', color: 'var(--warning)' }}>
                  [{e.type}] {e.details?.slice(0, 50)}...
                </div>
              ))
            ) : (
              <p style={{ color: 'var(--success)' }}>{t('dashboard.no_security')}</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default Dashboard
