import { useState, useEffect } from 'react'
import { getSkills, toggleSkill, scanSkills, installSkill, uninstallSkill, getAvailableSkills } from '../api'

function Skills() {
  const [skills, setSkills] = useState([])
  const [availableSkills, setAvailableSkills] = useState([])
  const [loading, setLoading] = useState(true)
  const [scanning, setScanning] = useState(false)
  const [installing, setInstalling] = useState(null)
  const [toast, setToast] = useState(null)
  const [showInstallModal, setShowInstallModal] = useState(false)
  const [activeTab, setActiveTab] = useState('installed')

  useEffect(() => {
    loadSkills()
  }, [])

  async function loadSkills() {
    try {
      const [skillsData, availableData] = await Promise.all([
        getSkills(),
        getAvailableSkills().catch(() => ({ skills: [] }))
      ])
      setSkills(skillsData.skills || [])
      setAvailableSkills(availableData.skills || [])
    } catch (e) {
      console.error('Failed to load skills:', e)
      showToast('error', 'Failed to load skills')
    } finally {
      setLoading(false)
    }
  }

  function showToast(type, message) {
    setToast({ type, message })
    setTimeout(() => setToast(null), 3000)
  }

  async function handleToggle(name, enabled) {
    try {
      await toggleSkill(name, enabled)
      setSkills(skills.map(s => 
        s.name === name ? { ...s, enabled } : s
      ))
      showToast('success', `Skill "${name}" ${enabled ? 'enabled' : 'disabled'}`)
    } catch (e) {
      showToast('error', e.message)
    }
  }

  async function handleScan() {
    setScanning(true)
    try {
      const data = await scanSkills()
      showToast('success', `Found ${data.skill_count || 0} skills`)
      loadSkills()
    } catch (e) {
      showToast('error', e.message)
    } finally {
      setScanning(false)
    }
  }

  async function handleInstall(name) {
    setInstalling(name)
    try {
      await installSkill(name)
      showToast('success', `Skill "${name}" installed`)
      loadSkills()
    } catch (e) {
      showToast('error', e.message)
    } finally {
      setInstalling(null)
    }
  }

  async function handleUninstall(name) {
    if (!confirm(`Uninstall skill "${name}"?`)) return
    try {
      await uninstallSkill(name)
      showToast('success', `Skill "${name}" uninstalled`)
      loadSkills()
    } catch (e) {
      showToast('error', e.message)
    }
  }

  if (loading) {
    return <div className="loading"><div className="spinner"></div>Loading...</div>
  }

  const installedNames = new Set(skills.map(s => s.name))
  const notInstalled = availableSkills.filter(s => !installedNames.has(s.name))

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">🎯 Skills</h1>
          <p className="page-subtitle">Extensible agent capabilities (Anthropic-style)</p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button 
            className="btn btn-secondary"
            onClick={handleScan}
            disabled={scanning}
          >
            {scanning ? '⏳ Scanning...' : '🔍 Scan Skills'}
          </button>
          <button className="btn btn-primary" onClick={() => setShowInstallModal(true)}>
            📦 Install Skill
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs" style={{ marginBottom: '20px' }}>
        <button 
          className={`tab ${activeTab === 'installed' ? 'active' : ''}`}
          onClick={() => setActiveTab('installed')}
        >
          Installed ({skills.length})
        </button>
        <button 
          className={`tab ${activeTab === 'available' ? 'active' : ''}`}
          onClick={() => setActiveTab('available')}
        >
          Available ({notInstalled.length})
        </button>
      </div>

      {activeTab === 'installed' && (
        <>
          {skills.length === 0 ? (
            <div className="card">
              <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-dim)' }}>
                <p style={{ fontSize: '48px', marginBottom: '16px' }}>🎯</p>
                <p>No skills installed</p>
                <p style={{ fontSize: '13px', marginTop: '8px' }}>
                  Install skills from the Available tab or create custom ones
                </p>
              </div>
            </div>
          ) : (
            <div className="grid grid-2">
              {skills.map(skill => (
                <div className="card" key={skill.name}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div style={{ flex: 1 }}>
                      <h3 style={{ fontSize: '16px', marginBottom: '8px' }}>
                        {skill.name}
                      </h3>
                      <p style={{ color: 'var(--text-dim)', fontSize: '13px', marginBottom: '12px' }}>
                        {skill.description || 'No description'}
                      </p>
                      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                        {skill.version && (
                          <span className="badge">v{skill.version}</span>
                        )}
                        {skill.author && (
                          <span className="badge">by {skill.author}</span>
                        )}
                        {skill.tool_count > 0 && (
                          <span className="badge badge-info">{skill.tool_count} tools</span>
                        )}
                        {skill.source && (
                          <span className="badge" style={{ 
                            background: skill.source === 'shared' ? 'var(--primary)' : 'var(--warning)',
                            color: 'white'
                          }}>
                            {skill.source}
                          </span>
                        )}
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                      {skill.source === 'shared' && (
                        <button 
                          className="btn btn-small btn-danger"
                          onClick={() => handleUninstall(skill.name)}
                          title="Uninstall"
                        >
                          🗑️
                        </button>
                      )}
                      <label className="toggle-switch">
                        <input 
                          type="checkbox"
                          checked={skill.enabled ?? true}
                          onChange={e => handleToggle(skill.name, e.target.checked)}
                        />
                        <span className="toggle-slider"></span>
                      </label>
                    </div>
                  </div>
                  
                  {skill.commands && Object.keys(skill.commands).length > 0 && (
                    <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid var(--border)' }}>
                      <p style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '8px' }}>Commands:</p>
                      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                        {Object.keys(skill.commands).map(cmd => (
                          <code key={cmd} style={{ 
                            fontSize: '12px', 
                            background: 'var(--bg-input)', 
                            padding: '4px 8px', 
                            borderRadius: '4px' 
                          }}>
                            {cmd}
                          </code>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {activeTab === 'available' && (
        <>
          {notInstalled.length === 0 ? (
            <div className="card">
              <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-dim)' }}>
                <p style={{ fontSize: '48px', marginBottom: '16px' }}>✅</p>
                <p>All available skills are installed</p>
              </div>
            </div>
          ) : (
            <div className="grid grid-2">
              {notInstalled.map(skill => (
                <div className="card" key={skill.name}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div style={{ flex: 1 }}>
                      <h3 style={{ fontSize: '16px', marginBottom: '8px' }}>
                        {skill.name}
                      </h3>
                      <p style={{ color: 'var(--text-dim)', fontSize: '13px', marginBottom: '12px' }}>
                        {skill.description || 'No description'}
                      </p>
                      {skill.source && (
                        <span className="badge">{skill.source}</span>
                      )}
                    </div>
                    <button 
                      className="btn btn-primary btn-small"
                      onClick={() => handleInstall(skill.name)}
                      disabled={installing === skill.name}
                    >
                      {installing === skill.name ? '⏳' : '📥 Install'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Install Modal */}
      {showInstallModal && (
        <div className="modal-overlay" onClick={() => setShowInstallModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h2 style={{ marginBottom: '20px' }}>Install Skill</h2>
            
            <div style={{ marginBottom: '20px' }}>
              <h3 style={{ fontSize: '14px', marginBottom: '12px', color: 'var(--text-dim)' }}>
                Anthropic Skills (Official)
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {['pptx', 'docx', 'pdf-reader', 'google-drive', 'linear', 'github'].map(name => (
                  <div key={name} style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center',
                    padding: '12px',
                    background: 'var(--bg-input)',
                    borderRadius: '8px'
                  }}>
                    <span>{name}</span>
                    <button 
                      className="btn btn-small btn-primary"
                      onClick={() => {
                        handleInstall(name)
                        setShowInstallModal(false)
                      }}
                      disabled={installedNames.has(name) || installing === name}
                    >
                      {installedNames.has(name) ? '✅ Installed' : installing === name ? '⏳' : 'Install'}
                    </button>
                  </div>
                ))}
              </div>
            </div>
            
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button className="btn btn-secondary" onClick={() => setShowInstallModal(false)}>
                Close
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

export default Skills
