import { useState, useEffect } from 'react'
import { getTools, toggleTool } from '../api'
import { useT } from '../i18n'

function Tools() {
  const { t } = useT()
  const [tools, setTools] = useState([])
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState(null)

  useEffect(() => {
    loadTools()
  }, [])

  async function loadTools() {
    try {
      const data = await getTools()
      setTools(data.tools || [])
    } catch (e) {
      console.error('Failed to load tools:', e)
    } finally {
      setLoading(false)
    }
  }

  async function handleToggle(name, enabled) {
    try {
      await toggleTool(name, enabled)
      setTools(tools.map(t => 
        t.name === name ? { ...t, enabled } : t
      ))
      setToast({ type: 'success', message: t('toast.tool_toggled', { state: enabled ? t('toast.enabled') : t('toast.disabled') }) })
    } catch (e) {
      setToast({ type: 'error', message: e.message })
    }
    setTimeout(() => setToast(null), 3000)
  }

  if (loading) {
    return <div className="loading"><div className="spinner"></div>{t('common.loading')}</div>
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">{t('tools.title')}</h1>
        <p className="page-subtitle">{t('tools.subtitle')}</p>
      </div>

      <div className="grid grid-2">
        {tools.map(tool => (
          <div className="card" key={tool.name}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <h3 style={{ fontSize: '16px', marginBottom: '8px' }}>
                  {tool.icon || '🔧'} {tool.name}
                </h3>
                <p style={{ color: 'var(--text-dim)', fontSize: '13px', marginBottom: '12px' }}>
                  {tool.description || t('tools.no_description')}
                </p>
                {tool.usage_count !== undefined && (
                  <span style={{ 
                    fontSize: '12px', 
                    color: 'var(--text-dim)',
                    background: 'var(--bg-input)',
                    padding: '4px 8px',
                    borderRadius: '4px'
                  }}>
                    {t('tools.used_times', { count: tool.usage_count })}
                  </span>
                )}
              </div>
              <label className="toggle-switch">
                <input 
                  type="checkbox"
                  checked={tool.enabled ?? true}
                  onChange={e => handleToggle(tool.name, e.target.checked)}
                />
                <span className="toggle-slider"></span>
              </label>
            </div>
          </div>
        ))}
      </div>

      {tools.length === 0 && (
        <div className="card">
          <p style={{ color: 'var(--text-dim)', textAlign: 'center', padding: '20px' }}>
            {t('tools.no_tools')}
          </p>
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

export default Tools
