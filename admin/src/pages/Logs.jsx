import { useState, useEffect, useRef } from 'react'
import { getLogs, getServices } from '../api'
import { useT } from '../i18n'

function Logs() {
  const { t } = useT()
  const [services, setServices] = useState([])
  const [activeService, setActiveService] = useState('core')
  const [logs, setLogs] = useState([])
  const [lines, setLines] = useState(100)
  const [loading, setLoading] = useState(true)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const logRef = useRef(null)

  useEffect(() => {
    loadServices()
  }, [])

  useEffect(() => {
    loadLogs()
    if (autoRefresh) {
      const interval = setInterval(loadLogs, 3000)
      return () => clearInterval(interval)
    }
  }, [activeService, lines, autoRefresh])

  async function loadServices() {
    try {
      const data = await getServices()
      setServices(data.map(s => s.name))
    } catch (e) {
      setServices(['core', 'bot', 'proxy', 'userbot'])
    }
  }

  async function loadLogs() {
    try {
      const data = await getLogs(activeService, lines)
      setLogs(data.logs || [])
      
      // Auto-scroll to bottom
      if (logRef.current) {
        logRef.current.scrollTop = logRef.current.scrollHeight
      }
    } catch (e) {
      console.error('Failed to load logs:', e)
    } finally {
      setLoading(false)
    }
  }

  function getLogClass(line) {
    const lower = line.toLowerCase()
    if (lower.includes('error') || lower.includes('exception') || lower.includes('failed')) return 'error'
    if (lower.includes('warning') || lower.includes('warn')) return 'warning'
    if (lower.includes('success') || lower.includes('✅') || lower.includes('done')) return 'success'
    return ''
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">{t('logs.title')}</h1>
        <p className="page-subtitle">{t('logs.subtitle')}</p>
      </div>

      {/* Controls */}
      <div className="card" style={{ marginBottom: '20px' }}>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center', flexWrap: 'wrap' }}>
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">{t('logs.service')}</label>
            <select 
              className="form-input" 
              style={{ width: '150px' }}
              value={activeService}
              onChange={e => setActiveService(e.target.value)}
            >
              {services.map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
          
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">{t('logs.lines')}</label>
            <select 
              className="form-input"
              style={{ width: '100px' }}
              value={lines}
              onChange={e => setLines(parseInt(e.target.value))}
            >
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={200}>200</option>
              <option value={500}>500</option>
            </select>
          </div>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginLeft: 'auto' }}>
            <label className="toggle-switch">
              <input 
                type="checkbox"
                checked={autoRefresh}
                onChange={e => setAutoRefresh(e.target.checked)}
              />
              <span className="toggle-slider"></span>
            </label>
            <span style={{ fontSize: '14px', color: 'var(--text-dim)' }}>{t('logs.auto_refresh')}</span>
          </div>
          
          <button className="btn btn-secondary" onClick={loadLogs}>
            {t('logs.refresh')}
          </button>
        </div>
      </div>

      {/* Log viewer */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">{activeService} {t('logs.logs_of')}</h2>
          <span style={{ color: 'var(--text-dim)', fontSize: '13px' }}>
            {logs.length} {t('logs.lines_count')}
          </span>
        </div>
        
        {loading ? (
          <div className="loading"><div className="spinner"></div>{t('common.loading')}</div>
        ) : (
          <div className="log-container" ref={logRef} style={{ height: '600px' }}>
            {logs.length === 0 ? (
              <p style={{ color: 'var(--text-dim)' }}>{t('logs.no_logs')}</p>
            ) : (
              logs.map((line, i) => (
                <div key={i} className={`log-line ${getLogClass(line)}`}>
                  {line}
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default Logs
