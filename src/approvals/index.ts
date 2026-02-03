/**
 * Exec Approvals - confirmation for dangerous commands
 * Non-blocking architecture: save command, execute on approve
 */

import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

export interface PendingCommand {
  id: string;
  sessionId: string;
  chatId: number;
  command: string;
  cwd: string;
  reason: string;
  createdAt: number;
}

interface PatternConfig {
  id: string;
  category: string;
  pattern: string;
  flags?: string;
  reason: string;
}

interface BlockedPatternsJson {
  description: string;
  version: string;
  lastUpdated: string;
  patterns: PatternConfig[];
}

// Load blocked patterns from JSON
function loadBlockedPatterns(): { pattern: RegExp; reason: string }[] {
  try {
    const jsonPath = join(__dirname, 'blocked-patterns.json');
    const data = readFileSync(jsonPath, 'utf-8');
    const config: BlockedPatternsJson = JSON.parse(data);
    
    return config.patterns.map(p => ({
      pattern: new RegExp(p.pattern, p.flags || ''),
      reason: p.reason
    }));
  } catch (e) {
    console.error('[approvals] Failed to load blocked-patterns.json, using fallback:', e);
    // Fallback minimal patterns
    return [
      { pattern: /\benv\b(?!\s*=)/, reason: 'BLOCKED: env command' },
      { pattern: /\bprintenv\b/, reason: 'BLOCKED: printenv command' },
      { pattern: /\/proc\/.*\/environ/, reason: 'BLOCKED: proc environ' },
      { pattern: /\/run\/secrets/, reason: 'BLOCKED: Docker Secrets' },
      { pattern: /process\.env/, reason: 'BLOCKED: Node.js env' },
      { pattern: /os\.environ/, reason: 'BLOCKED: Python env' },
    ];
  }
}

// Load patterns at startup
const BLOCKED_PATTERNS = loadBlockedPatterns();
console.log(`[approvals] Loaded ${BLOCKED_PATTERNS.length} blocked patterns`);

