import React, { useState, useEffect } from 'react';
import { useT } from '../i18n';

const API_BASE = '/api/admin';

function Tasks() {
  const { t } = useT();
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    loadTasks();
    // Auto-refresh every 30 seconds
    const interval = setInterval(loadTasks, 30000);
    return () => clearInterval(interval);
  }, []);

  async function loadTasks() {
    try {
      const res = await fetch(`${API_BASE}/tasks`);
      const data = await res.json();
      setTasks(data.tasks || []);
    } catch (e) {
      console.error('Failed to load tasks:', e);
    } finally {
      setLoading(false);
    }
  }

  async function cancelTask(taskId) {
    if (!window.confirm(t('confirm.cancel_task', { id: taskId }))) return;
    
    try {
      const res = await fetch(`${API_BASE}/tasks/${taskId}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        setToast({ type: 'success', message: t('toast.task_cancelled') });
        loadTasks();
      } else {
        throw new Error(t('toast.failed_cancel'));
      }
    } catch (e) {
      setToast({ type: 'error', message: e.message });
    }
    setTimeout(() => setToast(null), 3000);
  }

  function formatTimeLeft(minutes) {
    if (minutes < 0) return 'overdue';
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours}h ${mins}m`;
  }

  if (loading) {
    return <div className="loading"><div className="spinner"></div>{t('common.loading')}</div>;
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">{t('tasks.title')}</h1>
        <p className="page-subtitle">{t('tasks.subtitle')}</p>
      </div>

      <div className="card">
        <div className="card-header">
          <h2 className="card-title">{t('tasks.active_tasks')} ({tasks.length})</h2>
          <button onClick={loadTasks} className="btn btn-secondary btn-sm">{t('tasks.refresh')}</button>
        </div>

        {tasks.length === 0 ? (
          <p style={{ color: 'var(--text-dim)', textAlign: 'center', padding: '40px' }}>
            {t('tasks.no_tasks')}
          </p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>{t('tasks.col_id')}</th>
                <th>{t('tasks.col_user')}</th>
                <th>{t('tasks.col_type')}</th>
                <th>{t('tasks.col_content')}</th>
                <th>{t('tasks.col_next_run')}</th>
                <th>{t('tasks.col_time_left')}</th>
                <th>{t('tasks.col_recurring')}</th>
                <th>{t('tasks.col_source')}</th>
                <th>{t('tasks.col_actions')}</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((task) => (
                <tr key={task.id}>
                  <td>
                    <code style={{ fontSize: '11px' }}>{task.id.substring(0, 15)}...</code>
                  </td>
                  <td>{task.user_id}</td>
                  <td>
                    <span className={`badge ${task.type === 'agent' ? 'badge-primary' : 'badge-secondary'}`}>
                      {task.type}
                    </span>
                  </td>
                  <td style={{ maxWidth: '300px' }}>
                    <div style={{ 
                      overflow: 'hidden', 
                      textOverflow: 'ellipsis', 
                      whiteSpace: 'nowrap',
                      fontSize: '13px'
                    }}>
                      {task.content}
                    </div>
                  </td>
                  <td style={{ fontSize: '12px', whiteSpace: 'nowrap' }}>
                    {task.next_run}
                  </td>
                  <td>
                    <span style={{ 
                      color: task.time_left_minutes < 5 ? 'var(--accent)' : 'inherit',
                      fontWeight: task.time_left_minutes < 5 ? 'bold' : 'normal'
                    }}>
                      {formatTimeLeft(task.time_left_minutes)}
                    </span>
                  </td>
                  <td>
                    {task.recurring ? (
                      <span style={{ color: 'var(--success)' }}>
                        {t('tasks.recurring_every', { min: task.interval_minutes })}
                      </span>
                    ) : (
                      <span style={{ color: 'var(--text-dim)' }}>{t('tasks.once')}</span>
                    )}
                  </td>
                  <td>
                    <span className={`badge ${task.source === 'userbot' ? 'badge-warning' : 'badge-info'}`}>
                      {task.source === 'userbot' ? '👤' : '🤖'} {task.source}
                    </span>
                  </td>
                  <td>
                    <button 
                      onClick={() => cancelTask(task.id)} 
                      className="btn btn-danger btn-sm"
                    >
                      {t('tasks.cancel')}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card" style={{ marginTop: '20px' }}>
        <div className="card-header">
          <h2 className="card-title">{t('tasks.task_types')}</h2>
        </div>
        <div style={{ padding: '15px' }}>
          <table className="table" style={{ marginBottom: 0 }}>
            <tbody>
              <tr>
                <td><code>message</code></td>
                <td>{t('tasks.type_message')}</td>
              </tr>
              <tr>
                <td><code>agent</code></td>
                <td>{t('tasks.type_agent')}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {toast && (
        <div className={`toast ${toast.type}`}>
          {toast.message}
        </div>
      )}
    </div>
  );
}

export default Tasks;
