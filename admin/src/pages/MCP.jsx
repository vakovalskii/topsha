import { useState, useEffect } from 'react'
import { getMcpServers, addMcpServer, removeMcpServer, toggleMcpServer, refreshMcpServer, refreshAllMcp } from '../api'
import { useT } from '../i18n'

function MCP() {
  const { t } = useT()
  const [servers, setServers] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(null)
  const [toast, setToast] = useState(null)
  const [showAddModal, setShowAddModal] = useState(false)
  const [newServer, setNewServer] = useState({ name: '', url: '', description: '' })

  useEffect(() => {
    loadServers()
  }, [])

  async function loadServers() {
    try {
      const data = await getMcpServers()
      setServers(data.servers || [])
    } catch (e) {
      console.error('Failed to load MCP servers:', e)
      showToast('error', t('toast.failed_load', { msg: 'MCP servers' }))
    } finally {
      setLoading(false)
    }
  }

  function showToast(type, message) {
    setToast({ type, message })
    setTimeout(() => setToast(null), 3000)
  }

  async function handleAdd() {
    if (!newServer.name || !newServer.url) {
      showToast('error', t('toast.name_url_required'))
      return
    }
    try {
      await addMcpServer(newServer)
      showToast('success', t('toast.server_added', { name: newServer.name }))
      setShowAddModal(false)
      setNewServer({ name: '', url: '', description: '' })
      loadServers()
    } catch (e) {
      showToast('error', e.message)
    }
  }

  async function handleRemove(name) {
    if (!confirm(t('confirm.remove_server', { name }))) return
    try {
      await removeMcpServer(name)
      showToast('success', t('toast.server_removed', { name }))
      loadServers()
    } catch (e) {
      showToast('error', e.message)
    }
  }

  async function handleRefresh(name) {
    setRefreshing(name)
    try {
      const data = await refreshMcpServer(name)
      showToast('success', t('toast.server_refreshed', { count: data.tool_count || 0, name }))
      loadServers()
    } catch (e) {
      showToast('error', e.message)
    } finally {
      setRefreshing(null)
    }
  }

  async function handleToggle(name, currentEnabled) {
    try {
      await toggleMcpServer(name, !currentEnabled)
      showToast('success', t('toast.server_toggled', { name, state: !currentEnabled ? t('toast.enabled') : t('toast.disabled') }))
      loadServers()
    } catch (e) {
      showToast('error', e.message)
    }
  }

  async function handleRefreshAll() {
    setRefreshing('all')
    try {
      const data = await refreshAllMcp()
      showToast('success', t('toast.servers_refreshed', { servers: data.servers_refreshed || 0, tools: data.total_tools || 0 }))
      loadServers()
    } catch (e) {
      showToast('error', e.message)
    } finally {
      setRefreshing(null)
    }
  }

  if (loading) {
    return <div className="loading"><div className="spinner"></div>{t('common.loading')}</div>
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">{t('mcp.title')}</h1>
          <p className="page-subtitle">{t('mcp.subtitle')}</p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button 
            className="btn btn-secondary"
            onClick={handleRefreshAll}
            disabled={refreshing === 'all'}
          >
            {refreshing === 'all' ? t('mcp.refreshing') : t('mcp.refresh_all')}
          </button>
          <button className="btn btn-primary" onClick={() => setShowAddModal(true)}>
            {t('mcp.add_server')}
          </button>
        </div>
      </div>

      {servers.length === 0 ? (
        <div className="card">
          <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-dim)' }}>
            <p style={{ fontSize: '48px', marginBottom: '16px' }}>🔌</p>
            <p>{t('mcp.no_servers')}</p>
            <p style={{ fontSize: '13px', marginTop: '8px' }}>
              {t('mcp.no_servers_hint')}
            </p>
          </div>
        </div>
      ) : (
        <div className="grid grid-2">
          {servers.map(server => (
            <div className="card" key={server.name} style={{ opacity: server.enabled === false ? 0.6 : 1 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ flex: 1 }}>
                  <h3 style={{ fontSize: '16px', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <label className="toggle-switch" title={server.enabled !== false ? t('mcp.disable_server') : t('mcp.enable_server')} style={{ flexShrink: 0 }}>
                      <input 
                        type="checkbox" 
                        checked={server.enabled !== false}
                        onChange={() => handleToggle(server.name, server.enabled !== false)}
                      />
                      <span className="toggle-slider"></span>
                    </label>
                    <span style={{ 
                      display: 'inline-block',
                      width: '10px', 
                      height: '10px', 
                      minWidth: '10px',
                      minHeight: '10px',
                      borderRadius: '50%', 
                      flexShrink: 0,
                      background: server.enabled === false ? 'var(--text-dim)' : (server.status?.connected ? 'var(--success)' : 'var(--error)')
                    }}></span>
                    {server.name}
                    {server.enabled === false && <span className="badge" style={{ marginLeft: '8px' }}>{t('mcp.disabled')}</span>}
                  </h3>
                  <p style={{ color: 'var(--text-dim)', fontSize: '13px', marginBottom: '8px', wordBreak: 'break-all' }}>
                    {server.url}
                  </p>
                  {server.description && (
                    <p style={{ color: 'var(--text-dim)', fontSize: '12px', marginBottom: '12px' }}>
                      {server.description}
                    </p>
                  )}
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    <span className="badge badge-info">
                      {t('mcp.tools_count', { count: server.status?.tool_count || 0 })}
                    </span>
                    {server.status?.last_refresh && (
                      <span className="badge">
                        {new Date(server.status.last_refresh).toLocaleTimeString()}
                      </span>
                    )}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button 
                    className="btn btn-small btn-secondary"
                    onClick={() => handleRefresh(server.name)}
                    disabled={refreshing === server.name}
                    title={t('common.refresh')}
                  >
                    {refreshing === server.name ? '⏳' : '🔄'}
                  </button>
                  <button 
                    className="btn btn-small btn-danger"
                    onClick={() => handleRemove(server.name)}
                    title={t('common.delete')}
                  >
                    🗑️
                  </button>
                </div>
              </div>
              
              {server.status?.tools && server.status.tools.length > 0 && (
                <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid var(--border)' }}>
                  <p style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '8px' }}>{t('mcp.available_tools')}</p>
                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                    {server.status.tools.slice(0, 10).map(tool => (
                      <span key={tool} className="badge" style={{ fontSize: '11px' }}>
                        {tool}
                      </span>
                    ))}
                    {server.status.tools.length > 10 && (
                      <span className="badge" style={{ fontSize: '11px' }}>
                        {t('mcp.more', { count: server.status.tools.length - 10 })}
                      </span>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Add Server Modal */}
      {showAddModal && (
        <div className="modal-overlay" onClick={() => setShowAddModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h2 style={{ marginBottom: '20px' }}>{t('mcp.modal_title')}</h2>
            
            <div className="form-group">
              <label>{t('mcp.name')}</label>
              <input
                type="text"
                placeholder="e.g. filesystem"
                value={newServer.name}
                onChange={e => setNewServer({ ...newServer, name: e.target.value })}
              />
            </div>
            
            <div className="form-group">
              <label>{t('mcp.url')}</label>
              <input
                type="text"
                placeholder="e.g. http://mcp-server:3001"
                value={newServer.url}
                onChange={e => setNewServer({ ...newServer, url: e.target.value })}
              />
            </div>
            
            <div className="form-group">
              <label>{t('mcp.description')}</label>
              <input
                type="text"
                placeholder=""
                value={newServer.description}
                onChange={e => setNewServer({ ...newServer, description: e.target.value })}
              />
            </div>
            
            <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '20px' }}>
              <button className="btn btn-secondary" onClick={() => setShowAddModal(false)}>
                {t('mcp.cancel')}
              </button>
              <button className="btn btn-primary" onClick={handleAdd}>
                {t('mcp.add_server')}
              </button>
            </div>
          </div>
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

export default MCP