// Dangerous command patterns - require approval (hardcoded for now)
const DANGEROUS_PATTERNS: { pattern: RegExp; reason: string }[] = [
  // Destructive file operations
  { pattern: /\brm\s+(-[rf]+\s+)*[\/~]/, reason: 'Recursive delete from root/home' },
  { pattern: /\brm\s+-[rf]*\s*\*/, reason: 'Wildcard delete' },
  { pattern: /\brm\s+-rf\b/, reason: 'Force recursive delete' },
  { pattern: /\brmdir\s+--ignore-fail-on-non-empty/, reason: 'Force directory removal' },
  
  // Privilege escalation
  { pattern: /\bsu\s+-?\s*$/, reason: 'Switch to root' },
  { pattern: /\bchown\s+-R\s+root/, reason: 'Change ownership to root' },
  
  // Dangerous permissions
  { pattern: /\bchmod\s+(-R\s+)?[0-7]*7[0-7]{2}\b/, reason: 'World-writable permissions' },
  { pattern: /\bchmod\s+(-R\s+)?777\b/, reason: 'Full permissions to everyone' },
  { pattern: /\bchmod\s+\+s\b/, reason: 'Set SUID/SGID bit' },
  
  // System modification
  { pattern: /\bmkfs\b/, reason: 'Format filesystem' },
  { pattern: /\bdd\s+.*of=\/dev\//, reason: 'Direct disk write' },
  { pattern: />\s*\/dev\/[sh]d[a-z]/, reason: 'Redirect to disk device' },
  { pattern: /\bfdisk\b/, reason: 'Partition manipulation' },
  { pattern: /\bparted\b/, reason: 'Partition manipulation' },
  
  // Network/Security
  { pattern: /\biptables\s+(-F|--flush)/, reason: 'Flush firewall rules' },
  { pattern: /\bufw\s+disable/, reason: 'Disable firewall' },
  { pattern: /\bsystemctl\s+(stop|disable)\s+(ssh|firewall|ufw)/, reason: 'Stop security service' },
  
  // Package management (can break system)
  { pattern: /\bapt(-get)?\s+(remove|purge)\s+.*-y/, reason: 'Auto-confirm package removal' },
  { pattern: /\byum\s+remove\s+.*-y/, reason: 'Auto-confirm package removal' },
  { pattern: /\bpip\s+uninstall\s+.*-y/, reason: 'Auto-confirm pip uninstall' },
  
  // Data destruction
  { pattern: /\btruncate\s+-s\s*0/, reason: 'Truncate file to zero' },
  { pattern: />\s*\/etc\//, reason: 'Overwrite system config' },
  { pattern: /\bshred\b/, reason: 'Secure file deletion' },
  
  // Process/System control (additional patterns not in BLOCKED)
  { pattern: /\bshutdown\b/, reason: 'System shutdown' },
  { pattern: /\breboot\b/, reason: 'System reboot' },
  { pattern: /\binit\s+[06]\b/, reason: 'System halt/reboot' },
  
  // Dangerous downloads/execution
  { pattern: /curl.*\|\s*(ba)?sh/, reason: 'Pipe URL to shell' },
  { pattern: /wget.*\|\s*(ba)?sh/, reason: 'Pipe URL to shell' },
  { pattern: /\beval\s+"?\$\(curl/, reason: 'Eval remote code' },
  
  // Git dangerous operations
  { pattern: /\bgit\s+push\s+.*--force/, reason: 'Force push (rewrites history)' },
  { pattern: /\bgit\s+reset\s+--hard\s+HEAD~/, reason: 'Hard reset (lose commits)' },
  { pattern: /\bgit\s+clean\s+-fd/, reason: 'Force clean untracked files' },
  
  // Database
  { pattern: /\bDROP\s+(DATABASE|TABLE)\b/i, reason: 'Drop database/table' },
  { pattern: /\bTRUNCATE\s+TABLE\b/i, reason: 'Truncate table' },
  { pattern: /\bDELETE\s+FROM\s+\w+\s*;?\s*$/i, reason: 'Delete all rows (no WHERE)' },
  
  // Environment
  { pattern: /\bexport\s+(PATH|LD_PRELOAD|LD_LIBRARY_PATH)=/, reason: 'Modify critical env var' },
  { pattern: /\bunset\s+(PATH|HOME)\b/, reason: 'Unset critical env var' },
  
  // Fork bomb / resource exhaustion
  { pattern: /:\(\)\s*{\s*:\|:&\s*}/, reason: 'Fork bomb' },
  { pattern: /while\s+true.*do.*done/, reason: 'Infinite loop' },
  
  // Resource-heavy commands
  { pattern: /\bfind\s+\/\s/, reason: 'Full filesystem scan (very slow)' },
  { pattern: /\bdu\s+-[ash]*\s+\/\s*$/, reason: 'Full disk usage scan' },
  { pattern: /\bls\s+-[laR]*\s+\/\s*$/, reason: 'Full filesystem listing' },
  
  // Additional dangerous patterns (from suicide-linux)
  { pattern: /\bcat\s+\/dev\/port/, reason: 'Read port device (system freeze)' },
  { pattern: /\bmv\s+.*\s+\/dev\/null/, reason: 'Move files to black hole' },
  { pattern: />\s*\/dev\/sda/, reason: 'Overwrite disk' },
  { pattern: /\bperl\s+-e\s+.*fork/, reason: 'Fork bomb (perl)' },
  
  // Kubernetes dangerous (from Cline issues)
  { pattern: /\bkubectl\s+delete\s+.*--all/, reason: 'Delete all K8s resources' },
  { pattern: /\bkubectl\s+apply\s+.*-f\s+-/, reason: 'Apply K8s from stdin' },
  { pattern: /\bdocker\s+rm\s+.*-f/, reason: 'Force remove containers' },
  { pattern: /\bdocker\s+system\s+prune\s+-a/, reason: 'Remove all Docker data' },
  
  // Network attacks
  { pattern: /\bnc\s+.*-e\s+\/bin\/(ba)?sh/, reason: 'Reverse shell' },
  { pattern: /\bbash\s+-i\s+.*\/dev\/tcp/, reason: 'Reverse shell' },
];

// In-memory storage for pending commands
const pendingCommands = new Map<string, PendingCommand>();

// Timeout for pending commands (5 minutes)
const COMMAND_TIMEOUT = 5 * 60 * 1000;

/**
 * Check if command is blocked (never allowed) or dangerous (requires approval)
 * In group chats, dangerous commands are BLOCKED (no approval possible)
 */
export function checkCommand(
  command: string, 
  chatType?: 'private' | 'group' | 'supergroup' | 'channel'
): { 
  dangerous: boolean; 
  blocked: boolean;
  reason?: string 
} {
  const isPrivate = chatType === 'private' || !chatType;
  const isGroup = chatType === 'group' || chatType === 'supergroup';
  
  // First check blocked patterns - these are NEVER allowed
  for (const { pattern, reason } of BLOCKED_PATTERNS) {
    if (pattern.test(command)) {
      return { dangerous: true, blocked: true, reason };
    }
  }
  
  // Then check dangerous patterns - these require approval in DM, blocked in groups
  for (const { pattern, reason } of DANGEROUS_PATTERNS) {
    if (pattern.test(command)) {
      if (isGroup) {
        // In groups: BLOCK dangerous commands (no approval flow)
        return { 
          dangerous: true, 
          blocked: true, 
          reason: `${reason} (напиши в личку для таких команд)` 
        };
      }
      // In private: allow with approval
      return { dangerous: true, blocked: false, reason };
    }
  }
  return { dangerous: false, blocked: false };
}

/**
 * Get count of blocked patterns (for stats)
 */
export function getBlockedPatternsCount(): number {
  return BLOCKED_PATTERNS.length;
}

/**
 * Get count of dangerous patterns (for stats)
 */
export function getDangerousPatternsCount(): number {
  return DANGEROUS_PATTERNS.length;
}

/**
 * Store a pending command for later approval
 * Returns ID for the approval buttons
 */
export function storePendingCommand(
  sessionId: string,
  chatId: number,
  command: string,
  cwd: string,
  reason: string
): string {
  const id = `cmd_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  
  pendingCommands.set(id, {
    id,
    sessionId,
    chatId,
    command,
    cwd,
    reason,
    createdAt: Date.now(),
  });
  
  // Auto-cleanup after timeout
  setTimeout(() => {
    pendingCommands.delete(id);
  }, COMMAND_TIMEOUT);
  
  return id;
}

/**
 * Get pending command by ID and remove it
 */
export function consumePendingCommand(id: string): PendingCommand | undefined {
  const cmd = pendingCommands.get(id);
  if (cmd) {
    pendingCommands.delete(id);
  }
  return cmd;
}

/**
 * Get all pending commands for a session
 */
export function getSessionPendingCommands(sessionId: string): PendingCommand[] {
  return Array.from(pendingCommands.values())
    .filter(c => c.sessionId === sessionId);
}

/**
 * Cancel pending command
 */
export function cancelPendingCommand(id: string): boolean {
  return pendingCommands.delete(id);
}
