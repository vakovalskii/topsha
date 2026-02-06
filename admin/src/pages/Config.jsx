import { useState, useEffect } from 'react'
import { getConfig, updateConfig, getServices, stopService, startService, getAccess, setAccessMode, getAllowlist, updateAllowlist } from '../api'

function Config() {
  const [config, setConfig] = useState({})
  const [services, setServices] = useState({})
  const [access, setAccess] = useState(null)
  const [allowlist, setAllowlist] = useState([])
  const [newUserId, setNewUserId] = useState('')
  const [loading, setLoading] = useState(true)
  const [servicesLoading, setServicesLoading] = useState(true)
  const [toggling, setToggling] = useState(null)
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState(null)
  const [activeTab, setActiveTab] = useState('access')

  useEffect(() => {
    loadConfig()
    loadServices()
    loadAccessSettings()
  }, [])

  async function loadAccessSettings() {
    try {
      const [accessData, allowlistData] = await Promise.all([
        getAccess(),
        getAllowlist()
      ])
      setAccess(accessData)
      setAllowlist(allowlistData.allowlist || [])
    } catch (e) {
      console.error('Failed to load access settings:', e)
    }
  }

  async function handleModeChange(mode) {
    try {
      await setAccessMode(mode)
      setAccess(prev => ({ ...prev, mode }))
      setToast({ type: 'success', message: `Mode set to: ${mode}` })
    } catch (e) {
      setToast({ type: 'error', message: e.message })
    }
    setTimeout(() => setToast(null), 3000)
  }

  async function handleAddUser() {
    const userId = parseInt(newUserId)
    if (!userId || isNaN(userId)) {
      setToast({ type: 'error', message: 'Enter valid user ID' })
      setTimeout(() => setToast(null), 3000)
      return
    }
    try {
      const result = await updateAllowlist(userId, 'add')
      setAllowlist(result.allowlist)
      setNewUserId('')
      setToast({ type: 'success', message: `User ${userId} added` })
    } catch (e) {
      setToast({ type: 'error', message: e.message })
    }
    setTimeout(() => setToast(null), 3000)
  }

  async function handleRemoveUser(userId) {
    try {
      const result = await updateAllowlist(userId, 'remove')
      setAllowlist(result.allowlist)
      setToast({ type: 'success', message: `User ${userId} removed` })
    } catch (e) {
      setToast({ type: 'error', message: e.message })
    }
    setTimeout(() => setToast(null), 3000)
  }

  async function loadServices() {
    setServicesLoading(true)
    try {
      const data = await getServices()
      const serviceMap = {}
      data.forEach(s => { serviceMap[s.name] = s })
      setServices(serviceMap)
    } catch (e) {
      console.error('Failed to load services:', e)
    } finally {
      setServicesLoading(false)
    }
  }

  async function handleToggleService(name, currentlyRunning) {
    setToggling(name)
    try {
      if (currentlyRunning) {
        await stopService(name)
        setToast({ type: 'success', message: `${name} stopped!` })
      } else {
        await startService(name)
        setToast({ type: 'success', message: `${name} started!` })
      }
      // Reload services after toggle
      await loadServices()
    } catch (e) {
      setToast({ type: 'error', message: e.message })
    } finally {
      setToggling(null)
      setTimeout(() => setToast(null), 3000)
    }
  }

  function isServiceRunning(name) {
    return services[name]?.status === 'running'
  }

  async function loadConfig() {
    try {
      const data = await getConfig()
      // Remove access from config - it's managed separately
      const { access: _, ...configWithoutAccess } = data
      setConfig(configWithoutAccess)
    } catch (e) {
      console.error('Failed to load config:', e)
    } finally {
      setLoading(false)
    }
  }

  async function handleSave() {
    setSaving(true)
    try {
      // Don't send access in config - it's managed separately
      const { access: _, ...configWithoutAccess } = config
      await updateConfig(configWithoutAccess)
      setToast({ type: 'success', message: 'Configuration saved!' })
    } catch (e) {
      setToast({ type: 'error', message: e.message })
    } finally {
      setSaving(false)
      setTimeout(() => setToast(null), 3000)
    }
  }

  function updateValue(section, key, value) {
    setConfig(prev => ({
      ...prev,
      [section]: {
        ...prev[section],
        [key]: value
      }
    }))
  }

  if (loading) {
    return <div className="loading"><div className="spinner"></div>Loading...</div>
  }

  const tabs = ['access', 'agent', 'bot', 'security', 'limits']

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Configuration</h1>
        <p className="page-subtitle">Adjust system settings</p>
      </div>

      <div className="tabs">
        {tabs.map(tab => (
          <button
            key={tab}
            className={`tab ${activeTab === tab ? 'active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      <div className="card">
        {activeTab === 'access' && (
          <>
            <div style={{ marginBottom: '24px' }}>
              <h3 style={{ marginBottom: '8px', color: '#e74c3c' }}>🔐 Access Control</h3>
              <p style={{ color: '#888', fontSize: '14px' }}>
                Start/stop services. When stopped, the container is completely down.
              </p>
            </div>
            
            {/* Access Mode */}
            <div style={{ marginBottom: '24px' }}>
              <h4 style={{ marginBottom: '12px' }}>🎯 Access Mode</h4>
              <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                <button 
                  className={`btn ${access?.mode === 'admin_only' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => handleModeChange('admin_only')}
                >
                  👑 Admin Only
                </button>
                <button 
                  className={`btn ${access?.mode === 'allowlist' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => handleModeChange('allowlist')}
                >
                  📋 Allowlist
                </button>
                <button 
                  className={`btn ${access?.mode === 'public' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => handleModeChange('public')}
                >
                  🌍 Public
                </button>
              </div>
              <p style={{ color: '#888', fontSize: '13px', marginTop: '8px' }}>
                {access?.mode === 'admin_only' && '🔒 Only admin (809532582) can use the bot'}
                {access?.mode === 'allowlist' && '📋 Admin + users in allowlist can use the bot'}
                {access?.mode === 'public' && '⚠️ Everyone can use the bot'}
              </p>
            </div>

            {/* Allowlist */}
            {access?.mode === 'allowlist' && (
              <div style={{ marginBottom: '24px', padding: '16px', background: '#1a1a2a', borderRadius: '8px' }}>
                <h4 style={{ marginBottom: '12px' }}>📋 Allowlist</h4>
                
                <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
                  <input 
                    type="text"
                    className="form-input"
                    placeholder="User ID (e.g. 123456789)"
                    value={newUserId}
                    onChange={e => setNewUserId(e.target.value)}
                    style={{ flex: 1 }}
                  />
                  <button className="btn btn-primary" onClick={handleAddUser}>
                    ➕ Add
                  </button>
                </div>

                {allowlist.length === 0 ? (
                  <p style={{ color: '#888', fontSize: '13px' }}>No users in allowlist (only admin has access)</p>
                ) : (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                    {allowlist.map(uid => (
                      <div key={uid} style={{ 
                        display: 'flex', 
                        alignItems: 'center', 
                        gap: '6px',
                        padding: '6px 12px',
                        background: '#252525',
                        borderRadius: '20px',
                        fontSize: '13px'
                      }}>
                        <span>{uid}</span>
                        <button 
                          onClick={() => handleRemoveUser(uid)}
                          style={{ 
                            background: 'none', 
                            border: 'none', 
                            color: '#e74c3c', 
                            cursor: 'pointer',
                            padding: '0 4px'
                          }}
                        >
                          ✕
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Services Control */}
            <h4 style={{ marginBottom: '12px' }}>🐳 Services</h4>
            {servicesLoading ? (
              <div style={{ padding: '20px', textAlign: 'center', color: '#888' }}>Loading services...</div>
            ) : (
              <>
                <div style={{ 
                  padding: '16px', 
                  background: isServiceRunning('bot') ? '#1a2a1a' : '#2a1a1a', 
                  borderRadius: '8px', 
                  marginBottom: '12px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}>
                  <div>
                    <span style={{ fontSize: '16px', fontWeight: '500' }}>🤖 Telegram Bot</span>
                    <p style={{ color: '#888', fontSize: '13px', marginTop: '4px' }}>
                      @localtopshbot - <span style={{ color: isServiceRunning('bot') ? '#2ecc71' : '#e74c3c' }}>
                        {services.bot?.status || 'unknown'}
                      </span>
                    </p>
                  </div>
                  <button 
                    className={`btn ${isServiceRunning('bot') ? 'btn-danger' : 'btn-primary'}`}
                    disabled={toggling === 'bot'}
                    onClick={() => handleToggleService('bot', isServiceRunning('bot'))}
                    style={{ minWidth: '100px' }}
                  >
                    {toggling === 'bot' ? '...' : isServiceRunning('bot') ? '⏹ Stop' : '▶ Start'}
                  </button>
                </div>

                <div style={{ 
                  padding: '16px', 
                  background: isServiceRunning('userbot') ? '#1a2a1a' : '#2a1a1a', 
                  borderRadius: '8px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}>
                  <div>
                    <span style={{ fontSize: '16px', fontWeight: '500' }}>👤 Userbot</span>
                    <p style={{ color: '#888', fontSize: '13px', marginTop: '4px' }}>
                      Personal account - <span style={{ color: isServiceRunning('userbot') ? '#2ecc71' : '#e74c3c' }}>
                        {services.userbot?.status || 'not deployed'}
                      </span>
                    </p>
                  </div>
                  <button 
                    className={`btn ${isServiceRunning('userbot') ? 'btn-danger' : 'btn-primary'}`}
                    disabled={toggling === 'userbot'}
                    onClick={() => handleToggleService('userbot', isServiceRunning('userbot'))}
                    style={{ minWidth: '100px' }}
                  >
                    {toggling === 'userbot' ? '...' : isServiceRunning('userbot') ? '⏹ Stop' : '▶ Start'}
                  </button>
                </div>

                <div style={{ marginTop: '16px' }}>
                  <button className="btn btn-secondary" onClick={() => { loadServices(); loadAccessSettings(); }}>
                    🔄 Refresh
                  </button>
                </div>
              </>
            )}
          </>
        )}

        {activeTab === 'agent' && (
          <>
            <div className="form-group">
              <label className="form-label">Model</label>
              <input 
                type="text"
                className="form-input"
                value={config.agent?.model || ''}
                onChange={e => updateValue('agent', 'model', e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Max Iterations</label>
              <div className="range-container">
                <input 
                  type="range"
                  className="range-input"
                  min="5"
                  max="50"
                  value={config.agent?.max_iterations || 30}
                  onChange={e => updateValue('agent', 'max_iterations', parseInt(e.target.value))}
                />
                <span className="range-value">{config.agent?.max_iterations || 30}</span>
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Max History Messages</label>
              <div className="range-container">
                <input 
                  type="range"
                  className="range-input"
                  min="5"
                  max="30"
                  value={config.agent?.max_history || 10}
                  onChange={e => updateValue('agent', 'max_history', parseInt(e.target.value))}
                />
                <span className="range-value">{config.agent?.max_history || 10}</span>
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Tool Timeout (seconds)</label>
              <div className="range-container">
                <input 
                  type="range"
                  className="range-input"
                  min="30"
                  max="300"
                  value={config.agent?.tool_timeout || 120}
                  onChange={e => updateValue('agent', 'tool_timeout', parseInt(e.target.value))}
                />
                <span className="range-value">{config.agent?.tool_timeout || 120}s</span>
              </div>
            </div>
          </>
        )}

        {activeTab === 'bot' && (
          <>
            <div className="toggle">
              <span className="toggle-label">Enable Reactions</span>
              <label className="toggle-switch">
                <input 
                  type="checkbox"
                  checked={config.bot?.reactions_enabled ?? true}
                  onChange={e => updateValue('bot', 'reactions_enabled', e.target.checked)}
                />
                <span className="toggle-slider"></span>
              </label>
            </div>
            <div className="toggle">
              <span className="toggle-label">Enable Random Thoughts</span>
              <label className="toggle-switch">
                <input 
                  type="checkbox"
                  checked={config.bot?.thoughts_enabled ?? true}
                  onChange={e => updateValue('bot', 'thoughts_enabled', e.target.checked)}
                />
                <span className="toggle-slider"></span>
              </label>
            </div>
            <div className="form-group" style={{ marginTop: '16px' }}>
              <label className="form-label">Reaction Chance</label>
              <div className="range-container">
                <input 
                  type="range"
                  className="range-input"
                  min="0"
                  max="100"
                  value={(config.bot?.reaction_chance || 0.15) * 100}
                  onChange={e => updateValue('bot', 'reaction_chance', parseInt(e.target.value) / 100)}
                />
                <span className="range-value">{Math.round((config.bot?.reaction_chance || 0.15) * 100)}%</span>
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Ignore Chance</label>
              <div className="range-container">
                <input 
                  type="range"
                  className="range-input"
                  min="0"
                  max="30"
                  value={(config.bot?.ignore_chance || 0.05) * 100}
                  onChange={e => updateValue('bot', 'ignore_chance', parseInt(e.target.value) / 100)}
                />
                <span className="range-value">{Math.round((config.bot?.ignore_chance || 0.05) * 100)}%</span>
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Max Message Length</label>
              <input 
                type="number"
                className="form-input"
                value={config.bot?.max_length || 4000}
                onChange={e => updateValue('bot', 'max_length', parseInt(e.target.value))}
              />
            </div>
          </>
        )}

        {activeTab === 'security' && (
          <>
            <div className="toggle">
              <span className="toggle-label">Command Approval Required</span>
              <label className="toggle-switch">
                <input 
                  type="checkbox"
                  checked={config.security?.approval_required ?? true}
                  onChange={e => updateValue('security', 'approval_required', e.target.checked)}
                />
                <span className="toggle-slider"></span>
              </label>
            </div>
            <div className="toggle">
              <span className="toggle-label">Block Sensitive Patterns</span>
              <label className="toggle-switch">
                <input 
                  type="checkbox"
                  checked={config.security?.block_patterns ?? true}
                  onChange={e => updateValue('security', 'block_patterns', e.target.checked)}
                />
                <span className="toggle-slider"></span>
              </label>
            </div>
            <div className="toggle">
              <span className="toggle-label">Sandbox Isolation</span>
              <label className="toggle-switch">
                <input 
                  type="checkbox"
                  checked={config.security?.sandbox_enabled ?? true}
                  onChange={e => updateValue('security', 'sandbox_enabled', e.target.checked)}
                />
                <span className="toggle-slider"></span>
              </label>
            </div>
            <div className="form-group" style={{ marginTop: '16px' }}>
              <label className="form-label">Max Blocked Commands Before Lock</label>
              <div className="range-container">
                <input 
                  type="range"
                  className="range-input"
                  min="1"
                  max="10"
                  value={config.security?.max_blocked || 3}
                  onChange={e => updateValue('security', 'max_blocked', parseInt(e.target.value))}
                />
                <span className="range-value">{config.security?.max_blocked || 3}</span>
              </div>
            </div>
          </>
        )}

        {activeTab === 'limits' && (
          <>
            <div className="form-group">
              <label className="form-label">Sandbox TTL (minutes)</label>
              <div className="range-container">
                <input 
                  type="range"
                  className="range-input"
                  min="5"
                  max="60"
                  value={config.limits?.sandbox_ttl || 10}
                  onChange={e => updateValue('limits', 'sandbox_ttl', parseInt(e.target.value))}
                />
                <span className="range-value">{config.limits?.sandbox_ttl || 10} min</span>
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Sandbox Memory Limit</label>
              <input 
                type="text"
                className="form-input"
                value={config.limits?.sandbox_memory || '512m'}
                onChange={e => updateValue('limits', 'sandbox_memory', e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Workspace Disk Limit (MB)</label>
              <div className="range-container">
                <input 
                  type="range"
                  className="range-input"
                  min="100"
                  max="2000"
                  step="100"
                  value={config.limits?.workspace_limit || 500}
                  onChange={e => updateValue('limits', 'workspace_limit', parseInt(e.target.value))}
                />
                <span className="range-value">{config.limits?.workspace_limit || 500} MB</span>
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Max Concurrent Users</label>
              <div className="range-container">
                <input 
                  type="range"
                  className="range-input"
                  min="1"
                  max="50"
                  value={config.limits?.max_concurrent || 10}
                  onChange={e => updateValue('limits', 'max_concurrent', parseInt(e.target.value))}
                />
                <span className="range-value">{config.limits?.max_concurrent || 10}</span>
              </div>
            </div>
          </>
        )}

        <div style={{ marginTop: '24px', display: 'flex', gap: '12px' }}>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
            {saving ? 'Saving...' : '💾 Save Changes'}
          </button>
          <button className="btn btn-secondary" onClick={loadConfig}>
            🔄 Reset
          </button>
        </div>
      </div>

      {toast && (
        <div className={`toast ${toast.type}`}>
          {toast.message}
        </div>
      )}
    </div>
  )
}

export default Config
