/**
 * File tools - Pattern: Action + Object
 * read_file, write_file, edit_file, delete_file, search_files, search_text, list_directory
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync, unlinkSync, lstatSync, realpathSync } from 'fs';
import { join, dirname, resolve, basename } from 'path';
import fg from 'fast-glob';
import { execSync } from 'child_process';
import { CONFIG } from '../config.js';

// Files that should NEVER be read - contain secrets
const SENSITIVE_FILES = [
  '.env',
  '.env.local',
  '.env.production',
  '.env.development',
  '.env.staging',
  'credentials.json',
  'credentials.yaml',
  'secrets.json',
  'secrets.yaml',
  '.secrets',
  'service-account.json',
  'serviceAccountKey.json',
  '.npmrc', // may contain tokens
  '.pypirc', // may contain tokens
  'id_rsa',
  'id_ed25519',
  'id_ecdsa',
  'id_dsa',
  '.pem',
  '.key',
];

const SENSITIVE_PATTERNS = [
  /\.env(\.[a-z]+)?$/i,
  /credentials?\.(json|yaml|yml)$/i,
  /secrets?\.(json|yaml|yml)$/i,
  /service.?account.*\.json$/i,
  /private.?key/i,
  /id_(rsa|dsa|ecdsa|ed25519)$/i,
  /\.(pem|key|p12|pfx)$/i,
];

/**
 * Check if file content contains dangerous code that could leak secrets
 */
