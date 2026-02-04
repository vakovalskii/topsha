/**
 * ReAct Agent - Reasoning + Acting loop
 * Core: Think → Act → Observe → Repeat
 * 
 * Session format (clean, no tool calls in history):
 * - System prompt (fresh each time)
 * - [User + Assistant pairs from previous conversations]
 * - Current user message
 */

import OpenAI from 'openai';
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import * as tools from '../tools/index.js';
import { getMemoryForPrompt, getChatHistory } from '../tools/memory.js';
import { CONFIG } from '../config.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SYSTEM_PROMPT_FILE = join(__dirname, 'system.txt');

export interface AgentConfig {
  baseUrl: string;
  apiKey: string;
  model: string;
  cwd: string;
  zaiApiKey?: string;
  tavilyApiKey?: string;
  maxIterations?: number;
  maxHistory?: number;  // max user-assistant pairs to keep
  exposedPorts?: number[];  // ports exposed to external network
}

// Simple session: just user-assistant pairs (no tool calls)
export interface Session {
  history: Array<{ user: string; assistant: string }>;
}

// Session persistence helpers
const SESSION_FILE = 'SESSION.json';

function loadSession(cwd: string): Session {
  try {
    const sessionPath = join(cwd, SESSION_FILE);
    if (existsSync(sessionPath)) {
      const data = readFileSync(sessionPath, 'utf-8');
      return JSON.parse(data);
    }
  } catch (e) {
    console.error('[session] Error loading:', e);
  }
  return { history: [] };
}

function saveSession(cwd: string, session: Session) {
  try {
    const sessionPath = join(cwd, SESSION_FILE);
    writeFileSync(sessionPath, JSON.stringify(session, null, 2), 'utf-8');
  } catch (e) {
    console.error('[session] Error saving:', e);
  }
}

export class ReActAgent {
  private openai: OpenAI;
  private config: AgentConfig;
  private sessions = new Map<string, Session>();
  private currentChatId?: number;  // Set during run() for chat history
  
  constructor(config: AgentConfig) {
    this.config = {
      maxIterations: CONFIG.agent.maxIterations,
      maxHistory: CONFIG.agent.maxHistory,
      exposedPorts: [],
      ...config,
    };
    
    this.openai = new OpenAI({
      apiKey: config.apiKey,
      baseURL: config.baseUrl,
    });
  }
  
  private getSession(id: string, cwd: string): Session {
    if (!this.sessions.has(id)) {
      // Try to load from disk first
      const loaded = loadSession(cwd);
      this.sessions.set(id, loaded);
    }
    return this.sessions.get(id)!;
  }
  
  private getSystemPrompt(): string {
    let prompt = readFileSync(SYSTEM_PROMPT_FILE, 'utf-8');
    
    // Extract userId from cwd path (e.g., /workspace/123456789 -> 123456789)
    const cwdParts = this.config.cwd.split('/');
    const userIdStr = cwdParts[cwdParts.length - 1];
    const userId = parseInt(userIdStr) || 0;
    
    // Calculate user's port range (each user gets 10 ports)
    // Base port 5000 (sandbox containers), user index = hash of ID mod 10
    const userIndex = userId % 10;
    const basePort = 5000 + (userIndex * 10);
    const userPorts = `${basePort}-${basePort + 9}`;
    
    // Replace placeholders
    prompt = prompt
      .replace('{{cwd}}', this.config.cwd)
      .replace('{{date}}', new Date().toISOString().slice(0, 10))
      .replace('{{tools}}', tools.toolNames.join(', '))
      .replace('{{userPorts}}', userPorts);
    
    // Add exposed ports info
    if (this.config.exposedPorts?.length) {
      prompt += `\n\n<NETWORK>
External access via: http://HOST_IP:PORT
Your port range: ${userPorts}
Check if port free: lsof -i :PORT or netstat -tlnp | grep PORT
</NETWORK>`;
    }
    
    // Add memory from previous sessions
    const memoryContent = getMemoryForPrompt(this.config.cwd);
    if (memoryContent) {
      prompt += `\n\n<MEMORY>
Notes from previous sessions (use "memory" tool to update):
${memoryContent}
</MEMORY>`;
    }
    
    // Add recent chat history (per-chat, uses currentChatId)
    const chatHistory = getChatHistory(this.currentChatId);
    if (chatHistory) {
      const lineCount = chatHistory.split('\n').filter(l => l.trim()).length;
      prompt += `\n\n<RECENT_CHAT>
История чата (${lineCount} сообщений). ЭТО ВСЁ что у тебя есть - от самых старых к новым:
${chatHistory}
</RECENT_CHAT>`;
    }
    
    return prompt;
  }
  
