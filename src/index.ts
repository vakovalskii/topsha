/**
 * Entry point - starts bot or gateway based on mode
 */

import { config as loadEnv } from 'dotenv';
import { createBot } from './bot/index.js';
import { createGateway } from './gateway/server.js';

// Load .env
loadEnv();

// Validate required env vars
const required = ['BASE_URL', 'API_KEY', 'MODEL_NAME', 'TELEGRAM_TOKEN'];
for (const key of required) {
  if (!process.env[key]) {
    console.error(`Missing: ${key}`);
    process.exit(1);
  }
}

// Parse allowed users from env (comma-separated)
const allowedUsers = process.env.ALLOWED_USERS
  ? process.env.ALLOWED_USERS.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n))
  : [];

// Parse allowed groups from env (comma-separated, negative IDs)
const allowedGroups = process.env.ALLOWED_GROUPS
  ? process.env.ALLOWED_GROUPS.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n))
  : [];

// Parse exposed ports from env (comma-separated)
const exposedPorts = process.env.EXPOSED_PORTS
  ? process.env.EXPOSED_PORTS.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n))
  : [];

const config = {
  baseUrl: process.env.BASE_URL!,
  apiKey: process.env.API_KEY!,
  model: process.env.MODEL_NAME!,
  telegramToken: process.env.TELEGRAM_TOKEN!,
  zaiApiKey: process.env.ZAI_API_KEY,
  tavilyApiKey: process.env.TAVILY_API_KEY,
  cwd: process.env.AGENT_CWD || process.cwd(),
  gatewayPort: parseInt(process.env.GATEWAY_PORT || '3100'),
  allowedUsers,
  allowedGroups,
  exposedPorts,
};

const mode = process.argv[2] || 'bot';

if (mode === 'gateway') {
  const gateway = createGateway({
    port: config.gatewayPort,
    cwd: config.cwd,
    zaiApiKey: config.zaiApiKey,
    tavilyApiKey: config.tavilyApiKey,
  });
  gateway.start();
} else {
  console.log('Starting Agent...');
  console.log(`CWD: ${config.cwd}`);
  console.log(`Model: ${config.model}`);
  console.log(`Search: ${config.zaiApiKey ? 'Z.AI' : config.tavilyApiKey ? 'Tavily' : 'none'}`);
  console.log(`Allowed users: ${allowedUsers.length ? allowedUsers.join(', ') : 'all'}`);
  console.log(`Allowed groups: ${allowedGroups.length ? allowedGroups.join(', ') : 'none'}`);
  console.log(`Ports: ${exposedPorts.length ? exposedPorts.join(', ') : 'none'}`);
  
  const bot = createBot(config);
  
  // Register commands in Telegram menu
  bot.telegram.setMyCommands([
    { command: 'start', description: 'Start / Help' },
    { command: 'clear', description: 'Clear session history' },
    { command: 'status', description: 'Show status' },
    { command: 'pending', description: 'Pending commands to approve' },
  ]);
  
  bot.launch();
  
  process.once('SIGINT', () => bot.stop('SIGINT'));
  process.once('SIGTERM', () => bot.stop('SIGTERM'));
}
