import { useState, useEffect } from 'react'
import { api } from '../api'
import { useT } from '../i18n'

export default function Prompt() {
  const { t } = useT()
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
      setMessage({ type: 'error', text: t('toast.failed_load', { msg: err.message }) })
    }
    setLoading(false)
  }

  const savePrompt = async () => {
    setSaving(true)
    try {
      await api.updatePrompt(content)
      setOriginalContent(content)
      setMessage({ type: 'success', text: t('toast.prompt_saved') })
      loadPrompt()
    } catch (err) {
      setMessage({ type: 'error', text: t('toast.failed_save', { msg: err.message }) })
    }
    setSaving(false)
  }

  const restoreBackup = async () => {
    if (!confirm(t('confirm.restore_backup'))) return
    try {
      await api.restorePrompt()
      setMessage({ type: 'success', text: t('toast.prompt_restored') })
      loadPrompt()
    } catch (err) {
      setMessage({ type: 'error', text: t('toast.failed_restore', { msg: err.message }) })
    }
  }

  const hasChanges = content !== originalContent

  if (loading) {
    return <div className="page"><div className="loading">{t('prompt.loading')}</div></div>
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>{t('prompt.title')}</h2>
        <div className="header-actions">
          {info && (
            <span className="prompt-stats">
              {info.lines} {t('misc.lines')} • {info.length} {t('misc.chars')}
            </span>
          )}
          <button 
            className="btn btn-secondary"
            onClick={restoreBackup}
          >
            {t('prompt.restore')}
          </button>
          <button 
            className="btn btn-primary"
            onClick={savePrompt}
            disabled={saving || !hasChanges}
          >
            {saving ? t('prompt.saving') : t('prompt.save_btn')}
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
          {t('prompt.unsaved')}
        </div>
      )}

      <div className="prompt-editor">
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder={t('prompt.placeholder')}
          spellCheck={false}
        />
      </div>

      <div className="prompt-help">
        <h4>{t('prompt.help_title')}</h4>
        <ul>
          <li><code>{"{{tools}}"}</code> - {t('prompt.help_tools')}</li>
          <li><code>{"{{skills}}"}</code> - {t('prompt.help_skills')}</li>
          <li><code>{"{{cwd}}"}</code> - {t('prompt.help_cwd')}</li>
          <li><code>{"{{date}}"}</code> - {t('prompt.help_date')}</li>
          <li><code>{"{{userPorts}}"}</code> - {t('prompt.help_ports')}</li>
        </ul>
        <p>{t('prompt.help_tip')}</p>
      </div>
    </div>
  )
}