  // Build messages for API call (during agent loop)
  private buildMessages(
    session: Session, 
    userMessage: string,
    workingMessages: OpenAI.ChatCompletionMessageParam[] = []
  ): OpenAI.ChatCompletionMessageParam[] {
    const messages: OpenAI.ChatCompletionMessageParam[] = [];
    
    // 1. Fresh system prompt
    messages.push({ role: 'system', content: this.getSystemPrompt() });
    
    // 2. Previous conversations (user-assistant pairs only)
    for (const conv of session.history) {
      messages.push({ role: 'user', content: conv.user });
      messages.push({ role: 'assistant', content: conv.assistant });
    }
    
    // 3. Current user message
    const dateStr = new Date().toISOString().slice(0, 10);
    messages.push({ role: 'user', content: `[${dateStr}] ${userMessage}` });
    
    // 4. Working messages (tool calls during current cycle)
    messages.push(...workingMessages);
    
    return messages;
  }
  
  // Main ReAct loop
  async run(
    sessionId: string,
    userMessage: string,
    onToolCall?: (name: string) => void,
    chatId?: number,
    chatType?: 'private' | 'group' | 'supergroup' | 'channel'
  ): Promise<string> {
    // Set current chat ID for history retrieval
    this.currentChatId = chatId;
    
    const session = this.getSession(sessionId, this.config.cwd);
    const dateStr = new Date().toISOString().slice(0, 10);
    const currentUserMsg = `[${dateStr}] ${userMessage}`;
    
    // Working messages for current agent cycle (tool calls, results)
    let workingMessages: OpenAI.ChatCompletionMessageParam[] = [];
    let iteration = 0;
    let finalResponse = '';
    let blockedCount = 0;  // Track consecutive BLOCKED errors
    
    // ReAct loop: Think → Act → Observe
    while (iteration < this.config.maxIterations!) {
      iteration++;
      
      try {
        // Build full message list
        const messages = this.buildMessages(session, userMessage, workingMessages);
        
        // Minimal logging
        if (iteration === 1) {
          console.log(`[agent] Turn ${iteration}...`);
        }
        
        // Think: LLM decides what to do
        const response = await this.openai.chat.completions.create({
          model: this.config.model,
          messages,
          tools: tools.definitions as any[],
          tool_choice: 'auto',
        });
        
        const rawMessage = response.choices[0].message;
        
        // Clean message - remove non-standard fields (reasoning, etc.)
        // Only keep standard OpenAI fields to avoid API errors
        const message: OpenAI.ChatCompletionMessageParam = {
          role: rawMessage.role,
          content: rawMessage.content,
          ...(rawMessage.tool_calls && { tool_calls: rawMessage.tool_calls }),
        };
        
        // No tool calls = task complete
        if (!rawMessage.tool_calls?.length) {
          if (!rawMessage.content) {
            workingMessages.push(message);
            workingMessages.push({
              role: 'user',
              content: 'Continue. Finish the task or explain what you did.',
            });
            continue;
          }
          
          finalResponse = rawMessage.content;
          break;
        }
        
        // Add cleaned assistant message with tool calls to working messages
        workingMessages.push(message);
        
        // Act: Execute tools
        let hasBlocked = false;
        for (const call of message.tool_calls || []) {
          const name = call.function.name;
          
          // Parse args with error handling (LLM sometimes returns invalid JSON)
          let args: Record<string, any> = {};
          try {
            args = JSON.parse(call.function.arguments || '{}');
          } catch (parseError: any) {
            console.log(`[agent] Error: ${parseError}`);
            // Try to fix common JSON issues
            let fixed = (call.function.arguments || '{}')
              .replace(/,\s*}/g, '}')  // trailing comma
              .replace(/,\s*]/g, ']')  // trailing comma in array
              .replace(/'/g, '"')       // single quotes
              .replace(/\n/g, '\\n');   // unescaped newlines
            try {
              args = JSON.parse(fixed);
            } catch {
              // Give up, use empty args
              console.log(`[agent] Could not parse tool args, using empty`);
            }
          }
          
          onToolCall?.(name);
          
          // Observe: Get tool result
          const result = await tools.execute(name, args, {
            cwd: this.config.cwd,
            sessionId,
            userId: parseInt(sessionId) || 0,
            chatId,
            chatType,
            zaiApiKey: this.config.zaiApiKey,
            tavilyApiKey: this.config.tavilyApiKey,
          });
          
          let output = result.success 
            ? (result.output || 'Success') 
            : `Error: ${result.error}`;
          
          // Track BLOCKED commands to prevent loops
          if (output.includes('BLOCKED:')) {
            hasBlocked = true;
            blockedCount++;
            output += '\n\n⛔ THIS COMMAND IS PERMANENTLY BLOCKED. Do NOT retry it. Find an alternative approach or inform the user this action is not allowed.';
            console.log(`[SECURITY] BLOCKED count: ${blockedCount}/${CONFIG.agent.maxBlockedCommands}`);
          }
          
          workingMessages.push({
            role: 'tool',
            tool_call_id: call.id,
            content: output,
          });
        }
        
        // Stop if too many BLOCKED commands (prevent loops)
        if (blockedCount >= CONFIG.agent.maxBlockedCommands) {
          console.log(`[SECURITY] Too many BLOCKED commands (${blockedCount}), stopping agent`);
          finalResponse = '🚫 Stopped: Multiple blocked commands detected. The requested actions are not allowed for security reasons.';
          break;
        }
        
        // Reset blocked count if no blocked commands this iteration
        if (!hasBlocked) {
          blockedCount = 0;
        }
        
      } catch (e: any) {
        console.error('[agent] Error:', e);
        return `Error: ${e.message}`;
      }
    }
    
    if (!finalResponse) {
      finalResponse = '⚠️ Max iterations reached';
    }
    
    // Save to history (clean: just user message + final response)
    session.history.push({
      user: currentUserMsg,
      assistant: finalResponse,
    });
    
    // Trim history if too long
    while (session.history.length > this.config.maxHistory!) {
      session.history.shift();
    }
    
    // Persist to disk
    saveSession(this.config.cwd, session);
    
    console.log(`[session] History: ${session.history.length} conversations (saved)`);
    
    return finalResponse;
  }
  
  clear(sessionId: string, cwd?: string) {
    this.sessions.delete(sessionId);
    // Also clear file if cwd provided
    if (cwd) {
      try {
        const sessionPath = join(cwd, SESSION_FILE);
        if (existsSync(sessionPath)) {
          writeFileSync(sessionPath, JSON.stringify({ history: [] }), 'utf-8');
        }
      } catch {}
    }
  }
  
  getInfo(sessionId: string, cwd?: string) {
    let session = this.sessions.get(sessionId);
    // Try loading from disk if not in memory
    if (!session && cwd) {
      session = loadSession(cwd);
    }
    return {
      messages: session?.history.length || 0,
      tools: tools.toolNames.length,
    };
  }
}
