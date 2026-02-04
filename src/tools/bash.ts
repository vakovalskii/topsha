/**
 * run_command - Execute shell commands
 * Pattern: Action (run) + Object (command)
 * Security: Dangerous commands require user approval
 * Background: Commands ending with & run in background
 */

import { exec, spawn } from 'child_process';
import { promisify } from 'util';
import { CONFIG } from '../config.js';
import { 
  executeInSandbox as dockerExecute, 
  isDockerAvailable,
  markUserActive as markSandboxActive,
} from './dockerSandbox.js';
import { registerProcess, markUserActive } from './processManager.js';

const execAsync = promisify(exec);
import { checkCommand, storePendingCommand } from '../approvals/index.js';

// Docker sandbox status (set after async check)
let dockerAvailable = false;
isDockerAvailable().then(available => {
  dockerAvailable = available;
  console.log(`[sandbox] Docker available: ${available}`);
});

// Patterns to sanitize from output
const SECRET_PATTERNS = [
  // API Keys and Tokens
  /([A-Za-z0-9_]*(?:API[_-]?KEY|APIKEY|TOKEN|SECRET|PASSWORD|PASS|CREDENTIAL|AUTH)[A-Za-z0-9_]*)=([^\s\n]+)/gi,
  // Common key formats
  /sk-[A-Za-z0-9]{20,}/g,  // OpenAI-style keys
  /tvly-[A-Za-z0-9-]{20,}/g,  // Tavily keys
  /[a-f0-9]{32}\.[A-Za-z0-9]{10,}/g,  // ZAI-style keys (lowered threshold)
  /ghp_[A-Za-z0-9]{36,}/g,  // GitHub tokens
  /gho_[A-Za-z0-9]{36,}/g,  // GitHub OAuth
  /github_pat_[A-Za-z0-9_]{36,}/g,  // GitHub PAT
  /xox[baprs]-[A-Za-z0-9-]{10,}/g,  // Slack tokens
  /\b[0-9]{8,12}:[A-Za-z0-9_-]{35}\b/g,  // Telegram bot tokens
  /Bearer\s+[A-Za-z0-9._-]{20,}/gi,  // Bearer tokens
  /Basic\s+[A-Za-z0-9+/=]{20,}/gi,  // Basic auth
  // AWS
  /AKIA[0-9A-Z]{16}/g,  // AWS Access Key ID
  /[A-Za-z0-9/+=]{40}(?=\s|$|")/g,  // AWS Secret (heuristic)
  // Private keys
  /-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+ PRIVATE KEY-----/g,
  // Generic secrets with common env var names
  /(?:TELEGRAM_TOKEN|API_KEY|APIKEY|ZAI_API_KEY|TAVILY_API_KEY|BASE_URL|MCP_URL)=\S+/gi,
  // IP:port patterns (LLM endpoints, internal services)
  /https?:\/\/\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+[^\s"]*/g,
  // Telegram bot token format: 123456789:AAHxxxxxxx
  /\d{9,12}:AA[A-Za-z0-9_-]{30,}/g,
];

// Detect base64 encoded env dumps (like the attack used)
function containsEncodedSecrets(output: string): boolean {
  // Look for long base64 strings (potential env dump)
  const base64Pattern = /[A-Za-z0-9+/]{100,}={0,2}/g;
  const matches = output.match(base64Pattern);
  
  if (matches) {
    for (const match of matches) {
      try {
        const decoded = Buffer.from(match, 'base64').toString('utf-8');
        // Check if decoded content looks like env vars or secrets
        if (
          decoded.includes('API_KEY') ||
          decoded.includes('TOKEN') ||
          decoded.includes('SECRET') ||
          decoded.includes('PASSWORD') ||
          decoded.includes('TELEGRAM') ||
          decoded.includes('process.env') ||
          decoded.includes('ZAI_') ||
          decoded.includes('BASE_URL') ||
          decoded.includes('MCP_') ||
          decoded.includes('WORKSPACE') ||
          /[a-f0-9]{32}\.[A-Za-z0-9]{10,}/.test(decoded) ||  // ZAI key pattern
          /sk-[A-Za-z0-9_-]{15,}/.test(decoded) ||  // OpenAI-style key
          /\d{9,12}:AA[A-Za-z0-9_-]{30,}/.test(decoded) ||  // Telegram token
          /\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+/.test(decoded)  // IP:port
        ) {
          return true;
        }
      } catch {
        // Not valid base64, ignore
      }
    }
  }
  return false;
}

// Check if output contains suspicious patterns even in plaintext
function containsSuspiciousEnvDump(output: string): boolean {
  // JSON with multiple env-like keys = probably env dump
  const envKeyCount = (output.match(/"[A-Z_]{3,}":/g) || []).length;
  if (envKeyCount > 5) {
    // Looks like JSON env dump, check for sensitive keys
    if (
      output.includes('"API_KEY"') ||
      output.includes('"TOKEN"') ||
      output.includes('"SECRET"') ||
      output.includes('"ZAI_') ||
      output.includes('"TELEGRAM') ||
      output.includes('"BASE_URL"') ||
      output.includes('"MCP_') ||
      output.includes('"WORKSPACE"') ||
      output.includes('"HOME"') ||
      output.includes('"PATH"')
    ) {
      return true;
    }
  }
  
  // Also check for shell-style env dump (VAR=value format with many lines)
  const shellEnvCount = (output.match(/^[A-Z_]{3,}=.+$/gm) || []).length;
  if (shellEnvCount > 5) {
    return true;
  }
  
  return false;
}

/**
 * Remove secrets from output
 */
function sanitizeOutput(output: string): string {
  // First check for encoded/disguised secrets
  if (containsEncodedSecrets(output)) {
    console.log('[SECURITY] Detected base64-encoded secrets in output, blocking');
    return '🚫 [OUTPUT BLOCKED: Contains encoded sensitive data]';
  }
  
  // Check for env dump patterns
  if (containsSuspiciousEnvDump(output)) {
    console.log('[SECURITY] Detected env dump pattern in output, blocking');
    return '🚫 [OUTPUT BLOCKED: Looks like environment dump]';
  }
  
  let sanitized = output;
  
  for (const pattern of SECRET_PATTERNS) {
    sanitized = sanitized.replace(pattern, (match) => {
      // For key=value patterns, keep the key name
      if (match.includes('=')) {
        const key = match.split('=')[0];
        return `${key}=[REDACTED]`;
      }
      // For raw secrets, show partial
      if (match.length > 10) {
        return match.slice(0, 4) + '***[REDACTED]***';
      }
      return '[REDACTED]';
    });
  }
  
  return sanitized;
}

// Callback for showing approval buttons (non-blocking)
let showApprovalCallback: ((
  chatId: number,
  commandId: string,
  command: string,
  reason: string
) => void) | null = null;

/**
 * Set the callback to show approval buttons
 */
export function setApprovalCallback(
  callback: (chatId: number, commandId: string, command: string, reason: string) => void
) {
  showApprovalCallback = callback;
}

export const definition = {
  type: "function" as const,
  function: {
    name: "run_command",
    description: "Run a shell command. Use for: git, npm, pip, system operations. DANGEROUS commands (rm -rf, sudo, etc.) require user approval.",
    parameters: {
      type: "object",
      properties: {
        command: { 
          type: "string", 
          description: "The shell command to execute" 
        },
      },
      required: ["command"],
    },
  },
};

export interface ExecuteContext {
  cwd: string;
  sessionId?: string;
  chatId?: number;
  chatType?: 'private' | 'group' | 'supergroup' | 'channel';
}

/**
 * Check if command tries to access other user's workspace
 */
function checkWorkspaceIsolation(command: string, userWorkspace: string): { blocked: boolean; reason?: string } {
  // Extract user ID from workspace path (e.g., /workspace/123456789 -> 123456789)
  const userMatch = userWorkspace.match(/\/workspace\/(\d+)/);
  if (!userMatch) {
    return { blocked: false };  // Not in workspace structure
  }
  const userId = userMatch[1];
  
  // Patterns that access other workspaces
  const otherWorkspacePatterns = [
    // Direct access to /workspace/OTHER_ID
    new RegExp(`/workspace/(?!${userId})[\\d_]`, 'i'),
    // Wildcard access to all workspaces
    /\/workspace\/\*/,
    // Find/ls/cat across /workspace root (show all users)
    /\b(find|ls|cat|head|tail|grep|less|more|tree|du|wc)\s+[^|]*\/workspace\s*($|[|;>&\n])/,
    // Access to _shared folder (global logs)
    /\/workspace\/_shared/i,
    // Parent directory traversal from workspace
    /\.\.\/\.\./,
    // glob patterns that might match other workspaces
    /\/workspace\/\[/,
    /\/workspace\/\{/,
  ];
  
  for (const pattern of otherWorkspacePatterns) {
    if (pattern.test(command)) {
      return { 
        blocked: true, 
        reason: 'BLOCKED: Cannot access other user workspaces. Use only your own workspace.' 
      };
    }
  }
  
  return { blocked: false };
}

export async function execute(
  args: { command: string },
  cwd: string | ExecuteContext
): Promise<{ success: boolean; output?: string; error?: string; approval_required?: boolean }> {
  // Handle both old (string) and new (object) signatures
  const context: ExecuteContext = typeof cwd === 'string' ? { cwd } : cwd;
  const workDir = context.cwd;
  const sessionId = context.sessionId || 'default';
  const chatId = context.chatId || 0;
  const chatType = context.chatType;
  
  // Check workspace isolation first
  const workspaceCheck = checkWorkspaceIsolation(args.command, workDir);
  if (workspaceCheck.blocked) {
    console.log(`[SECURITY] Workspace isolation: ${args.command}`);
    return {
      success: false,
      error: `🚫 ${workspaceCheck.reason}`,
    };
  }
  
  // Check if command is dangerous or blocked
  // In groups: dangerous = blocked (no approval possible)
  const { dangerous, blocked, reason } = checkCommand(args.command, chatType);
  
  // BLOCKED commands - never allowed, even with approval
  if (blocked) {
    console.log(`[SECURITY] BLOCKED command: ${args.command}`);
    console.log(`[SECURITY] Reason: ${reason}`);
    return {
      success: false,
      error: `🚫 ${reason}\n\nThis command is not allowed for security reasons.`,
    };
  }
  
  // DANGEROUS commands - require approval
  if (dangerous) {
    console.log(`[SECURITY] Dangerous command detected: ${args.command}`);
    console.log(`[SECURITY] Reason: ${reason}`);
    
    // Store command and show approval buttons
    const commandId = storePendingCommand(sessionId, chatId, args.command, workDir, reason!);
    
    // Show buttons (non-blocking)
    if (showApprovalCallback && chatId) {
      showApprovalCallback(chatId, commandId, args.command, reason!);
    }
    
    return {
      success: false,
      error: `⚠️ APPROVAL REQUIRED: "${reason}"\n\nWaiting for user to click Approve/Deny button.`,
      approval_required: true,
    };
  }
  
  return await executeCommand(args.command, workDir);
}

/**
 * Extract userId from workspace path
 */
function extractUserId(cwd: string): string | null {
  const match = cwd.match(/\/workspace\/(\d+)/);
  return match ? match[1] : null;
}

/**
 * Execute a command (used for both regular and approved commands)
 * Uses Docker sandbox for isolation when available
 */
export async function executeCommand(
  command: string,
  cwd: string
): Promise<{ success: boolean; output?: string; error?: string }> {
  const userId = extractUserId(cwd);
  const useSandbox = dockerAvailable && userId;
  
  // Check if command should run in background
  const isBackground = /&\s*$/.test(command.trim()) || command.includes('nohup');
  
  // === DOCKER SANDBOX EXECUTION ===
  if (useSandbox) {
    console.log(`[sandbox] Executing in Docker for user ${userId}`);
    
    // Mark user active
    markSandboxActive(userId);
    
    const result = await dockerExecute(userId, command, cwd);
    
    if (result.sandboxed) {
      // Sanitize output even from sandbox (defense in depth)
      const sanitized = sanitizeOutput(result.output || '');
      
      // Truncate if needed
      const maxOutput = 4000;
      const trimmed = sanitized.length > maxOutput 
        ? sanitized.slice(0, 2000) + '\n\n...(truncated)...\n\n' + sanitized.slice(-1500)
        : sanitized;
      
      return result.success 
        ? { success: true, output: trimmed || '(empty output)' }
        : { success: false, error: trimmed };
    }
    // If sandbox failed to run, fall through to regular execution
    console.log('[sandbox] Docker sandbox failed, falling back to regular execution');
  }
  
  // === BACKGROUND COMMANDS (no sandbox fallback) ===
  if (isBackground) {
    const cleanCmd = command.trim().replace(/&\s*$/, '').trim();
    
    try {
      const child = spawn('sh', ['-c', cleanCmd], {
        cwd,
        detached: true,
        stdio: 'ignore',
      });
      
      child.unref();
      
      // Wait a bit and check if process is still running
      await new Promise(r => setTimeout(r, 500));
      
      try {
        process.kill(child.pid!, 0); // Check if alive
        
        // Register process for tracking and cleanup
        if (userId) {
          registerProcess(userId, child.pid!, cleanCmd);
        }
        
        return { 
          success: true, 
          output: `Started in background (PID: ${child.pid}). Max lifetime: ${CONFIG.sandbox.backgroundTimeout / 60} min. Check logs with: tail <logfile>` 
        };
      } catch {
        // Process died immediately - likely an error
        return { 
          success: false, 
          error: `Process started but died immediately (PID: ${child.pid}). Check the log file for errors! Common issues: missing module (pip install first), syntax error, port in use.` 
        };
      }
    } catch (e: any) {
      return { 
        success: false, 
        error: `Failed to start background process: ${e.message}` 
      };
    }
  }
  
  // === REGULAR EXECUTION (no sandbox) ===
  // This path is used when sandbox is not available or for system commands
  try {
    const { stdout, stderr } = await execAsync(command, {
      cwd,
      encoding: 'utf-8',
      timeout: CONFIG.timeouts.toolExecution,
      maxBuffer: 1024 * 1024 * 10,
    });
    
    const output = stdout || stderr || '';
    
    // Sanitize secrets from output
    const sanitized = sanitizeOutput(output);
    
    // Limit output to prevent context overflow and rate limits
    const maxOutput = 4000;
    const trimmed = sanitized.length > maxOutput 
      ? sanitized.slice(0, 2000) + '\n\n...(truncated ' + (sanitized.length - maxOutput) + ' chars)...\n\n' + sanitized.slice(-1500)
      : sanitized;
    
    return { success: true, output: trimmed || "(empty output)" };
  } catch (e: any) {
    const stderr = e.stderr?.toString() || '';
    const stdout = e.stdout?.toString() || '';
    const full = stderr || stdout || e.message;
    
    // Sanitize secrets from error output too
    const sanitized = sanitizeOutput(full);
    
    // Truncate error output
    const trimmed = sanitized.length > 5000 
      ? sanitized.slice(0, 2500) + '\n...(truncated)...\n' + sanitized.slice(-2000)
      : sanitized;
    
    return { 
      success: false, 
      error: `Exit ${e.status || 1}: ${trimmed}`
    };
  }
}
