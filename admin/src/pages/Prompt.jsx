import { useState, useEffect } from 'react'
import { api } from '../api'

export default function Prompt() {
  const [content, setContent] = useState('')
  const [originalContent, setOriginalContent] = useState('')
  const [info, setInfo] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState(null)

  useEffect(() => {
    loadPrompt()
  }, [])

  const loadPrompt = async () => {
    setLoading(true)
    try {
      const data = await api.getPrompt()
      setContent(data.content || '')
      setOriginalContent(data.content || '')
      setInfo(data)
    } catch (err) {
      setMessage({ type: 'error', text: 'Failed to load prompt: ' + err.message })
    }
    setLoading(false)
  }

  const savePrompt = async () => {
    setSaving(true)
    try {
      await api.updatePrompt(content)
      setOriginalContent(content)
      setMessage({ type: 'success', text: 'Prompt saved! Restart core to apply changes.' })
      loadPrompt()
    } catch (err) {
      setMessage({ type: 'error', text: 'Failed to save: ' + err.message })
    }
    setSaving(false)
  }

  const restoreBackup = async () => {
    if (!confirm('Restore from backup?')) return
    try {
      await api.restorePrompt()
      setMessage({ type: 'success', text: 'Restored from backup!' })
      loadPrompt()
    } catch (err) {
      setMessage({ type: 'error', text: 'Failed to restore: ' + err.message })
    }
  }

  const hasChanges = content !== originalContent

  if (loading) {
    return <div className="page"><div className="loading">Loading prompt...</div></div>
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>📝 System Prompt</h2>
        <div className="header-actions">
          {info && (
            <span className="prompt-stats">
              {info.lines} lines • {info.length} chars
            </span>
          )}
          <button 
            className="btn btn-secondary"
            onClick={restoreBackup}
          >
            ↩️ Restore Backup
          </button>
          <button 
            className="btn btn-primary"
            onClick={savePrompt}
            disabled={saving || !hasChanges}
          >
            {saving ? '💾 Saving...' : '💾 Save'}
          </button>
        </div>
      </div>

      {message && (
        <div className={`alert alert-${message.type}`}>
          {message.text}
          <button onClick={() => setMessage(null)}>×</button>
        </div>
      )}

      {hasChanges && (
        <div className="alert alert-warning">
          ⚠️ You have unsaved changes
        </div>
      )}

      <div className="prompt-editor">
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="System prompt content..."
          spellCheck={false}
        />
      </div>

      <div className="prompt-help">
        <h4>Available placeholders:</h4>
        <ul>
          <li><code>{"{{tools}}"}</code> - List of available tools (name + description)</li>
          <li><code>{"{{skills}}"}</code> - Installed skills with descriptions</li>
          <li><code>{"{{cwd}}"}</code> - User's working directory</li>
          <li><code>{"{{date}}"}</code> - Current date/time</li>
          <li><code>{"{{userPorts}}"}</code> - Assigned ports for user's servers</li>
        </ul>
        <p>💡 Changes apply immediately - no restart needed!</p>
      </div>
    </div>
  )
}
