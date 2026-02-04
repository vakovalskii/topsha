/**
 * Tools Registry
 * Pattern: Action + Object
 * 
 * Core tools:
 * - run_command      : Execute shell commands
 * - read_file        : Read file contents
 * - write_file       : Write/create files
 * - edit_file        : Edit files (find & replace)
 * - delete_file      : Delete files
 * - search_files     : Find files by glob pattern
 * - search_text      : Search text in files (grep)
 * - list_directory   : List directory contents
 * - search_web       : Search the internet (Z.AI + Tavily)
 * - fetch_page       : Fetch URL content
 * - manage_tasks     : Task management (todo list)
 * - ask_user         : Ask user with button options
 * - send_file        : Send file from workspace to chat
 * - send_dm          : Send direct message to user's private chat
 */

import * as bash from './bash.js';
import * as files from './files.js';
import * as web from './web.js';
import * as tasks from './tasks.js';
import * as ask from './ask.js';
import * as memory from './memory.js';
import * as sendFile from './sendFile.js';
import * as sendDm from './sendDm.js';
import * as message from './message.js';
import * as meme from './meme.js';
import * as scheduler from './scheduler.js';
import { CONFIG } from '../config.js';

// Re-export callback setters
export { setApprovalCallback } from './bash.js';
export { setAskCallback } from './ask.js';
export { setSendFileCallback } from './sendFile.js';
export { setSendDmCallback } from './sendDm.js';
export { setDeleteMessageCallback, setEditMessageCallback, recordBotMessage } from './message.js';
export { setSendMessageCallback, setExecuteCommandCallback, startScheduler } from './scheduler.js';
export { getMemoryForPrompt, logGlobal, getGlobalLog, shouldTroll, getTrollMessage, saveChatMessage, getChatHistory } from './memory.js';
export { getChatHistory as getChatHistoryForPrompt } from './memory.js';
export { setProxyUrl } from './web.js';

// Tool definitions for OpenAI
export const definitions = [
  bash.definition,
  files.readDefinition,
  files.writeDefinition,
  files.editDefinition,
  files.deleteDefinition,
  files.searchFilesDefinition,
  files.searchTextDefinition,
  files.listDirectoryDefinition,
  web.searchWebDefinition,
  web.fetchPageDefinition,
  tasks.manageTasksDefinition,
  ask.definition,
  memory.definition,
  sendFile.definition,
  sendDm.definition,
  message.definition,
  meme.definition,
  scheduler.definition,
];

// Tool names
export const toolNames = definitions.map(d => d.function.name);

// Result type
export interface ToolResult {
  success: boolean;
  output?: string;
  error?: string;
}

// Context
export interface ToolContext {
  cwd: string;
  sessionId?: string;
  userId?: number;
  chatId?: number;
  chatType?: 'private' | 'group' | 'supergroup' | 'channel';
  zaiApiKey?: string;
  tavilyApiKey?: string;
}

// Format args for logging (truncate long values)
function formatArgs(args: Record<string, any>): string {
  const parts: string[] = [];
  for (const [key, value] of Object.entries(args)) {
    let v = typeof value === 'string' ? value : JSON.stringify(value);
    if (v.length > 60) v = v.slice(0, 60) + '...';
    parts.push(`${key}=${v}`);
  }
  return parts.join(', ');
}

// Timeout for all tool executions (from config)

async function withTimeout<T>(promise: Promise<T>, timeoutMs: number, toolName: string): Promise<T> {
  let timeoutId: NodeJS.Timeout;
  
  const timeoutPromise = new Promise<never>((_, reject) => {
    timeoutId = setTimeout(() => {
      reject(new Error(`Tool ${toolName} timed out after ${timeoutMs / 1000}s`));
    }, timeoutMs);
  });
  
  try {
    const result = await Promise.race([promise, timeoutPromise]);
    clearTimeout(timeoutId!);
    return result;
  } catch (e) {
    clearTimeout(timeoutId!);
    throw e;
  }
}

// Execute tool by name (with 120s timeout)
export async function execute(
  name: string, 
  args: Record<string, any>,
  ctx: ToolContext
): Promise<ToolResult> {
  const argsStr = formatArgs(args);
  console.log(`[tool] ${name}(${argsStr})`);
  
  try {
    const result = await withTimeout(
      executeInternal(name, args, ctx),
      CONFIG.timeouts.toolExecution,
      name
    );
    
    // Log result
    const output = result.success ? (result.output?.slice(0, 80) || 'ok') : `ERROR: ${result.error?.slice(0, 60)}`;
    console.log(`[tool] → ${output}${(result.output?.length || 0) > 80 ? '...' : ''}`);
    
    return result;
  } catch (e: any) {
    const errorMsg = e.message || 'Unknown error';
    console.log(`[tool] → TIMEOUT: ${errorMsg}`);
    return { success: false, error: `⏱️ ${errorMsg}` };
  }
}

// Internal execute without timeout
async function executeInternal(
  name: string, 
  args: Record<string, any>,
  ctx: ToolContext
): Promise<ToolResult> {
  let result: ToolResult;
  
  switch (name) {
    case 'run_command':
      result = await bash.execute(args as any, { cwd: ctx.cwd, sessionId: ctx.sessionId, chatId: ctx.chatId, chatType: ctx.chatType });
      break;
    
    case 'read_file':
      result = await files.executeRead(args as any, ctx.cwd);
      break;
    
    case 'write_file':
      result = await files.executeWrite(args as any, ctx.cwd);
      break;
    
    case 'edit_file':
      result = await files.executeEdit(args as any, ctx.cwd);
      break;
    
    case 'delete_file':
      result = await files.executeDelete(args as any, ctx.cwd);
      break;
    
    case 'search_files':
      result = await files.executeSearchFiles(args as any, ctx.cwd);
      break;
    
    case 'search_text':
      result = await files.executeSearchText(args as any, ctx.cwd);
      break;
    
    case 'list_directory':
      result = await files.executeListDirectory(args as any, ctx.cwd);
      break;
    
    case 'search_web':
      result = await web.executeSearchWeb(args as any, ctx.zaiApiKey, ctx.tavilyApiKey);
      break;
    
    case 'fetch_page':
      result = await web.executeFetchPage(args as any, ctx.zaiApiKey);
      break;
    
    case 'manage_tasks':
      result = await tasks.executeManageTasks(args as any, ctx.sessionId || 'default');
      break;
    
    case 'ask_user':
      result = await ask.execute(args as any, ctx.sessionId || 'default');
      break;
    
    case 'memory':
      result = await memory.execute(args as any, ctx.cwd);
      break;
    
    case 'send_file':
      result = await sendFile.execute(args as any, ctx.cwd, ctx.chatId || 0);
      break;
    
    case 'send_dm':
      result = await sendDm.execute(args as any, ctx.userId || 0);
      break;
    
    case 'manage_message':
      result = await message.execute(args as any, ctx.chatId || 0);
      break;
    
    case 'get_meme':
      result = await meme.execute(args as any);
      break;
    
    case 'schedule_task':
      result = await scheduler.execute(args as any, parseInt(ctx.sessionId || '0'), ctx.chatId || 0);
      break;
    
    default:
      result = { success: false, error: `Unknown tool: ${name}` };
  }
  
  return result;
}
