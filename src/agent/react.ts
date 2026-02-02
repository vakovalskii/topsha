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
import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import * as tools from '../tools/index.js';
import { getMemoryForPrompt } from '../tools/memory.js';

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

export class ReActAgent {
  private openai: OpenAI;
  private config: AgentConfig;
  private sessions = new Map<string, Session>();
  
  constructor(config: AgentConfig) {
    this.config = {
      maxIterations: 15,  // Reduced from 30 to prevent long loops
      maxHistory: 10,  // keep last 10 conversations
      exposedPorts: [],
      ...config,
    };
    
    this.openai = new OpenAI({
      apiKey: config.apiKey,
      baseURL: config.baseUrl,
    });
  }
  
  private getSession(id: string): Session {
    if (!this.sessions.has(id)) {
      this.sessions.set(id, { history: [] });
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
    // Base port 4000, user index = hash of ID mod 10 (max 10 concurrent users)
    const userIndex = userId % 10;
    const basePort = 4000 + (userIndex * 10);
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
    chatId?: number
  ): Promise<string> {
    const session = this.getSession(sessionId);
    const dateStr = new Date().toISOString().slice(0, 10);
    const currentUserMsg = `[${dateStr}] ${userMessage}`;
    
    // Working messages for current agent cycle (tool calls, results)
    let workingMessages: OpenAI.ChatCompletionMessageParam[] = [];
    let iteration = 0;
    let finalResponse = '';
    let blockedCount = 0;  // Track consecutive BLOCKED errors
    const MAX_BLOCKED = 3;  // Stop after 3 BLOCKED commands
    
    // ReAct loop: Think → Act → Observe
    while (iteration < this.config.maxIterations!) {
      iteration++;
      
      try {
        // Build full message list
        const messages = this.buildMessages(session, userMessage, workingMessages);
        
        // Log request
        console.log('\n' + '='.repeat(80));
        console.log(`[TURN ${iteration}] REQUEST → ${this.config.model}`);
        console.log('='.repeat(80));
        console.log('\nMESSAGES:');
        for (const m of messages) {
          console.log(`\n[${m.role.toUpperCase()}]`);
          if (typeof m.content === 'string') {
            console.log(m.content);
          }
          if ((m as any).tool_calls) {
            console.log('tool_calls:', JSON.stringify((m as any).tool_calls, null, 2));
          }
          if ((m as any).tool_call_id) {
            console.log(`tool_call_id: ${(m as any).tool_call_id}`);
          }
        }
        console.log('\nTOOLS:', tools.toolNames.join(', '));
        
        // Think: LLM decides what to do
        const response = await this.openai.chat.completions.create({
          model: this.config.model,
          messages,
          tools: tools.definitions as any[],
          tool_choice: 'auto',
        });
        
        // Log RAW response
        console.log('\n' + '-'.repeat(60));
        console.log(`[TURN ${iteration}] RAW RESPONSE`);
        console.log('-'.repeat(60));
        console.log(JSON.stringify(response, null, 2));
        
        const rawMessage = response.choices[0].message;
        
        // Log reasoning if present (vLLM reasoning models)
        const reasoning = (rawMessage as any).reasoning || (rawMessage as any).reasoning_content;
        if (reasoning) {
          console.log(`\n[REASONING] ${reasoning}`);
        }
        
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
            console.log('\n[WARN] Empty response, nudging model to continue...');
            workingMessages.push(message);
            workingMessages.push({
              role: 'user',
              content: 'Continue. Finish the task or explain what you did.',
            });
            continue;
          }
          
          finalResponse = rawMessage.content;
          console.log('\n[DONE] Final response');
          break;
        }
        
        // Add cleaned assistant message with tool calls to working messages
        workingMessages.push(message);
        
        // Act: Execute tools
        let hasBlocked = false;
        for (const call of message.tool_calls) {
          const name = call.function.name;
          const args = JSON.parse(call.function.arguments || '{}');
          
          console.log(`\n[TOOL] ${name}(${JSON.stringify(args)})`);
          
          onToolCall?.(name);
          
          // Observe: Get tool result
          const result = await tools.execute(name, args, {
            cwd: this.config.cwd,
            sessionId,
            chatId,
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
            console.log(`[SECURITY] BLOCKED count: ${blockedCount}/${MAX_BLOCKED}`);
          }
          
          console.log(`[RESULT] ${output.slice(0, 500)}${output.length > 500 ? '...' : ''}`);
          
          workingMessages.push({
            role: 'tool',
            tool_call_id: call.id,
            content: output,
          });
        }
        
        // Stop if too many BLOCKED commands (prevent loops)
        if (blockedCount >= MAX_BLOCKED) {
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
    
    console.log(`[session] History: ${session.history.length} conversations`);
    
    return finalResponse;
  }
  
  clear(sessionId: string) {
    this.sessions.delete(sessionId);
  }
  
  getInfo(sessionId: string) {
    const session = this.sessions.get(sessionId);
    return {
      messages: session?.history.length || 0,
      tools: tools.toolNames.length,
    };
  }
}
