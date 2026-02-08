// API client for admin panel
const API_BASE = '/api/admin'

export async function fetchApi(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`
  const res = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers
    },
    ...options
  })
  
  if (!res.ok) {
    const error = await res.json().catch(() => ({ error: res.statusText }))
    throw new Error(error.error || error.detail || 'Request failed')
  }
  
  return res.json()
}

// Dashboard
export const getStats = () => fetchApi('/stats')
export const getHealth = () => fetchApi('/health')

// Services
export const getServices = () => fetchApi('/services')
export const getServiceStats = (name) => fetchApi(`/services/${name}/stats`)
export const restartService = (name) => fetchApi(`/services/${name}/restart`, { method: 'POST' })
export const stopService = (name) => fetchApi(`/services/${name}/stop`, { method: 'POST' })
export const startService = (name) => fetchApi(`/services/${name}/start`, { method: 'POST' })

// Config
export const getConfig = () => fetchApi('/config')
export const updateConfig = (data) => fetchApi('/config', { 
  method: 'PUT', 
  body: JSON.stringify(data) 
})

// Security
export const getSecurityPatterns = () => fetchApi('/security/patterns')
export const addSecurityPattern = (pattern) => fetchApi('/security/patterns', {
  method: 'POST',
  body: JSON.stringify({ pattern })
})
export const deleteSecurityPattern = (pattern) => fetchApi('/security/patterns', {
  method: 'DELETE',
  body: JSON.stringify({ pattern })
})

// Tools
export const getTools = () => fetchApi('/tools')
export const toggleTool = (name, enabled) => fetchApi(`/tools/${name}`, {
  method: 'PUT',
  body: JSON.stringify({ enabled })
})

// Users
export const getUsers = () => fetchApi('/users')
export const getSandboxes = () => fetchApi('/sandboxes')
export const killSandbox = (userId) => fetchApi(`/sandboxes/${userId}`, { method: 'DELETE' })

// Logs
export const getLogs = (service, lines = 100) => fetchApi(`/logs/${service}?lines=${lines}`)

// Access Control
export const getAccess = () => fetchApi('/access')
export const toggleBot = (enabled) => fetchApi('/access/bot', {
  method: 'PUT',
  body: JSON.stringify({ enabled })
})
export const toggleUserbot = (enabled) => fetchApi('/access/userbot', {
  method: 'PUT',
  body: JSON.stringify({ enabled })
})
export const setAccessMode = (mode) => fetchApi('/access/mode', {
  method: 'PUT',
  body: JSON.stringify({ mode })
})
export const setAdminId = (admin_id) => fetchApi('/access/admin', {
  method: 'PUT',
  body: JSON.stringify({ admin_id })
})
export const getAllowlist = () => fetchApi('/access/allowlist')
export const updateAllowlist = (user_id, action) => fetchApi('/access/allowlist', {
  method: 'POST',
  body: JSON.stringify({ user_id, action })
})

// Sessions
export const getSessions = () => fetchApi('/sessions')
export const getSessionDetail = (userId) => fetchApi(`/sessions/${userId}`)
export const clearSession = (userId) => fetchApi(`/sessions/${userId}`, { method: 'DELETE' })

// MCP Servers
export const getMcpServers = () => fetchApi('/mcp/servers')
export const addMcpServer = (server) => fetchApi('/mcp/servers', {
  method: 'POST',
  body: JSON.stringify(server)
})
export const removeMcpServer = (name) => fetchApi(`/mcp/servers/${name}`, { method: 'DELETE' })
export const toggleMcpServer = (name, enabled) => fetchApi(`/mcp/servers/${name}/toggle`, {
  method: 'PUT',
  body: JSON.stringify({ enabled })
})
export const refreshMcpServer = (name) => fetchApi(`/mcp/servers/${name}/refresh`, { method: 'POST' })
export const refreshAllMcp = () => fetchApi('/mcp/refresh-all', { method: 'POST' })

// Skills
export const getSkills = () => fetchApi('/skills')
export const getAvailableSkills = () => fetchApi('/skills/available')
export const toggleSkill = (name, enabled) => fetchApi(`/skills/${name}`, {
  method: 'PUT',
  body: JSON.stringify({ enabled })
})
export const scanSkills = () => fetchApi('/skills/scan', { method: 'POST' })
export const installSkill = (name) => fetchApi('/skills/install', {
  method: 'POST',
  body: JSON.stringify({ name, source: 'anthropic' })
})
export const uninstallSkill = (name) => fetchApi(`/skills/${name}`, { method: 'DELETE' })

// Search Config
export const getSearchConfig = () => fetchApi('/search')
export const updateSearchConfig = (data) => fetchApi('/search', {
  method: 'PUT',
  body: JSON.stringify(data)
})

// Locale
export const getLocale = () => fetchApi('/locale')
export const updateLocale = (language) => fetchApi('/locale', {
  method: 'PUT',
  body: JSON.stringify({ language })
})

// Timezone
export const getTimezone = () => fetchApi('/timezone')
export const updateTimezone = (timezone) => fetchApi('/timezone', {
  method: 'PUT',
  body: JSON.stringify({ timezone })
})

// ASR Config
export const getASRConfig = () => fetchApi('/asr')
export const updateASRConfig = (data) => fetchApi('/asr', {
  method: 'PUT',
  body: JSON.stringify(data)
})
export const getASRHealth = () => fetchApi('/asr/health')

// System Prompt
export const getPrompt = () => fetchApi('/prompt')
export const updatePrompt = (content) => fetchApi('/prompt', {
  method: 'PUT',
  body: JSON.stringify({ content })
})
export const restorePrompt = () => fetchApi('/prompt/restore', { method: 'POST' })

// Export all as object for convenient imports
export const api = {
  // Dashboard
  getStats, getHealth,
  // Services
  getServices, getServiceStats, restartService, stopService, startService,
  // Config
  getConfig, updateConfig,
  // Security
  getSecurityPatterns, addSecurityPattern, deleteSecurityPattern,
  // Tools
  getTools, toggleTool,
  // Users
  getUsers, getSandboxes, killSandbox,
  // Logs
  getLogs,
  // Access
  getAccess, toggleBot, toggleUserbot, setAccessMode, setAdminId, getAllowlist, updateAllowlist,
  // Sessions
  getSessions, getSessionDetail, clearSession,
  // MCP
  getMcpServers, addMcpServer, removeMcpServer, toggleMcpServer, refreshMcpServer, refreshAllMcp,
  // Skills
  getSkills, getAvailableSkills, toggleSkill, scanSkills, installSkill, uninstallSkill,
  // Search
  getSearchConfig, updateSearchConfig,
  // Locale
  getLocale, updateLocale,
  // Timezone
  getTimezone, updateTimezone,
  // ASR
  getASRConfig, updateASRConfig, getASRHealth,
  // Prompt
  getPrompt, updatePrompt, restorePrompt
}
