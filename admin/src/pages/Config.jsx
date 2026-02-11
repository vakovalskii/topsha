import { useState, useEffect } from 'react'
import { getConfig, updateConfig, getServices, stopService, startService, getAccess, setAccessMode, setAdminId, getAllowlist, updateAllowlist, getSearchConfig, updateSearchConfig, getZAIKeyStatus, updateZAIKey, testZAIConnection, getASRConfig, updateASRConfig, getASRHealth, testASRConnection, getTimezone, updateTimezone, getLocale, updateLocale, getGoogleStatus, getGoogleAuthUrl, authorizeGoogle, disconnectGoogle, updateGoogleCredentials } from '../api'
import { useT } from '../i18n'

function Config() {
  const { t } = useT()
  const [config, setConfig] = useState({})
  const [services, setServices] = useState({})
  const [access, setAccess] = useState(null)
  const [allowlist, setAllowlist] = useState([])
  const [newUserId, setNewUserId] = useState('')
  const [editingAdminId, setEditingAdminId] = useState(false)
  const [newAdminId, setNewAdminId] = useState('')
  const [loading, setLoading] = useState(true)
  const [servicesLoading, setServicesLoading] = useState(true)
  const [toggling, setToggling] = useState(null)
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState(null)
  const [activeTab, setActiveTab] = useState('access')
  const [searchConfig, setSearchConfig] = useState(null)
  const [searchSaving, setSearchSaving] = useState(false)
  const [zaiKeyStatus, setZaiKeyStatus] = useState(null)
  const [zaiKeyInput, setZaiKeyInput] = useState('')
  const [zaiKeySaving, setZaiKeySaving] = useState(false)
  const [zaiTesting, setZaiTesting] = useState(false)
  const [asrConfig, setAsrConfig] = useState(null)
  const [asrSaving, setAsrSaving] = useState(false)
  const [asrHealth, setAsrHealth] = useState(null)
  const [asrTesting, setAsrTesting] = useState(false)
  const [googleStatus, setGoogleStatus] = useState(null)
  const [googleAuthUrl, setGoogleAuthUrl] = useState(null)
  const [googleCode, setGoogleCode] = useState('')
  const [googleAuthorizing, setGoogleAuthorizing] = useState(false)
  const [googleClientId, setGoogleClientId] = useState('')
  const [googleClientSecret, setGoogleClientSecret] = useState('')
  const [googleSaving, setGoogleSaving] = useState(false)
  const [tzData, setTzData] = useState(null)
  const [tzSaving, setTzSaving] = useState(false)
  const [selectedTz, setSelectedTz] = useState('')
  const [localeData, setLocaleData] = useState(null)
  const [selectedLang, setSelectedLang] = useState('')
  const [localeSaving, setLocaleSaving] = useState(false)

  useEffect(() => {
    loadConfig()
    loadServices()
    loadAccessSettings()
    loadSearchConfig()
    loadASRConfig()
    loadGoogleStatus()
    loadTimezone()
    loadLocale()
  }, [])

  async function loadSearchConfig() {
    try {
      const data = await getSearchConfig()
      setSearchConfig(data)
      // Also load ZAI key status
      try {
        const keyStatus = await getZAIKeyStatus()
        setZaiKeyStatus(keyStatus)
      } catch (e) {
        console.error('Failed to load ZAI key status:', e)
      }
    } catch (e) {
      console.error('Failed to load search config:', e)
    }
  }

  async function handleZAIKeySave() {
    if (!zaiKeyInput || zaiKeyInput.length < 10) {
      setToast({ type: 'error', message: 'API key is too short' })
      setTimeout(() => setToast(null), 3000)
      return
    }
    setZaiKeySaving(true)
    try {
      const result = await updateZAIKey(zaiKeyInput)
      setZaiKeyStatus({ configured: true, masked_key: result.masked_key, source: 'data' })
      setZaiKeyInput('')
      setToast({ type: 'success', message: '✅ API key saved! Restart proxy to apply.' })
    } catch (e) {
      setToast({ type: 'error', message: e.message })
    } finally {
      setZaiKeySaving(false)
      setTimeout(() => setToast(null), 5000)
    }
  }

  async function handleZAITest() {
    setZaiTesting(true)
    try {
      // Test with input key if provided, otherwise use saved key
      const result = await testZAIConnection(zaiKeyInput || null)
      if (result.status === 'ready') {
        setToast({ type: 'success', message: '✅ Z.AI connection successful!' })
      } else {
        setToast({ type: 'error', message: result.error || 'Connection failed' })
      }
    } catch (e) {
      setToast({ type: 'error', message: e.message })
    } finally {
      setZaiTesting(false)
      setTimeout(() => setToast(null), 3000)
    }
  }

  async function loadASRConfig() {
    try {
      const data = await getASRConfig()
      setAsrConfig(data)
      // Also check health
      try {
        const health = await getASRHealth()
        setAsrHealth(health)
      } catch (e) {
        setAsrHealth({ status: 'error', error: e.message })
      }
    } catch (e) {
      console.error('Failed to load ASR config:', e)
    }
  }

  async function handleASRSave() {
    setAsrSaving(true)
    try {
      await updateASRConfig(asrConfig)
      setToast({ type: 'success', message: t('toast.asr_saved') })
      // Re-check health
      try {
        const health = await getASRHealth()
        setAsrHealth(health)
      } catch (e) {}
    } catch (e) {
      setToast({ type: 'error', message: e.message })
    } finally {
      setAsrSaving(false)
      setTimeout(() => setToast(null), 3000)
    }
  }

  async function handleASRTest() {
    if (!asrConfig?.url) {
      setToast({ type: 'error', message: 'URL is required' })
      setTimeout(() => setToast(null), 3000)
      return
    }
    setAsrTesting(true)
    try {
      const result = await testASRConnection(
        asrConfig.url,
        asrConfig.api_type || 'openai',
        asrConfig.api_key || ''
      )
      setAsrHealth(result)
      if (result.status === 'ready') {
        setToast({ type: 'success', message: '✅ Connection successful!' })
      } else {
        setToast({ type: 'error', message: result.error || `Error: ${result.http_status || 'connection failed'}` })
      }
    } catch (e) {
      setToast({ type: 'error', message: e.message })
      setAsrHealth({ status: 'error', error: e.message })
    } finally {
      setAsrTesting(false)
      setTimeout(() => setToast(null), 3000)
    }
  }

  async function loadGoogleStatus() {
    try {
      const data = await getGoogleStatus()
      setGoogleStatus(data)
      // Load client credentials if available
      if (data.client_id_saved) {
        setGoogleClientId(data.client_id_saved)
      }
    } catch (e) {
      console.error('Failed to load Google status:', e)
    }
  }

  async function handleGoogleSaveCredentials() {
    if (!googleClientId.trim() || !googleClientSecret.trim()) {
      setToast({ type: 'error', message: 'Введите Client ID и Client Secret' })
      setTimeout(() => setToast(null), 3000)
      return
    }
    setGoogleSaving(true)
    try {
      await updateGoogleCredentials(googleClientId.trim(), googleClientSecret.trim())
      setToast({ type: 'success', message: '✅ Credentials сохранены' })
      setGoogleClientSecret('')  // Clear secret after save
      loadGoogleStatus()
    } catch (e) {
      setToast({ type: 'error', message: e.message })
    } finally {
      setGoogleSaving(false)
      setTimeout(() => setToast(null), 3000)
    }
  }

  async function handleGoogleGetAuthUrl() {
    try {
      const data = await getGoogleAuthUrl()
      setGoogleAuthUrl(data.auth_url)
      // Open in new tab
      window.open(data.auth_url, '_blank')
    } catch (e) {
      setToast({ type: 'error', message: e.message })
      setTimeout(() => setToast(null), 3000)
    }
  }

  async function handleGoogleAuthorize() {
    if (!googleCode.trim()) {
      setToast({ type: 'error', message: 'Введите код авторизации' })
      setTimeout(() => setToast(null), 3000)
      return
    }
    setGoogleAuthorizing(true)
    try {
      // Extract code from URL or use as-is
      let code = googleCode.trim()
      // If user pasted the full URL, extract the code
      const match = code.match(/[?&]code=([^&]+)/)
      if (match) {
        code = decodeURIComponent(match[1])
      }
      const result = await authorizeGoogle(code)
      if (result.success) {
        setToast({ type: 'success', message: `✅ Авторизация успешна: ${result.email || 'OK'}` })
        setGoogleCode('')
        setGoogleAuthUrl(null)
        loadGoogleStatus()
      }
    } catch (e) {
      setToast({ type: 'error', message: e.message })
    } finally {
      setGoogleAuthorizing(false)
      setTimeout(() => setToast(null), 3000)
    }
  }

  async function handleGoogleDisconnect() {
    if (!confirm('Отключить Google аккаунт? Бот потеряет доступ к Gmail, Calendar и Drive.')) {
      return
    }
    try {
      await disconnectGoogle()
      setToast({ type: 'success', message: 'Google отключён' })
      loadGoogleStatus()
    } catch (e) {
      setToast({ type: 'error', message: e.message })
    }
    setTimeout(() => setToast(null), 3000)
  }

  async function loadTimezone() {
    try {
      const data = await getTimezone()
      setTzData(data)
      setSelectedTz(data.saved || data.current || 'Europe/Moscow')
    } catch (e) {
      console.error('Failed to load timezone:', e)
    }
  }

  async function handleTzSave() {
    setTzSaving(true)
    try {
      await updateTimezone(selectedTz)
      setToast({ type: 'success', message: `Timezone set to ${selectedTz}. Restart containers for full effect.` })
      await loadTimezone()
    } catch (e) {
      setToast({ type: 'error', message: e.message })
    } finally {
      setTzSaving(false)
      setTimeout(() => setToast(null), 5000)
    }
  }

  async function loadLocale() {
    try {
      const data = await getLocale()
      setLocaleData(data)
      setSelectedLang(data.language || 'ru')
    } catch (e) {
      console.error('Failed to load locale:', e)
    }
  }

  async function handleLocaleSave() {
    setLocaleSaving(true)
    try {
      await updateLocale(selectedLang)
      setToast({ type: 'success', message: `Language set to ${selectedLang}` })
      await loadLocale()
    } catch (e) {
      setToast({ type: 'error', message: e.message })
    } finally {
      setLocaleSaving(false)
      setTimeout(() => setToast(null), 3000)
    }
  }

  async function handleSearchSave() {
    setSearchSaving(true)
    try {
      await updateSearchConfig(searchConfig)
      setToast({ type: 'success', message: t('toast.search_saved') })
    } catch (e) {
      setToast({ type: 'error', message: e.message })
    } finally {
      setSearchSaving(false)
      setTimeout(() => setToast(null), 3000)
    }
  }

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
      setToast({ type: 'success', message: t('toast.mode_set', { mode }) })
    } catch (e) {
      setToast({ type: 'error', message: e.message })
    }
    setTimeout(() => setToast(null), 3000)
  }

  async function handleAdminIdSave() {
    const adminId = parseInt(newAdminId)
    if (!adminId || isNaN(adminId) || adminId <= 0) {
      setToast({ type: 'error', message: t('toast.invalid_admin_id') })
      setTimeout(() => setToast(null), 3000)
      return
    }
    try {
      await setAdminId(adminId)
      setAccess(prev => ({ ...prev, admin_id: adminId }))
      setEditingAdminId(false)
      setToast({ type: 'success', message: t('toast.admin_id_set', { id: adminId }) })
    } catch (e) {
      setToast({ type: 'error', message: e.message })
    }
    setTimeout(() => setToast(null), 3000)
  }

  async function handleAddUser() {
    const userId = parseInt(newUserId)
    if (!userId || isNaN(userId)) {
      setToast({ type: 'error', message: t('toast.invalid_user_id') })
      setTimeout(() => setToast(null), 3000)
      return
    }
    try {
      const result = await updateAllowlist(userId, 'add')
      setAllowlist(result.allowlist)
      setNewUserId('')
      setToast({ type: 'success', message: t('toast.user_added', { id: userId }) })
    } catch (e) {
      setToast({ type: 'error', message: e.message })
    }
    setTimeout(() => setToast(null), 3000)
  }

  async function handleRemoveUser(userId) {
    try {
      const result = await updateAllowlist(userId, 'remove')
      setAllowlist(result.allowlist)
      setToast({ type: 'success', message: t('toast.user_removed', { id: userId }) })
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
      setToast({ type: 'success', message: t('toast.config_saved') })
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
    return <div className="loading"><div className="spinner"></div>{t('common.loading')}</div>
  }

  const tabs = ['access', 'search', 'asr', 'google', 'agent', 'bot', 'userbot', 'security', 'limits']

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">{t('config.title')}</h1>
        <p className="page-subtitle">{t('config.subtitle')}</p>
      </div>

      <div className="tabs">
        {tabs.map(tab => (
          <button
            key={tab}
            className={`tab ${activeTab === tab ? 'active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {t(`config.tab.${tab}`)}
          </button>
        ))}
      </div>

      <div className="card">
        {activeTab === 'access' && (
          <>
            <div style={{ marginBottom: '24px' }}>
              <h3 style={{ marginBottom: '8px', color: '#e74c3c' }}>{t('config.access.title')}</h3>
              <p style={{ color: '#888', fontSize: '14px' }}>
                {t('config.access.desc')}
              </p>
            </div>
            
            {/* Admin ID */}
            <div style={{ marginBottom: '24px' }}>
              <h4 style={{ marginBottom: '12px' }}>{t('config.access.admin_title')}</h4>
              <div style={{ 
                padding: '12px 16px', 
                background: '#1a1a2a', 
                borderRadius: '8px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '12px'
              }}>
                {editingAdminId ? (
                  <>
                    <input 
                      type="text"
                      className="form-input"
                      placeholder={t('config.access.add_user_placeholder')}
                      value={newAdminId}
                      onChange={e => setNewAdminId(e.target.value)}
                      style={{ flex: 1 }}
                    />
                    <button className="btn btn-primary" onClick={handleAdminIdSave}>
                      {t('config.access.save')}
                    </button>
                    <button className="btn btn-secondary" onClick={() => setEditingAdminId(false)}>
                      ✕
                    </button>
                  </>
                ) : (
                  <>
                    <div>
                      <span style={{ color: '#888', fontSize: '13px' }}>{t('config.access.admin_label')} </span>
                      <span style={{ fontFamily: 'monospace', fontSize: '15px' }}>
                        {access?.admin_id || t('config.access.not_set')}
                      </span>
                      {!access?.admin_id || access?.admin_id === 0 ? (
                        <span style={{ color: '#e74c3c', fontSize: '12px', marginLeft: '8px' }}>
                          {t('config.access.configure_warning')}
                        </span>
                      ) : null}
                    </div>
                    <button 
                      className="btn btn-secondary" 
                      onClick={() => {
                        setNewAdminId(access?.admin_id?.toString() || '')
                        setEditingAdminId(true)
                      }}
                    >
                      {t('config.access.edit')}
                    </button>
                  </>
                )}
              </div>
              <p style={{ color: '#888', fontSize: '12px', marginTop: '6px' }}>
                {t('config.access.admin_hint')}
              </p>
            </div>

            {/* Access Mode */}
            <div style={{ marginBottom: '24px' }}>
              <h4 style={{ marginBottom: '12px' }}>{t('config.access.mode_title')}</h4>
              <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                <button 
                  className={`btn ${access?.mode === 'admin_only' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => handleModeChange('admin_only')}
                >
                  {t('config.access.mode_admin')}
                </button>
                <button 
                  className={`btn ${access?.mode === 'allowlist' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => handleModeChange('allowlist')}
                >
                  {t('config.access.mode_allowlist')}
                </button>
                <button 
                  className={`btn ${access?.mode === 'public' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => handleModeChange('public')}
                >
                  {t('config.access.mode_public')}
                </button>
              </div>
              <p style={{ color: '#888', fontSize: '13px', marginTop: '8px' }}>
                {access?.mode === 'admin_only' && t('config.access.mode_admin_desc', { id: access?.admin_id || t('config.access.not_set') })}
                {access?.mode === 'allowlist' && t('config.access.mode_allowlist_desc')}
                {access?.mode === 'public' && t('config.access.mode_public_desc')}
              </p>
            </div>

            {/* Allowlist */}
            {access?.mode === 'allowlist' && (
              <div style={{ marginBottom: '24px', padding: '16px', background: '#1a1a2a', borderRadius: '8px' }}>
                <h4 style={{ marginBottom: '12px' }}>{t('config.access.allowlist_title')}</h4>
                
                <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
                  <input 
                    type="text"
                    className="form-input"
                    placeholder={t('config.access.add_user_placeholder')}
                    value={newUserId}
                    onChange={e => setNewUserId(e.target.value)}
                    style={{ flex: 1 }}
                  />
                  <button className="btn btn-primary" onClick={handleAddUser}>
                    {t('config.access.add_user_btn')}
                  </button>
                </div>

                {allowlist.length === 0 ? (
                  <p style={{ color: '#888', fontSize: '13px' }}>{t('config.access.no_users')}</p>
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
            <h4 style={{ marginBottom: '12px' }}>{t('config.access.services_title')}</h4>
            {servicesLoading ? (
              <div style={{ padding: '20px', textAlign: 'center', color: '#888' }}>{t('toast.loading_services')}</div>
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
                    <span style={{ fontSize: '16px', fontWeight: '500' }}>🤖 {t('config.access.bot_label')}</span>
                    <p style={{ color: '#888', fontSize: '13px', marginTop: '4px' }}>
                      @socialwarebot - <span style={{ color: isServiceRunning('bot') ? '#2ecc71' : '#e74c3c' }}>
                        {services.bot?.status || t('misc.unknown')}
                      </span>
                    </p>
                  </div>
                  <button 
                    className={`btn ${isServiceRunning('bot') ? 'btn-danger' : 'btn-primary'}`}
                    disabled={toggling === 'bot'}
                    onClick={() => handleToggleService('bot', isServiceRunning('bot'))}
                    style={{ minWidth: '100px' }}
                  >
                    {toggling === 'bot' ? '...' : isServiceRunning('bot') ? t('services.stop') : t('services.start')}
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
                    <span style={{ fontSize: '16px', fontWeight: '500' }}>👤 {t('config.access.userbot_label')}</span>
                    <p style={{ color: '#888', fontSize: '13px', marginTop: '4px' }}>
                      {t('config.access.personal_account')} - <span style={{ color: isServiceRunning('userbot') ? '#2ecc71' : '#e74c3c' }}>
                        {services.userbot?.status || t('misc.not_deployed')}
                      </span>
                    </p>
                  </div>
                  <button 
                    className={`btn ${isServiceRunning('userbot') ? 'btn-danger' : 'btn-primary'}`}
                    disabled={toggling === 'userbot'}
                    onClick={() => handleToggleService('userbot', isServiceRunning('userbot'))}
                    style={{ minWidth: '100px' }}
                  >
                    {toggling === 'userbot' ? '...' : isServiceRunning('userbot') ? t('services.stop') : t('services.start')}
                  </button>
                </div>

                <div style={{ marginTop: '16px' }}>
                  <button className="btn btn-secondary" onClick={() => { loadServices(); loadAccessSettings(); }}>
                    {t('common.refresh')}
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
                placeholder="e.g. gpt-4, claude-3-opus, deepseek-chat"
              />
              <p style={{ color: '#888', fontSize: '12px', marginTop: '4px' }}>
                Model name for the proxy. Changes apply immediately.
              </p>
            </div>
            <div className="form-group">
              <label className="form-label">Temperature</label>
              <div className="range-container">
                <input 
                  type="range"
                  className="range-input"
                  min="0"
                  max="100"
                  value={(config.agent?.temperature ?? 0.7) * 100}
                  onChange={e => updateValue('agent', 'temperature', parseInt(e.target.value) / 100)}
                />
                <span className="range-value">{(config.agent?.temperature ?? 0.7).toFixed(2)}</span>
              </div>
              <p style={{ color: '#888', fontSize: '12px', marginTop: '4px' }}>
                0 = deterministic, 1 = creative. Default: 0.7
              </p>
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
            {localeData && (
              <div style={{ marginBottom: '24px', padding: '16px', borderRadius: '8px', background: '#1a1a2e' }}>
                <h4 style={{ marginBottom: '12px' }}>{t('config.bot.language')}</h4>
                <p style={{ color: '#888', fontSize: '13px', marginBottom: '8px' }}>
                  {t('config.bot.language_desc')}
                </p>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <select
                    className="form-input"
                    style={{ flex: 1 }}
                    value={selectedLang}
                    onChange={e => setSelectedLang(e.target.value)}
                  >
                    {(localeData.supported || []).map(l => (
                      <option key={l.code} value={l.code}>{l.name} ({l.code})</option>
                    ))}
                  </select>
                  <button
                    className="btn btn-primary"
                    style={{ whiteSpace: 'nowrap' }}
                    onClick={handleLocaleSave}
                    disabled={localeSaving || selectedLang === localeData.language}
                  >
                    {localeSaving ? '...' : t('common.save')}
                  </button>
                </div>
              </div>
            )}

            {tzData && (
              <div style={{ marginBottom: '24px', padding: '16px', borderRadius: '8px', background: '#1a1a2e' }}>
                <h4 style={{ marginBottom: '12px' }}>{t('config.bot.timezone')}</h4>
                {tzData.now && (
                  <p style={{ color: '#888', fontSize: '13px', marginBottom: '8px' }}>
                    {t('config.bot.timezone_current')}: <strong style={{ color: '#fff' }}>{tzData.now}</strong> ({tzData.current})
                  </p>
                )}
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <select
                    className="form-input"
                    style={{ flex: 1 }}
                    value={selectedTz}
                    onChange={e => setSelectedTz(e.target.value)}
                  >
                    {(tzData.common || []).map(tz => (
                      <option key={tz} value={tz}>{tz}</option>
                    ))}
                  </select>
                  <button
                    className="btn btn-primary"
                    style={{ whiteSpace: 'nowrap' }}
                    onClick={handleTzSave}
                    disabled={tzSaving || selectedTz === tzData.current}
                  >
                    {tzSaving ? '...' : t('common.save')}
                  </button>
                </div>
                {selectedTz !== tzData.current && (
                  <p style={{ color: '#f90', fontSize: '12px', marginTop: '6px' }}>
                    {t('config.bot.timezone_restart')}
                  </p>
                )}
              </div>
            )}

            <div className="toggle">
              <span className="toggle-label">{t('config.bot.reactions')}</span>
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
              <span className="toggle-label">{t('config.bot.thoughts')}</span>
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
              <label className="form-label">{t('config.bot.reaction_chance')}</label>
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

        {activeTab === 'userbot' && (
          <>
            <div style={{ marginBottom: '16px' }}>
              <h3 style={{ marginBottom: '8px' }}>👤 Userbot Response Settings</h3>
              <p style={{ color: '#888', fontSize: '13px' }}>
                Control when the userbot responds to messages. Lower values = more selective.
              </p>
            </div>
            
            <div className="toggle">
              <span className="toggle-label">Ignore Other Bots</span>
              <label className="toggle-switch">
                <input 
                  type="checkbox"
                  checked={config.userbot?.ignore_bots ?? true}
                  onChange={e => updateValue('userbot', 'ignore_bots', e.target.checked)}
                />
                <span className="toggle-slider"></span>
              </label>
            </div>

            <div className="form-group" style={{ marginTop: '16px' }}>
              <label className="form-label">Response Chance in DMs</label>
              <div className="range-container">
                <input 
                  type="range"
                  className="range-input"
                  min="0"
                  max="100"
                  value={(config.userbot?.response_chance_dm || 0.6) * 100}
                  onChange={e => updateValue('userbot', 'response_chance_dm', parseInt(e.target.value) / 100)}
                />
                <span className="range-value">{Math.round((config.userbot?.response_chance_dm || 0.6) * 100)}%</span>
              </div>
              <p style={{ color: '#666', fontSize: '11px', marginTop: '2px' }}>Chance to respond in private messages</p>
            </div>

            <div className="form-group">
              <label className="form-label">Response Chance in Groups</label>
              <div className="range-container">
                <input 
                  type="range"
                  className="range-input"
                  min="0"
                  max="50"
                  value={(config.userbot?.response_chance_group || 0.1) * 100}
                  onChange={e => updateValue('userbot', 'response_chance_group', parseInt(e.target.value) / 100)}
                />
                <span className="range-value">{Math.round((config.userbot?.response_chance_group || 0.1) * 100)}%</span>
              </div>
              <p style={{ color: '#666', fontSize: '11px', marginTop: '2px' }}>Chance to respond to random group messages</p>
            </div>

            <div className="form-group">
              <label className="form-label">Response Chance on @Mention</label>
              <div className="range-container">
                <input 
                  type="range"
                  className="range-input"
                  min="0"
                  max="100"
                  value={(config.userbot?.response_chance_mention || 0.5) * 100}
                  onChange={e => updateValue('userbot', 'response_chance_mention', parseInt(e.target.value) / 100)}
                />
                <span className="range-value">{Math.round((config.userbot?.response_chance_mention || 0.5) * 100)}%</span>
              </div>
              <p style={{ color: '#666', fontSize: '11px', marginTop: '2px' }}>Chance to respond when @mentioned</p>
            </div>

            <div className="form-group">
              <label className="form-label">Response Chance on Reply</label>
              <div className="range-container">
                <input 
                  type="range"
                  className="range-input"
                  min="0"
                  max="100"
                  value={(config.userbot?.response_chance_reply || 0.4) * 100}
                  onChange={e => updateValue('userbot', 'response_chance_reply', parseInt(e.target.value) / 100)}
                />
                <span className="range-value">{Math.round((config.userbot?.response_chance_reply || 0.4) * 100)}%</span>
              </div>
              <p style={{ color: '#666', fontSize: '11px', marginTop: '2px' }}>Chance to respond when someone replies to userbot's message</p>
            </div>

            {/* LLM Classifier Section */}
            <div style={{ 
              marginTop: '24px', 
              padding: '16px', 
              background: config.userbot?.use_classifier ? '#1a2a1a' : '#1a1a2a',
              borderRadius: '8px',
              border: '1px solid #333'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <div>
                  <h4 style={{ margin: 0, color: '#fff' }}>🧠 LLM Classifier</h4>
                  <p style={{ color: '#888', fontSize: '12px', marginTop: '4px' }}>
                    Use AI to decide when to respond instead of random chance
                  </p>
                </div>
                <label className="toggle-switch">
                  <input 
                    type="checkbox"
                    checked={config.userbot?.use_classifier ?? false}
                    onChange={e => updateValue('userbot', 'use_classifier', e.target.checked)}
                  />
                  <span className="toggle-slider"></span>
                </label>
              </div>
              
              {config.userbot?.use_classifier && (
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">Minimum Confidence</label>
                  <div className="range-container">
                    <input 
                      type="range"
                      className="range-input"
                      min="30"
                      max="95"
                      value={(config.userbot?.classifier_min_confidence || 0.6) * 100}
                      onChange={e => updateValue('userbot', 'classifier_min_confidence', parseInt(e.target.value) / 100)}
                    />
                    <span className="range-value">{Math.round((config.userbot?.classifier_min_confidence || 0.6) * 100)}%</span>
                  </div>
                  <p style={{ color: '#666', fontSize: '11px', marginTop: '2px' }}>
                    Only respond when LLM is this confident the message is worth answering
                  </p>
                </div>
              )}
              
              {!config.userbot?.use_classifier && (
                <p style={{ color: '#666', fontSize: '12px', fontStyle: 'italic', marginBottom: 0 }}>
                  When disabled, random chance (sliders above) is used
                </p>
              )}
            </div>

            <div className="form-group" style={{ marginTop: '16px' }}>
              <label className="form-label">Cooldown Between Responses (seconds)</label>
              <div className="range-container">
                <input 
                  type="range"
                  className="range-input"
                  min="0"
                  max="300"
                  step="10"
                  value={config.userbot?.cooldown_seconds || 60}
                  onChange={e => updateValue('userbot', 'cooldown_seconds', parseInt(e.target.value))}
                />
                <span className="range-value">{config.userbot?.cooldown_seconds || 60}s</span>
              </div>
              <p style={{ color: '#666', fontSize: '11px', marginTop: '2px' }}>Minimum time between responses in the same chat</p>
            </div>
          </>
        )}

        {activeTab === 'security' && (
          <>
            <div className="toggle">
              <span className="toggle-label">{t('config.security.prompt_filter')}</span>
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
              <span className="toggle-label">{t('config.security.block_patterns')}</span>
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
              <span className="toggle-label">{t('config.security.sandbox')}</span>
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
              <label className="form-label">{t('config.security.max_blocked')}</label>
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

        {activeTab === 'search' && searchConfig && (
          <>
            <div style={{ marginBottom: '24px' }}>
              <h3 style={{ marginBottom: '8px' }}>{t('config.search.title')}</h3>
              <p style={{ color: '#888', fontSize: '14px' }}>
                {t('config.search.desc')}
              </p>
            </div>

            {/* ZAI API Key Section */}
            <div style={{ 
              marginBottom: '24px', 
              padding: '16px', 
              borderRadius: '8px', 
              background: zaiKeyStatus?.configured ? '#1a2a1a' : '#2a1a1a',
              border: '1px solid #333'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <div>
                  <h4 style={{ margin: 0, color: '#fff' }}>🔑 Z.AI API Key</h4>
                  <p style={{ color: '#888', fontSize: '12px', marginTop: '4px' }}>
                    {zaiKeyStatus?.configured 
                      ? `Настроен: ${zaiKeyStatus.masked_key} (${zaiKeyStatus.source})` 
                      : '❌ Не настроен — поиск не будет работать'}
                  </p>
                </div>
                <button 
                  className="btn btn-primary" 
                  style={{ padding: '4px 12px', fontSize: '12px' }}
                  onClick={handleZAITest}
                  disabled={zaiTesting}
                >
                  {zaiTesting ? '...' : '🔌 Тест'}
                </button>
              </div>
              
              <div style={{ display: 'flex', gap: '8px' }}>
                <input
                  type="password"
                  className="form-input"
                  placeholder="Введите новый API ключ Z.AI..."
                  value={zaiKeyInput}
                  onChange={e => setZaiKeyInput(e.target.value)}
                  style={{ flex: 1 }}
                />
                <button 
                  className="btn btn-primary" 
                  onClick={handleZAIKeySave}
                  disabled={zaiKeySaving || !zaiKeyInput}
                >
                  {zaiKeySaving ? '...' : '💾 Сохранить'}
                </button>
              </div>
              <p style={{ color: '#666', fontSize: '11px', marginTop: '6px' }}>
                После сохранения ключа перезапустите proxy: <code>docker compose up -d --build proxy</code>
              </p>
            </div>

            <div className="form-group">
              <label className="form-label">{t('config.search.mode')}</label>
              <div style={{ display: 'flex', gap: '8px' }}>
                {['coding', 'legacy'].map(mode => (
                  <button
                    key={mode}
                    className={`btn ${searchConfig.mode === mode ? 'btn-primary' : 'btn-secondary'}`}
                    onClick={() => setSearchConfig(prev => ({ ...prev, mode }))}
                    style={{ flex: 1 }}
                  >
                    {mode === 'coding' ? '⚡ Coding Plan' : '📡 Legacy API'}
                  </button>
                ))}
              </div>
              <p style={{ color: '#888', fontSize: '12px', marginTop: '6px' }}>
                {searchConfig.mode === 'coding' 
                  ? t('config.search.mode_coding_desc')
                  : t('config.search.mode_basic_desc')
                }
              </p>
            </div>

            {searchConfig.mode === 'coding' && (
              <div className="form-group">
                <label className="form-label">{t('config.search.model')}</label>
                <select
                  className="form-input"
                  value={searchConfig.model || 'glm-4.7-flash'}
                  onChange={e => setSearchConfig(prev => ({ ...prev, model: e.target.value }))}
                >
                  <option value="glm-4.7-flash">glm-4.7-flash (fast)</option>
                  <option value="glm-4.7-flashx">glm-4.7-flashx (faster)</option>
                  <option value="glm-4.7">glm-4.7 (best quality)</option>
                  <option value="glm-4.5-flash">glm-4.5-flash</option>
                </select>
              </div>
            )}

            <div className="form-group">
              <label className="form-label">{t('config.search.response_model')}</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. glm-4.7-flash (empty = use main model)"
                value={searchConfig.response_model || ''}
                onChange={e => setSearchConfig(prev => ({ ...prev, response_model: e.target.value }))}
              />
              <p style={{ color: '#888', fontSize: '12px', marginTop: '4px' }}>
                {searchConfig.response_model
                  ? `${t('config.search.response_model_desc_on')} ${searchConfig.response_model}`
                  : t('config.search.response_model_desc_off')
                }
              </p>
            </div>

            <div className="form-group">
              <label className="form-label">{t('config.search.results_count')}</label>
              <div className="range-container">
                <input
                  type="range"
                  className="range-input"
                  min="1"
                  max="20"
                  value={searchConfig.count || 10}
                  onChange={e => setSearchConfig(prev => ({ ...prev, count: parseInt(e.target.value) }))}
                />
                <span className="range-value">{searchConfig.count || 10}</span>
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">{t('config.search.recency')}</label>
              <select
                className="form-input"
                value={searchConfig.recency_filter || 'noLimit'}
                onChange={e => setSearchConfig(prev => ({ ...prev, recency_filter: e.target.value }))}
              >
                <option value="noLimit">No limit</option>
                <option value="oneDay">Last 24 hours</option>
                <option value="oneWeek">Last week</option>
                <option value="oneMonth">Last month</option>
                <option value="oneYear">Last year</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">{t('config.search.timeout')}</label>
              <div className="range-container">
                <input
                  type="range"
                  className="range-input"
                  min="30"
                  max="300"
                  step="10"
                  value={searchConfig.timeout || 120}
                  onChange={e => setSearchConfig(prev => ({ ...prev, timeout: parseInt(e.target.value) }))}
                />
                <span className="range-value">{searchConfig.timeout || 120}s</span>
              </div>
            </div>

            <div style={{ marginTop: '24px', display: 'flex', gap: '12px' }}>
              <button className="btn btn-primary" onClick={handleSearchSave} disabled={searchSaving}>
                {searchSaving ? t('common.saving') : t('config.search.save')}
              </button>
              <button className="btn btn-secondary" onClick={loadSearchConfig}>
                {t('common.reset')}
              </button>
            </div>
          </>
        )}

        {activeTab === 'asr' && asrConfig && (
          <>
            <div style={{ marginBottom: '24px' }}>
              <h3 style={{ marginBottom: '8px' }}>{t('config.asr.title')}</h3>
              <p style={{ color: '#888', fontSize: '14px' }}>
                {t('config.asr.desc')}
              </p>
            </div>

            <div style={{ marginBottom: '16px', padding: '12px', borderRadius: '8px', background: asrHealth?.status === 'ready' ? '#1a3a1a' : asrHealth?.status === 'disabled' ? '#2a2a2a' : '#3a1a1a' }}>
              <span style={{ fontWeight: 'bold' }}>
                {asrHealth?.status === 'ready' ? t('config.asr.online') : asrHealth?.status === 'disabled' ? t('config.asr.disabled_status') : t('config.asr.offline')}
              </span>
              {asrHealth?.api_type && <span style={{ color: '#888', marginLeft: '12px' }}>Type: {asrHealth.api_type}</span>}
              {asrHealth?.model_name && <span style={{ color: '#888', marginLeft: '12px' }}>Model: {asrHealth.model_name}</span>}
              {asrHealth?.device && <span style={{ color: '#888', marginLeft: '12px' }}>Device: {asrHealth.device}</span>}
              {asrHealth?.error && <span style={{ color: '#f66', marginLeft: '12px' }}>{asrHealth.error}</span>}
              {asrHealth?.http_status && <span style={{ color: '#f66', marginLeft: '12px' }}>HTTP {asrHealth.http_status}</span>}
              <button 
                className="btn btn-primary" 
                style={{ marginLeft: '12px', padding: '4px 12px', fontSize: '12px' }} 
                onClick={handleASRTest}
                disabled={asrTesting}
              >
                {asrTesting ? '...' : '🔌 Тест подключения'}
              </button>
            </div>

            <div className="toggle">
              <span className="toggle-label">{t('config.asr.enable')}</span>
              <label className="toggle-switch">
                <input
                  type="checkbox"
                  checked={asrConfig.enabled ?? true}
                  onChange={e => setAsrConfig(prev => ({ ...prev, enabled: e.target.checked }))}
                />
                <span className="toggle-slider"></span>
              </label>
            </div>

            <div className="form-group">
              <label className="form-label">{t('config.asr.url')}</label>
              <input
                type="text"
                className="form-input"
                placeholder="http://host.docker.internal:8080"
                value={asrConfig.url || ''}
                onChange={e => setAsrConfig(prev => ({ ...prev, url: e.target.value }))}
              />
              <p style={{ color: '#888', fontSize: '12px', marginTop: '4px' }}>
                {t('config.asr.url_desc')}
              </p>
            </div>

            <div className="form-group">
              <label className="form-label">API Type</label>
              <div style={{ display: 'flex', gap: '8px' }}>
                {[
                  { value: 'openai', label: '🔌 OpenAI Compatible', desc: '/v1/audio/transcriptions' },
                  { value: 'faster-whisper', label: '⚡ Faster-Whisper', desc: '/api/v1/transcribe' }
                ].map(type => (
                  <button
                    key={type.value}
                    className={`btn ${asrConfig.api_type === type.value ? 'btn-primary' : 'btn-secondary'}`}
                    onClick={() => setAsrConfig(prev => ({ ...prev, api_type: type.value }))}
                    style={{ flex: 1, textAlign: 'left', padding: '12px' }}
                  >
                    <div>{type.label}</div>
                    <div style={{ fontSize: '11px', color: asrConfig.api_type === type.value ? '#adf' : '#888', marginTop: '4px' }}>
                      {type.desc}
                    </div>
                  </button>
                ))}
              </div>
              <p style={{ color: '#888', fontSize: '12px', marginTop: '6px' }}>
                OpenAI Compatible for remote Whisper servers (with Bearer token). Faster-Whisper for local servers.
              </p>
            </div>

            {asrConfig.api_type === 'openai' && (
              <div className="form-group">
                <label className="form-label">API Key (Bearer Token)</label>
                <input
                  type="password"
                  className="form-input"
                  placeholder="secret-token"
                  value={asrConfig.api_key || ''}
                  onChange={e => setAsrConfig(prev => ({ ...prev, api_key: e.target.value }))}
                />
                <p style={{ color: '#888', fontSize: '12px', marginTop: '4px' }}>
                  Authorization: Bearer &lt;token&gt; for authenticated ASR endpoints
                </p>
              </div>
            )}

            <div className="form-group">
              <label className="form-label">{t('config.asr.language')}</label>
              <select
                className="form-input"
                value={asrConfig.language || 'ru'}
                onChange={e => setAsrConfig(prev => ({ ...prev, language: e.target.value }))}
              >
                <option value="ru">Russian (ru)</option>
                <option value="en">English (en)</option>
                <option value="uk">Ukrainian (uk)</option>
                <option value="de">German (de)</option>
                <option value="fr">French (fr)</option>
                <option value="">Auto-detect</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">{t('config.asr.max_duration')}</label>
              <div className="range-container">
                <input
                  type="range"
                  className="range-input"
                  min="10"
                  max="300"
                  step="10"
                  value={asrConfig.max_duration || 120}
                  onChange={e => setAsrConfig(prev => ({ ...prev, max_duration: parseInt(e.target.value) }))}
                />
                <span className="range-value">{asrConfig.max_duration || 120}s</span>
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">{t('config.asr.timeout')}</label>
              <div className="range-container">
                <input
                  type="range"
                  className="range-input"
                  min="10"
                  max="120"
                  step="5"
                  value={asrConfig.timeout || 60}
                  onChange={e => setAsrConfig(prev => ({ ...prev, timeout: parseInt(e.target.value) }))}
                />
                <span className="range-value">{asrConfig.timeout || 60}s</span>
              </div>
            </div>

            <div style={{ marginTop: '24px', display: 'flex', gap: '12px' }}>
              <button className="btn btn-primary" onClick={handleASRSave} disabled={asrSaving}>
                {asrSaving ? t('common.saving') : t('config.asr.save')}
              </button>
              <button className="btn btn-secondary" onClick={loadASRConfig}>
                {t('common.reset')}
              </button>
            </div>
          </>
        )}

        {activeTab === 'google' && (
          <>
            <div style={{ marginBottom: '24px' }}>
              <h3 style={{ marginBottom: '8px' }}>🔗 Google Workspace</h3>
              <p style={{ color: '#888', fontSize: '14px' }}>
                Подключите свой Google аккаунт для доступа к Gmail, Calendar и Drive
              </p>
            </div>

            {/* Step 1: OAuth Client Credentials */}
            <div style={{ 
              marginBottom: '24px', 
              padding: '20px', 
              borderRadius: '8px', 
              background: '#1a1a2e',
              border: '1px solid #333'
            }}>
              <h4 style={{ marginBottom: '16px' }}>1️⃣ OAuth Client Credentials</h4>
              <p style={{ color: '#aaa', fontSize: '13px', marginBottom: '16px' }}>
                Создайте OAuth Client в <a href="https://console.cloud.google.com/apis/credentials" target="_blank" style={{ color: '#6af' }}>Google Cloud Console</a> и введите Client ID и Secret:
              </p>
              
              <div className="form-group" style={{ marginBottom: '12px' }}>
                <label className="form-label">Client ID</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="660651688426-xxxxx.apps.googleusercontent.com"
                  value={googleClientId}
                  onChange={e => setGoogleClientId(e.target.value)}
                />
              </div>

              <div className="form-group" style={{ marginBottom: '16px' }}>
                <label className="form-label">Client Secret</label>
                <input
                  type="password"
                  className="form-input"
                  placeholder="GOCSPX-xxxxx"
                  value={googleClientSecret}
                  onChange={e => setGoogleClientSecret(e.target.value)}
                />
              </div>

              <button 
                className="btn btn-primary"
                onClick={handleGoogleSaveCredentials}
                disabled={googleSaving || !googleClientId.trim() || !googleClientSecret.trim()}
              >
                {googleSaving ? '💾 Сохранение...' : '💾 Сохранить Credentials'}
              </button>

              {googleStatus?.client_configured && (
                <div style={{ marginTop: '12px', color: '#6f6', fontSize: '13px' }}>
                  ✅ Client ID настроен: {googleStatus.client_id_saved || googleStatus.client_id}
                </div>
              )}
            </div>

            {/* Step 2: Authorization Status */}
            <div style={{ 
              marginBottom: '24px', 
              padding: '16px', 
              borderRadius: '8px', 
              background: googleStatus?.authorized ? '#1a3a1a' : googleStatus?.client_configured ? '#2a2a1a' : '#3a1a1a' 
            }}>
              <h4 style={{ marginBottom: '12px' }}>2️⃣ Статус авторизации</h4>
              {googleStatus?.authorized ? (
                <>
                  <div style={{ fontWeight: 'bold', color: '#6f6', marginBottom: '8px' }}>
                    ✅ Авторизовано
                  </div>
                  <div style={{ color: '#aaa' }}>
                    📧 {googleStatus.email || 'Email не определён'}
                  </div>
                  {googleStatus.expires_at && (
                    <div style={{ color: '#888', fontSize: '12px', marginTop: '4px' }}>
                      Токен действителен до: {new Date(googleStatus.expires_at * 1000).toLocaleString()}
                    </div>
                  )}
                  {googleStatus.scopes?.length > 0 && (
                    <div style={{ color: '#888', fontSize: '11px', marginTop: '8px' }}>
                      Разрешения: {googleStatus.scopes.map(s => s.split('/').pop()).join(', ')}
                    </div>
                  )}
                </>
              ) : googleStatus?.client_configured ? (
                <>
                  <div style={{ fontWeight: 'bold', color: '#ff6' }}>
                    ⚠️ Не авторизовано
                  </div>
                  <div style={{ color: '#888', fontSize: '12px', marginTop: '4px' }}>
                    OAuth Client настроен, но авторизация не выполнена. Перейдите к шагу 3.
                  </div>
                </>
              ) : (
                <>
                  <div style={{ fontWeight: 'bold', color: '#f66' }}>
                    ❌ Не настроено
                  </div>
                  <div style={{ color: '#888', fontSize: '12px', marginTop: '4px' }}>
                    Сначала сохраните OAuth Client Credentials в шаге 1
                  </div>
                </>
              )}
            </div>

            {/* Step 3: Authorization flow */}
            {googleStatus?.client_configured && !googleStatus?.authorized && (
              <div style={{ 
                padding: '20px', 
                background: '#1a1a2e', 
                borderRadius: '8px',
                border: '1px solid #333',
                marginBottom: '24px'
              }}>
                <h4 style={{ marginBottom: '16px' }}>3️⃣ Авторизация Google</h4>
                
                <div style={{ marginBottom: '16px' }}>
                  <p style={{ color: '#aaa', fontSize: '14px', marginBottom: '12px' }}>
                    1. Нажмите кнопку ниже, чтобы открыть страницу авторизации Google
                  </p>
                  <button 
                    className="btn btn-primary"
                    onClick={handleGoogleGetAuthUrl}
                  >
                    🔑 Открыть Google Authorization
                  </button>
                </div>

                <div style={{ marginBottom: '16px' }}>
                  <p style={{ color: '#aaa', fontSize: '14px', marginBottom: '12px' }}>
                    2. После авторизации Google перенаправит на localhost с кодом. Скопируйте URL или код из адресной строки:
                  </p>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="http://localhost/?code=4/0... или просто код"
                    value={googleCode}
                    onChange={e => setGoogleCode(e.target.value)}
                    style={{ marginBottom: '8px' }}
                  />
                  <button 
                    className="btn btn-primary"
                    onClick={handleGoogleAuthorize}
                    disabled={googleAuthorizing || !googleCode.trim()}
                  >
                    {googleAuthorizing ? '⏳ Авторизация...' : '✅ Подтвердить код'}
                  </button>
                </div>

                {googleAuthUrl && (
                  <div style={{ marginTop: '16px', padding: '12px', background: '#0a0a15', borderRadius: '6px' }}>
                    <p style={{ color: '#888', fontSize: '12px', marginBottom: '8px' }}>
                      Если окно не открылось, откройте ссылку вручную:
                    </p>
                    <input
                      type="text"
                      className="form-input"
                      value={googleAuthUrl}
                      readOnly
                      style={{ fontSize: '11px' }}
                      onClick={e => e.target.select()}
                    />
                  </div>
                )}
              </div>
            )}

            {/* Disconnect button */}
            {googleStatus?.authorized && (
              <div style={{ marginTop: '24px' }}>
                <button 
                  className="btn btn-secondary"
                  onClick={handleGoogleDisconnect}
                  style={{ background: '#3a1a1a', borderColor: '#633' }}
                >
                  🔌 Отключить Google аккаунт
                </button>
                <button 
                  className="btn btn-secondary"
                  onClick={loadGoogleStatus}
                  style={{ marginLeft: '12px' }}
                >
                  🔄 Обновить статус
                </button>
              </div>
            )}
          </>
        )}

        {activeTab === 'limits' && (
          <>
            <div className="form-group">
              <label className="form-label">{t('config.limits.sandbox_ttl')}</label>
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
              <label className="form-label">{t('config.limits.sandbox_memory')}</label>
              <input 
                type="text"
                className="form-input"
                value={config.limits?.sandbox_memory || '512m'}
                onChange={e => updateValue('limits', 'sandbox_memory', e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label">{t('config.limits.max_tool_output')}</label>
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
              <label className="form-label">{t('config.limits.max_context')}</label>
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

        {/* Show general save buttons only for tabs that don't have their own */}
        {!['asr', 'search'].includes(activeTab) && (
          <div style={{ marginTop: '24px', display: 'flex', gap: '12px' }}>
            <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
              {saving ? t('common.saving') : t('common.save')}
            </button>
            <button className="btn btn-secondary" onClick={loadConfig}>
              {t('common.reset')}
            </button>
          </div>
        )}
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
