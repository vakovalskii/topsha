import { useState, useEffect } from 'react'
import { getServices, getServiceStats, restartService, stopService, startService } from '../api'
import { useT } from '../i18n'

function Services() {
  const { t } = useT()
  const [services, setServices] = useState([])
  const [stats, setStats] = useState({})
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(null)
  const [toast, setToast] = useState(null)

  useEffect(() => {
    loadServices()
    const interval = setInterval(loadServices, 5000)
    return () => clearInterval(interval)
  }, [])

  async function loadServices() {
    try {
      const data = await getServices()
      setServices(data || [])
    } catch (e) {
      console.error('Failed to load services:', e)
    } finally {
      setLoading(false)
    }
  }

  async function loadStats(name) {
    try {
      const data = await getServiceStats(name)
      setStats(prev => ({ ...prev, [name]: data }))
    } catch (e) {
      console.error(`Failed to load stats for ${name}:`, e)
    }
  }

  async function handleAction(name, action) {
    setActionLoading(`${name}-${action}`)
    try {
      if (action === 'restart') await restartService(name)
      else if (action === 'stop') await stopService(name)
      else if (action === 'start') await startService(name)
      
      setToast({ type: 'success', message: `${name} ${action}ed successfully` })
      setTimeout(loadServices, 1000)
    } catch (e) {
      setToast({ type: 'error', message: e.message })
    } finally {
      setActionLoading(null)
      setTimeout(() => setToast(null), 3000)
    }
  }

  if (loading) {
    return <div className="loading"><div className="spinner"></div>{t('common.loading')}</div>
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">{t('services.title')}</h1>
        <p className="page-subtitle">{t('services.subtitle')}</p>
      </div>

      <div className="grid grid-2">
        {services.map(s => (
          <div className="card" key={s.name}>
            <div className="card-header">
              <h2 className="card-title">{s.name}</h2>
              <span className={`status ${s.status === 'running' ? 'online' : 'offline'}`}>
                <span className="status-dot"></span>
                {s.status}
              </span>
            </div>
            
            <div style={{ marginBottom: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span style={{ color: 'var(--text-dim)' }}>{t('services.image')}</span>
                <span style={{ fontSize: '12px' }}>{s.image?.split(':')[0] || '-'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span style={{ color: 'var(--text-dim)' }}>{t('services.uptime')}</span>
                <span>{s.uptime || '-'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span style={{ color: 'var(--text-dim)' }}>{t('services.memory_label')}</span>
                <span>
                  {stats[s.name]?.memory || '-'}
                  {!stats[s.name] && s.status === 'running' && (
                    <button 
                      onClick={() => loadStats(s.name)}
                      style={{ marginLeft: '8px', fontSize: '11px', color: 'var(--accent)', background: 'none', border: 'none', cursor: 'pointer' }}
                    >
                      {t('services.load')}
                    </button>
                  )}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span style={{ color: 'var(--text-dim)' }}>{t('services.cpu')}</span>
                <span>{stats[s.name]?.cpu || '-'}</span>
              </div>
              {s.ports && (
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-dim)' }}>{t('services.ports')}</span>
                  <span>{s.ports}</span>
                </div>
              )}
            </div>

            <div style={{ display: 'flex', gap: '8px' }}>
              {s.status === 'running' ? (
                <>
                  <button 
                    className="btn btn-secondary btn-sm"
                    onClick={() => handleAction(s.name, 'restart')}
                    disabled={actionLoading === `${s.name}-restart`}
                  >
                    {actionLoading === `${s.name}-restart` ? '...' : t('services.restart')}
                  </button>
                  <button 
                    className="btn btn-danger btn-sm"
                    onClick={() => handleAction(s.name, 'stop')}
                    disabled={actionLoading === `${s.name}-stop`}
                  >
                    {actionLoading === `${s.name}-stop` ? '...' : t('services.stop')}
                  </button>
                </>
              ) : (
                <button 
                  className="btn btn-primary btn-sm"
                  onClick={() => handleAction(s.name, 'start')}
                  disabled={actionLoading === `${s.name}-start`}
                >
                  {actionLoading === `${s.name}-start` ? '...' : t('services.start')}
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {toast && (
        <div className={`toast ${toast.type}`}>
          {toast.message}
        </div>
      )}
    </div>
  )
}

export default Services
