import { useState, useEffect } from 'react'
import { getSecurityPatterns, addSecurityPattern, deleteSecurityPattern } from '../api'
import { useT } from '../i18n'

function Security() {
  const { t } = useT()
  const [patterns, setPatterns] = useState([])
  const [newPattern, setNewPattern] = useState('')
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState(null)
  const [filter, setFilter] = useState('')

  useEffect(() => {
    loadPatterns()
  }, [])

  async function loadPatterns() {
    try {
      const data = await getSecurityPatterns()
      // data.patterns can be an object with .patterns array inside, or an array
      let patternList = []
      if (data.patterns) {
        if (Array.isArray(data.patterns)) {
          patternList = data.patterns
        } else if (data.patterns.patterns && Array.isArray(data.patterns.patterns)) {
          // Nested structure: {patterns: {patterns: [...]}}
          patternList = data.patterns.patterns.map(p => p.pattern || p)
        }
      }
      setPatterns(patternList)
    } catch (e) {
      console.error('Failed to load patterns:', e)
    } finally {
      setLoading(false)
    }
  }

  async function handleAdd() {
    if (!newPattern.trim()) return
    
    try {
      await addSecurityPattern(newPattern)
      setPatterns([...patterns, newPattern])
      setNewPattern('')
      setToast({ type: 'success', message: t('toast.pattern_added') })
    } catch (e) {
      setToast({ type: 'error', message: e.message })
    }
    setTimeout(() => setToast(null), 3000)
  }

  async function handleDelete(pattern) {
    if (!confirm(t('confirm.delete_pattern', { pattern }))) return
    
    try {
      await deleteSecurityPattern(pattern)
      setPatterns(patterns.filter(p => p !== pattern))
      setToast({ type: 'success', message: t('toast.pattern_deleted') })
    } catch (e) {
      setToast({ type: 'error', message: e.message })
    }
    setTimeout(() => setToast(null), 3000)
  }

  const filtered = patterns.filter(p => 
    p.toLowerCase().includes(filter.toLowerCase())
  )

  if (loading) {
    return <div className="loading"><div className="spinner"></div>{t('common.loading')}</div>
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">{t('security.title')}</h1>
        <p className="page-subtitle">{t('security.subtitle')} ({patterns.length})</p>
      </div>

      {/* Add new pattern */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">{t('security.add_pattern')}</h2>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <input
            type="text"
            className="form-input"
            placeholder="Enter regex pattern (e.g., rm\\s+-rf)"
            value={newPattern}
            onChange={e => setNewPattern(e.target.value)}
            onKeyPress={e => e.key === 'Enter' && handleAdd()}
          />
          <button className="btn btn-primary" onClick={handleAdd}>
            {t('security.add_btn')}
          </button>
        </div>
      </div>

      {/* Pattern list */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">{t('security.blocked_patterns')}</h2>
          <input
            type="text"
            className="form-input"
            placeholder={t('security.filter')}
            style={{ width: '200px' }}
            value={filter}
            onChange={e => setFilter(e.target.value)}
          />
        </div>
        
        <div style={{ maxHeight: '500px', overflowY: 'auto' }}>
          {filtered.length === 0 ? (
            <p style={{ color: 'var(--text-dim)', padding: '20px', textAlign: 'center' }}>
              {t('security.no_patterns')}
            </p>
          ) : (
            filtered.map((pattern, i) => (
              <div 
                key={i}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '10px 0',
                  borderBottom: '1px solid var(--border)'
                }}
              >
                <code style={{ 
                  fontSize: '13px', 
                  color: 'var(--warning)',
                  background: 'var(--bg-input)',
                  padding: '4px 8px',
                  borderRadius: '4px',
                  maxWidth: '80%',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis'
                }}>
                  {pattern}
                </code>
                <button 
                  className="btn btn-danger btn-sm"
                  onClick={() => handleDelete(pattern)}
                >
                  🗑️
                </button>
              </div>
            ))
          )}
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

export default Security
