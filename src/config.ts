/**
 * Centralized configuration for LocalTopSH bot
 * All timing, limits and behavioral settings in one place
 */

export const CONFIG = {
  // ============== RATE LIMITING ==============
  rateLimit: {
    globalMinInterval: 200,       // ms between any telegram messages (5/sec max)
    groupMinInterval: 5000,       // ms for group messages (avoid 429)
    maxRetries: 2,                // retry attempts on 429
    retryBuffer: 5,               // extra seconds to add to retry_after
  },

  // ============== CONCURRENT USERS ==============
  users: {
    maxConcurrent: 10,            // max users processing simultaneously
  },

  // ============== TIMEOUTS ==============
  timeouts: {
    toolExecution: 120_000,       // 120s - max time for any tool
    commandPending: 5 * 60_000,   // 5 min - pending command expires
    questionPending: 2 * 60_000,  // 2 min - pending question expires
    webFetch: 30_000,             // 30s - web fetch timeout
    memeApi: 10_000,              // 10s - meme API timeout
    grepTimeout: 30_000,          // 30s - grep command timeout
  },

  // ============== SANDBOX (Docker) ==============
  sandbox: {
    commandTimeout: 120,          // sec - max time for single command
    backgroundTimeout: 3600,      // sec - max time for background process (1 hour)
    userInactivityTTL: 60,        // min - kill processes after user inactive
    memoryMB: 512,                // MB - memory limit per command
    maxFileSizeMB: 100,           // MB - max file size (prevent zip bombs)
    maxFiles: 64,                 // max open file descriptors
    maxProcs: 32,                 // max processes per user
    cleanupInterval: 5,           // min - how often to check for inactive users
  },

  // ============== AGENT BEHAVIOR ==============
  agent: {
    maxIterations: 15,            // max think-act cycles per request
    maxHistory: 10,               // conversation pairs to keep
    maxBlockedCommands: 3,        // stop after N blocked commands
  },

  // ============== BOT RESPONSES ==============
  bot: {
    thinkDelayMin: 500,           // ms - min delay before responding
    thinkDelayMax: 2000,          // ms - max delay before responding
    typingInterval: 5000,         // ms - send typing action interval
    trollDelay: 2000,             // ms - delay before troll message
    
    // Игнорирование (более человечное поведение)
    ignoreChance: 0.05,           // 5% шанс проигнорировать сообщение в группе
    ignorePrivateChance: 0,       // 0% в личке (всегда отвечаем)
    
    // Отложенный ответ
    delayedResponseChance: 0.20,  // 20% шанс ответить с задержкой
    delayedResponseMin: 3000,     // ms - минимальная задержка
    delayedResponseMax: 15000,    // ms - максимальная задержка (до 15 сек)
  },

  // ============== STATUS UPDATES ==============
  status: {
    minEditInterval: 3000,        // ms - min time between status edits
    toolUpdateInterval: 2,        // update every N tools
  },

  // ============== REACTIONS ==============
  reactions: {
    minInterval: 5000,            // ms between reactions
    randomChance: 0.15,           // 15% chance to react to messages
    minTextLength: 10,            // min chars to consider reacting
    llmMaxTokens: 10,             // max tokens for reaction LLM
    // Weights for random category selection
    weights: {
      positive: 0.40,
      neutral: 0.30,
      negative: 0.30,
    },
  },

  // ============== RANDOM TRIGGERS ==============
  triggers: {
    randomReplyChance: 0.10,      // 10% random reply in groups
    minTextForRandom: 15,         // min chars for random trigger
  },

  // ============== AUTONOMOUS THOUGHTS ==============
  thoughts: {
    enabled: true,
    minIntervalMin: 10,           // min minutes between thoughts
    maxIntervalMin: 30,           // max minutes between thoughts
    startDelayMin: 5,             // minutes before first thought
  },

  // ============== AFK MODE ==============
  afk: {
    maxMinutes: 60,               // max AFK duration
    defaultMinutes: 5,            // default if not specified
  },

  // ============== MESSAGES ==============
  messages: {
    maxLength: 4000,              // max telegram message length
    outputTrimLength: 3000,       // trim tool output if longer
    outputHeadLength: 1500,       // keep first N chars when trimming
    outputTailLength: 1000,       // keep last N chars when trimming
    historySliceLength: 500,      // chars to save in chat history
    logSliceLength: 80,           // chars to save in global log
  },

  // ============== STORAGE ==============
  storage: {
    maxChatMessages: 2500,         // max messages in CHAT_HISTORY.md
    maxMemoryChars: 2000,         // max chars from memory in prompt
    chatMessageLength: 200,       // max chars per chat message
    logDetailsLength: 100,        // max chars for log details
  },

  // ============== MEME API ==============
  meme: {
    maxCount: 5,                  // max memes per request
  },

  // ============== ADMIN ==============
  admin: {
    userId: 809532582,            // VaKovaLskii - bot owner
  },

  // ============== DONE REACTIONS (after successful response) ==============
  doneEmojis: ['👍', '🔥', '💯', '👌', '🎉', '⚡', '🤩', '🏆'],
  
  // ============== ALL VALID REACTIONS ==============
  allReactions: {
    positive: ['❤️', '🔥', '👍', '🎉', '💯', '🤩', '👏', '😍', '🤗', '🏆', '🙏', '👌', '🕊', '⚡', '🥰', '😁', '🤣', '❤️‍🔥'],
    negative: ['💩', '👎', '🤡', '😴', '🥱', '🗿', '🤮', '💔', '😡', '🤬', '😢'],
    neutral: ['👀', '🤔', '🤨', '😐', '🌚', '👻', '🤷', '🫡', '😎', '😈', '🙈', '🎃', '🤯', '✍️', '👾', '😱'],
  },
} as const;

// Helper to get random done emoji
export function getRandomDoneEmoji(): string {
  return CONFIG.doneEmojis[Math.floor(Math.random() * CONFIG.doneEmojis.length)];
}

// Helper to get all reactions as flat array
export function getAllReactions(): string[] {
  return [
    ...CONFIG.allReactions.positive,
    ...CONFIG.allReactions.negative,
    ...CONFIG.allReactions.neutral,
  ];
}

// Export type for autocomplete
export type Config = typeof CONFIG;