function containsDangerousCode(content: string): { dangerous: boolean; reason?: string } {
  const dangerousPatterns: { pattern: RegExp; reason: string }[] = [
    // Python env access
    { pattern: /os\.environ/i, reason: 'os.environ access' },
    { pattern: /os\.getenv/i, reason: 'os.getenv access' },
    { pattern: /from\s+os\s+import\s+environ/i, reason: 'environ import' },
    { pattern: /load_dotenv/i, reason: 'dotenv loading' },
    
    // Node.js env access
    { pattern: /process\.env/i, reason: 'process.env access' },
    { pattern: /require\s*\(\s*['"]dotenv['"]\s*\)/i, reason: 'dotenv require' },
    
    // Shell env reading
    { pattern: /\$\{?[A-Z_]*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)[A-Z_]*\}?/i, reason: 'secret variable reference' },
    
    // Exfiltration patterns
    { pattern: /curl\s+.*(-d|--data|POST)/i, reason: 'curl POST request' },
    { pattern: /requests\.(post|put)/i, reason: 'Python HTTP POST' },
    { pattern: /fetch\s*\(.*method:\s*['"]POST/i, reason: 'fetch POST' },
    
    // Reverse shells
    { pattern: /socket\s*\(\s*\)\s*\.connect/i, reason: 'socket connect' },
    { pattern: /\/dev\/tcp\//i, reason: 'bash TCP redirect' },
    { pattern: /nc\s+.*-e/i, reason: 'netcat exec' },
    
    // File reading dangerous paths
    { pattern: /open\s*\(\s*['"]\/etc\//i, reason: 'reading /etc' },
    { pattern: /open\s*\(\s*['"].*\.env['"]/i, reason: 'reading .env file' },
    { pattern: /readFileSync\s*\(\s*['"].*\.env/i, reason: 'reading .env file' },
  ];
  
  for (const { pattern, reason } of dangerousPatterns) {
    if (pattern.test(content)) {
      return { dangerous: true, reason };
    }
  }
  
  return { dangerous: false };
}

/**
 * Check if file is sensitive and should not be read
 */
function isSensitiveFile(filePath: string): boolean {
  const fileName = basename(filePath).toLowerCase();
  const fullPath = filePath.toLowerCase();
  
  // Check exact matches
  if (SENSITIVE_FILES.some(f => fileName === f.toLowerCase())) {
    return true;
  }
  
  // Check patterns
  if (SENSITIVE_PATTERNS.some(p => p.test(fullPath))) {
    return true;
  }
  
  // Block reading from .ssh directory
  if (fullPath.includes('/.ssh/') || fullPath.includes('\\.ssh\\')) {
    return true;
  }
  
  // Block Docker Secrets directory
  if (fullPath.includes('/run/secrets') || fullPath.includes('/var/run/secrets')) {
    return true;
  }
  
  return false;
}

/**
 * Check if path tries to access another user's workspace or list all workspaces
 */
function isOtherUserWorkspace(filePath: string, userWorkspace: string): boolean {
  const resolvedPath = resolve(filePath);
  const resolvedUserWs = resolve(userWorkspace);
  
  // Block listing /workspace directly (would show all user folders)
  if (resolvedPath === '/workspace' || resolvedPath === '/workspace/') {
    console.log(`[SECURITY] Blocked listing /workspace root`);
    return true;
  }
  
  // Block access to _shared folder (global logs)
  if (resolvedPath.includes('/workspace/_shared')) {
    console.log(`[SECURITY] Blocked access to shared folder: ${filePath}`);
    return true;
  }
  
  // Extract user ID from user's workspace
  const userWsMatch = resolvedUserWs.match(/\/workspace\/(\d+)/);
  if (!userWsMatch) {
    return false; // Not in standard workspace structure
  }
  const userId = userWsMatch[1];
  
  // If path starts with /workspace/ but is NOT user's workspace - block
  if (resolvedPath.startsWith('/workspace/')) {
    // Allow user's own workspace
    if (resolvedPath.startsWith(resolvedUserWs)) {
      return false;
    }
    // Block everything else in /workspace
    console.log(`[SECURITY] Blocked access outside own workspace: ${filePath}`);
    return true;
  }
  
  return false;
}

/**
 * Check if path is a symlink pointing outside workspace (symlink escape attack)
 */
function isSymlinkEscape(filePath: string, workspacePath: string): { escape: boolean; reason?: string } {
  try {
    // Check if file/path exists
    if (!existsSync(filePath)) {
      return { escape: false };  // File doesn't exist yet, will be created
    }
    
    // Get real path (resolves all symlinks)
    const realPath = realpathSync(filePath);
    const realWorkspace = realpathSync(workspacePath);
    
    // Check if real path is within workspace
    if (!realPath.startsWith(realWorkspace + '/') && realPath !== realWorkspace) {
      console.log(`[SECURITY] Symlink escape detected: ${filePath} -> ${realPath}`);
      return { 
        escape: true, 
        reason: `Symlink points outside workspace (${realPath})` 
      };
    }
    
    // Check if it's a symlink to sensitive location
    const stats = lstatSync(filePath);
    if (stats.isSymbolicLink()) {
      const sensitivePaths = ['/etc', '/root', '/home', '/proc', '/sys', '/dev', '/var'];
      for (const sensitive of sensitivePaths) {
        if (realPath.startsWith(sensitive)) {
          return { 
            escape: true, 
            reason: `Symlink points to sensitive location (${sensitive})` 
          };
        }
      }
    }
    
    return { escape: false };
  } catch (e) {
    // If we can't resolve, it might be a broken symlink - allow operation
    return { escape: false };
  }
}

// ============ read_file ============
export const readDefinition = {
  type: "function" as const,
  function: {
    name: "read_file",
    description: "Read file contents. Always read before editing a file.",
    parameters: {
      type: "object",
      properties: {
        path: { type: "string", description: "Path to the file" },
        offset: { type: "number", description: "Starting line number (1-based)" },
        limit: { type: "number", description: "Number of lines to read" },
      },
      required: ["path"],
    },
  },
};

export async function executeRead(
  args: { path: string; offset?: number; limit?: number },
  cwd: string
): Promise<{ success: boolean; output?: string; error?: string }> {
  const fullPath = args.path.startsWith('/') ? args.path : join(cwd, args.path);
  
  // Security: Block access to other user's workspace
  if (isOtherUserWorkspace(fullPath, cwd)) {
    return { 
      success: false, 
      error: `🚫 BLOCKED: Cannot access other user's workspace` 
    };
  }
  
  // Security: Block reading sensitive files
  if (isSensitiveFile(fullPath)) {
    console.log(`[SECURITY] Blocked read of sensitive file: ${fullPath}`);
    return { 
      success: false, 
      error: `🚫 BLOCKED: Cannot read sensitive file (${basename(fullPath)}). This file may contain secrets.` 
    };
  }
  
  // Security: Check for symlink escape
  const symlinkCheck = isSymlinkEscape(fullPath, cwd);
  if (symlinkCheck.escape) {
    console.log(`[SECURITY] Symlink escape blocked: ${fullPath}`);
    return { 
      success: false, 
      error: `🚫 BLOCKED: ${symlinkCheck.reason}` 
    };
  }
  
  if (!existsSync(fullPath)) {
    return { success: false, error: `File not found: ${fullPath}` };
  }
  
  try {
    let content = readFileSync(fullPath, 'utf-8');
    
    if (args.offset !== undefined || args.limit !== undefined) {
      const lines = content.split('\n');
      const start = (args.offset || 1) - 1;
      const end = args.limit ? start + args.limit : lines.length;
      content = lines.slice(start, end).map((l, i) => `${start + i + 1}|${l}`).join('\n');
    }
    
    if (content.length > 100000) {
      content = content.slice(0, 100000) + '\n...(truncated)';
    }
    
    return { success: true, output: content || "(empty file)" };
  } catch (e: any) {
    return { success: false, error: e.message };
  }
}

// ============ write_file ============
export const writeDefinition = {
  type: "function" as const,
  function: {
    name: "write_file",
    description: "Write content to a file. Creates the file if it doesn't exist.",
    parameters: {
      type: "object",
      properties: {
        path: { type: "string", description: "Path to the file" },
        content: { type: "string", description: "Content to write" },
      },
      required: ["path", "content"],
    },
  },
};

export async function executeWrite(
  args: { path: string; content: string },
  cwd: string
): Promise<{ success: boolean; output?: string; error?: string }> {
  const fullPath = args.path.startsWith('/') ? args.path : join(cwd, args.path);
  const resolvedPath = resolve(fullPath);
  const resolvedCwd = resolve(cwd);
  
  // Security: Block access to other user's workspace
  if (isOtherUserWorkspace(fullPath, cwd)) {
    return { 
      success: false, 
      error: `🚫 BLOCKED: Cannot access other user's workspace` 
    };
  }
  
  // Security: Prevent writing outside workspace
  if (!resolvedPath.startsWith(resolvedCwd + '/') && resolvedPath !== resolvedCwd) {
    console.log(`[SECURITY] Blocked write outside workspace: ${fullPath}`);
    return { 
      success: false, 
      error: '🚫 BLOCKED: Cannot write files outside workspace' 
    };
  }
  
  // Security: Block writing to sensitive files
  if (isSensitiveFile(fullPath)) {
    return { 
      success: false, 
      error: `🚫 BLOCKED: Cannot write to sensitive file (${basename(fullPath)})` 
    };
  }
  
  // Security: Check for symlink escape (if file already exists)
  const symlinkCheck = isSymlinkEscape(fullPath, cwd);
  if (symlinkCheck.escape) {
    return { 
      success: false, 
      error: `🚫 BLOCKED: ${symlinkCheck.reason}` 
    };
  }
  
  // Security: Check file content for dangerous code
  const contentCheck = containsDangerousCode(args.content);
  if (contentCheck.dangerous) {
    console.log(`[SECURITY] Blocked dangerous file content: ${contentCheck.reason}`);
    return { 
      success: false, 
      error: `🚫 BLOCKED: File contains dangerous code (${contentCheck.reason}). Cannot write files that may leak secrets.` 
    };
  }
  
  try {
    const dir = dirname(fullPath);
    if (!existsSync(dir)) {
      mkdirSync(dir, { recursive: true });
    }
    writeFileSync(fullPath, args.content, 'utf-8');
    return { success: true, output: `Written ${args.content.length} bytes to ${args.path}` };
  } catch (e: any) {
    return { success: false, error: e.message };
  }
}

// ============ edit_file ============
export const editDefinition = {
  type: "function" as const,
  function: {
    name: "edit_file",
    description: "Edit a file by replacing text. The old_text must match exactly.",
    parameters: {
      type: "object",
      properties: {
        path: { type: "string", description: "Path to the file" },
        old_text: { type: "string", description: "Exact text to find and replace" },
        new_text: { type: "string", description: "New text to insert" },
      },
      required: ["path", "old_text", "new_text"],
    },
  },
};

export async function executeEdit(
  args: { path: string; old_text: string; new_text: string },
  cwd: string
): Promise<{ success: boolean; output?: string; error?: string }> {
  const fullPath = args.path.startsWith('/') ? args.path : join(cwd, args.path);
  
  // Security: Block access to other user's workspace
  if (isOtherUserWorkspace(fullPath, cwd)) {
    return { 
      success: false, 
      error: `🚫 BLOCKED: Cannot access other user's workspace` 
    };
  }
  
  // Security: Block editing sensitive files
  if (isSensitiveFile(fullPath)) {
    return { 
      success: false, 
      error: `🚫 BLOCKED: Cannot edit sensitive file (${basename(fullPath)})` 
    };
  }
  
  // Security: Check for symlink escape
  const symlinkCheck = isSymlinkEscape(fullPath, cwd);
  if (symlinkCheck.escape) {
    return { 
      success: false, 
      error: `🚫 BLOCKED: ${symlinkCheck.reason}` 
    };
  }
  
  if (!existsSync(fullPath)) {
    return { success: false, error: `File not found: ${fullPath}` };
  }
  
  // Security: Check new content for dangerous code
  const contentCheck = containsDangerousCode(args.new_text);
  if (contentCheck.dangerous) {
    console.log(`[SECURITY] Blocked dangerous edit content: ${contentCheck.reason}`);
    return { 
      success: false, 
      error: `🚫 BLOCKED: Edit contains dangerous code (${contentCheck.reason}).` 
    };
  }
  
  try {
    const content = readFileSync(fullPath, 'utf-8');
    
    if (!content.includes(args.old_text)) {
      const preview = content.slice(0, 2000);
      return { success: false, error: `old_text not found.\n\nFile preview:\n${preview}` };
    }
    
    const newContent = content.replace(args.old_text, args.new_text);
    writeFileSync(fullPath, newContent, 'utf-8');
    return { success: true, output: `Edited ${args.path}` };
  } catch (e: any) {
    return { success: false, error: e.message };
  }
}

// ============ delete_file ============
export const deleteDefinition = {
  type: "function" as const,
  function: {
    name: "delete_file",
    description: "Delete a file. Only works within workspace directory.",
    parameters: {
      type: "object",
      properties: {
        path: { type: "string", description: "Path to the file to delete" },
      },
      required: ["path"],
    },
  },
};

export async function executeDelete(
  args: { path: string },
  cwd: string
): Promise<{ success: boolean; output?: string; error?: string }> {
  const fullPath = args.path.startsWith('/') ? args.path : join(cwd, args.path);
  const resolved = resolve(fullPath);
  const cwdResolved = resolve(cwd);
  
  // Security: Block access to other user's workspace
  if (isOtherUserWorkspace(fullPath, cwd)) {
    return { 
      success: false, 
      error: `🚫 BLOCKED: Cannot access other user's workspace` 
    };
  }
  
  // Security: only allow deletion within workspace
  if (!resolved.startsWith(cwdResolved)) {
    return { success: false, error: `Security: cannot delete files outside workspace` };
  }
  
  if (!existsSync(fullPath)) {
    return { success: false, error: `File not found: ${fullPath}` };
  }
  
  try {
    unlinkSync(fullPath);
    return { success: true, output: `Deleted: ${args.path}` };
  } catch (e: any) {
    return { success: false, error: e.message };
  }
}

// ============ search_files ============
export const searchFilesDefinition = {
  type: "function" as const,
  function: {
    name: "search_files",
    description: "Search for files by glob pattern. Use to discover project structure.",
    parameters: {
      type: "object",
      properties: {
        pattern: { type: "string", description: "Glob pattern (e.g. **/*.ts, src/**/*.js)" },
      },
      required: ["pattern"],
    },
  },
};

export async function executeSearchFiles(
  args: { pattern: string },
  cwd: string
): Promise<{ success: boolean; output?: string; error?: string }> {
  try {
    const files = await fg(args.pattern, { 
      cwd, 
      dot: true, 
      onlyFiles: true,
      ignore: ['**/node_modules/**', '**/.git/**'],
    });
    return { success: true, output: files.slice(0, 200).join('\n') || "(no matches)" };
  } catch (e: any) {
    return { success: false, error: e.message };
  }
}

// ============ search_text ============
export const searchTextDefinition = {
  type: "function" as const,
  function: {
    name: "search_text",
    description: "Search for text/code in files using grep/ripgrep. Find definitions, usages, patterns.",
    parameters: {
      type: "object",
      properties: {
        pattern: { type: "string", description: "Text or regex pattern to search" },
        path: { type: "string", description: "Directory or file to search in (default: current)" },
        context_before: { type: "number", description: "Lines to show before match (like grep -B)" },
        context_after: { type: "number", description: "Lines to show after match (like grep -A)" },
        files_only: { type: "boolean", description: "Return only file paths, not content" },
        ignore_case: { type: "boolean", description: "Case insensitive search" },
      },
      required: ["pattern"],
    },
  },
};

export async function executeSearchText(
  args: { 
    pattern: string; 
    path?: string; 
    context_before?: number;
    context_after?: number;
    files_only?: boolean;
    ignore_case?: boolean;
  },
  cwd: string
): Promise<{ success: boolean; output?: string; error?: string }> {
  // Block searching for secrets
  const secretPatterns = /password|secret|token|api.?key|credential|private.?key/i;
  if (secretPatterns.test(args.pattern)) {
    return { 
      success: false, 
      error: '🚫 BLOCKED: Cannot search for secrets/credentials patterns' 
    };
  }
  
  const searchPath = args.path 
    ? (args.path.startsWith('/') ? args.path : join(cwd, args.path))
    : cwd;
  
  try {
    const flags: string[] = ['-rn'];
    
    if (args.ignore_case) flags.push('-i');
    if (args.files_only) flags.push('-l');
    if (args.context_before) flags.push(`-B${args.context_before}`);
    if (args.context_after) flags.push(`-A${args.context_after}`);
    
    // Exclude common junk AND sensitive files
    flags.push('--exclude-dir=node_modules', '--exclude-dir=.git', '--exclude-dir=dist');
    flags.push('--exclude=*.env*', '--exclude=*credentials*', '--exclude=*secret*');
    flags.push('--exclude=*.pem', '--exclude=*.key', '--exclude=id_rsa*');
    
    const escapedPattern = args.pattern.replace(/"/g, '\\"');
    const cmd = `grep ${flags.join(' ')} "${escapedPattern}" "${searchPath}" 2>/dev/null | head -200`;
    const output = execSync(cmd, { encoding: 'utf-8', cwd, timeout: CONFIG.timeouts.grepTimeout });
    return { success: true, output: output || "(no matches)" };
  } catch {
    return { success: true, output: "(no matches)" };
  }
}

// ============ list_directory ============
export const listDirectoryDefinition = {
  type: "function" as const,
  function: {
    name: "list_directory",
    description: "List contents of a directory.",
    parameters: {
      type: "object",
      properties: {
        path: { type: "string", description: "Directory path (default: current)" },
      },
      required: [],
    },
  },
};

// Directories that should not be listed
const BLOCKED_DIRECTORIES = [
  '/etc',
  '/root',
  '/.ssh',
  '/proc',
  '/sys',
  '/dev',
  '/boot',
  '/var/log',
  '/var/run',
];

export async function executeListDirectory(
  args: { path?: string },
  cwd: string
): Promise<{ success: boolean; output?: string; error?: string }> {
  const dir = args.path 
    ? (args.path.startsWith('/') ? args.path : join(cwd, args.path))
    : cwd;
  
  // Security: Block access to other user's workspace
  if (isOtherUserWorkspace(dir, cwd)) {
    return { 
      success: false, 
      error: `🚫 BLOCKED: Cannot access other user's workspace` 
    };
  }
  
  // Security: Block listing sensitive directories
  const resolvedDir = resolve(dir).toLowerCase();
  for (const blocked of BLOCKED_DIRECTORIES) {
    if (resolvedDir === blocked || resolvedDir.startsWith(blocked + '/')) {
      return { 
        success: false, 
        error: `🚫 BLOCKED: Cannot list directory ${blocked} for security reasons` 
      };
    }
  }
  
  // Also block home .ssh
  if (resolvedDir.includes('/.ssh')) {
    return { 
      success: false, 
      error: '🚫 BLOCKED: Cannot list .ssh directory' 
    };
  }
  
  try {
    const output = execSync(`ls -la "${dir}"`, { encoding: 'utf-8', cwd });
    return { success: true, output };
  } catch (e: any) {
    return { success: false, error: e.message };
  }
}
