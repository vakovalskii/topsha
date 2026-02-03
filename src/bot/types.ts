/**
 * Bot types and interfaces
 */

export interface BotConfig {
  telegramToken: string;
  baseUrl: string;
  apiKey: string;
  model: string;
  cwd: string;  // Base workspace dir
  maxConcurrentUsers?: number;  // Max users processing at once
  proxyUrl?: string;  // Proxy URL for API requests (secrets isolation)
  zaiApiKey?: string;
  tavilyApiKey?: string;
  exposedPorts?: number[];
}

// Pending user questions (ask_user tool)
export interface PendingQuestion {
  id: string;
  resolve: (answer: string) => void;
}

// Track tools for batched status updates
export interface ToolTracker {
  tools: string[];
  lastUpdate: number;
  messageId?: number;
}
