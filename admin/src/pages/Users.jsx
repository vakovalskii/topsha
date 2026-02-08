import { useState, useEffect } from 'react'
import { getUsers, getSandboxes, killSandbox, getSessions, clearSession, getSessionDetail } from '../api'
import { useT } from '../i18n'

function Users() {
  const { t } = useT()
  const [sandboxes, setSandboxes] = useState([])
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState(null)
  const [activeTab, setActiveTab] = useState('sessions')
  const [selectedSession, setSelectedSession] = useState(null)
  const [sessionDetail, setSessionDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 10000)
    return () => clearInterval(interval)
  }, [])

  async function loadData() {
    try {
      const [sandboxData, sessionData] = await Promise.all([
        getSandboxes().catch(() => ({ sandboxes: [] })),
        getSessions().catch(() => ({ sessions: [] }))
      ])
      setSandboxes(sandboxData.sandboxes || [])
      setSessions(sessionData.sessions || [])
    } catch (e) {
      console.error('Failed to load data:', e)
    } finally {
      setLoading(false)
    }
  }

  async function handleKillSandbox(userId) {
    if (!confirm(t('confirm.kill_sandbox', { id: userId }))) return
    
    try {
      await killSandbox(userId)
      setSandboxes(sandboxes.filter(s => s.user_id !== userId))
      setToast({ type: 'success', message: t('toast.sandbox_killed') })
    } catch (e) {
      setToast({ type: 'error', message: e.message })
    }
    setTimeout(() => setToast(null), 3000)
  }

  async function handleClearSession(userId) {
    if (!confirm(t('confirm.clear_session', { id: userId }))) return
    
    try {
      await clearSession(userId)
      setSessions(sessions.map(s => 
        s.user_id === userId ? { ...s, message_count: 0, last_message: null } : s
      ))
      if (selectedSession === userId) {
        setSessionDetail(prev => prev ? { ...prev, history: [] } : null)
      }
      setToast({ type: 'success', message: t('toast.session_cleared') })
    } catch (e) {
      setToast({ type: 'error', message: e.message })
    }
    setTimeout(() => setToast(null), 3000)
  }

  async function handleViewSession(userId) {
    setSelectedSession(userId)
    setDetailLoading(true)
    try {
      const data = await getSessionDetail(userId)
      setSessionDetail(data)
    } catch (e) {
      setToast({ type: 'error', message: t('toast.failed_session') })
    } finally {
      setDetailLoading(false)
    }
  }

  if (loading) {
    return <div className="loading"><div className="spinner"></div>{t('common.loading')}</div>
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">{t('users.title')}</h1>
        <p className="page-subtitle">{t('users.subtitle')}</p>
      </div>

      <div className="tabs">
        <button 
          className={`tab ${activeTab === 'sandboxes' ? 'active' : ''}`}
          onClick={() => setActiveTab('sandboxes')}
        >
          {t('users.sandboxes_tab')} ({sandboxes.length})
        </button>
        <button 
          className={`tab ${activeTab === 'sessions' ? 'active' : ''}`}
          onClick={() => setActiveTab('sessions')}
        >
          {t('users.sessions_tab')} ({sessions.length})
        </button>
      </div>

      {activeTab === 'sandboxes' && (
        <div className="card">
          {sandboxes.length === 0 ? (
            <p style={{ color: 'var(--text-dim)', textAlign: 'center', padding: '20px' }}>
              {t('users.no_sandboxes')}
            </p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>{t('users.col_user_id')}</th>
                  <th>{t('users.col_container')}</th>
                  <th>{t('users.col_ports')}</th>
                  <th>{t('users.col_active')}</th>
                  <th>{t('users.col_actions')}</th>
                </tr>
              </thead>
              <tbody>
                {sandboxes.map(s => (
                  <tr key={s.user_id}>
                    <td><strong>{s.user_id}</strong></td>
                    <td><code style={{ fontSize: '12px' }}>{s.container_id?.slice(0, 12)}</code></td>
                    <td>{s.ports?.join(', ') || '-'}</td>
                    <td>{s.active_for || '-'}</td>
                    <td>
                      <button 
                        className="btn btn-danger btn-sm"
                        onClick={() => handleKillSandbox(s.user_id)}
                      >
                        {t('users.kill')}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {activeTab === 'sessions' && (
        <div style={{ display: 'flex', gap: '15px', width: '100%', maxWidth: '100%', overflow: 'hidden' }}>
          <div className="card" style={{ flex: selectedSession ? '1 1 55%' : '1', minWidth: 0, overflow: 'auto' }}>
            {sessions.length === 0 ? (
              <p style={{ color: 'var(--text-dim)', textAlign: 'center', padding: '20px' }}>
                {t('users.no_sessions')}
              </p>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>{t('users.col_user_id')}</th>
                    <th>{t('users.col_messages')}</th>
                    <th>{t('users.col_last_active')}</th>
                    <th>{t('users.col_actions')}</th>
                  </tr>
                </thead>
                <tbody>
                  {sessions.map(s => (
                    <tr 
                      key={s.user_id} 
                      style={{ 
                        cursor: 'pointer',
                        background: selectedSession === s.user_id ? 'var(--bg-accent)' : 'transparent'
                      }}
                      onClick={() => handleViewSession(s.user_id)}
                    >
                      <td>
                        <strong>{s.user_id}</strong>
                        {s.last_message && (
                          <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '4px', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {s.last_message}
                          </div>
                        )}
                      </td>
                      <td>{s.message_count || 0}</td>
                      <td style={{ fontSize: '12px' }}>{s.last_active || '-'}</td>
                      <td>
                        <button 
                          className="btn btn-secondary btn-sm"
                          onClick={(e) => { e.stopPropagation(); handleClearSession(s.user_id); }}
                        >
                          🗑️
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {selectedSession && (
            <div className="card" style={{ flex: '1 1 45%', minWidth: 0, maxHeight: '75vh', overflow: 'auto' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px', position: 'sticky', top: 0, background: 'var(--bg-card)', padding: '5px 0', zIndex: 1 }}>
                <h3 style={{ margin: 0, fontSize: '14px' }}>{t('users.user_label')} {selectedSession}</h3>
                <button 
                  className="btn btn-secondary btn-sm"
                  onClick={() => { setSelectedSession(null); setSessionDetail(null); }}
                >
                  {t('users.close')}
                </button>
              </div>

              {detailLoading ? (
                <div className="loading"><div className="spinner"></div></div>
              ) : sessionDetail ? (
                <>
                  {sessionDetail.history && sessionDetail.history.length > 0 ? (
                    <div style={{ maxHeight: '50vh', overflow: 'auto' }}>
                      {sessionDetail.history.map((msg, i) => (
                        <div key={i} style={{ marginBottom: '15px', padding: '10px', background: 'var(--bg-card)', borderRadius: '8px' }}>
                          <div style={{ color: 'var(--primary)', fontSize: '12px', marginBottom: '5px' }}>{t('users.user_msg')}</div>
                          <div style={{ marginBottom: '10px', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{msg.user}</div>
                          <div style={{ color: 'var(--success)', fontSize: '12px', marginBottom: '5px' }}>{t('users.assistant_msg')}</div>
                          <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', color: 'var(--text-dim)' }}>{msg.assistant}</div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p style={{ color: 'var(--text-dim)' }}>{t('users.no_messages')}</p>
                  )}

                  {sessionDetail.memory && (
                    <div style={{ marginTop: '20px' }}>
                      <h4 style={{ color: 'var(--warning)', marginBottom: '10px' }}>{t('users.memory_label')}</h4>
                      <pre style={{ background: 'var(--bg-card)', padding: '10px', borderRadius: '8px', overflow: 'auto', maxHeight: '200px', fontSize: '11px' }}>
                        {sessionDetail.memory}
                      </pre>
                    </div>
                  )}
                </>
              ) : null}
            </div>
          )}
        </div>
      )}

      {toast && (
        <div className={`toast ${toast.type}`}>
          {toast.message}
        </div>
      )}
    </div>
  )
}

export default Users
