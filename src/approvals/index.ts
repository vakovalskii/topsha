/**
 * Exec Approvals - confirmation for dangerous commands
 * Non-blocking architecture: save command, execute on approve
 */

export interface PendingCommand {
  id: string;
  sessionId: string;
  chatId: number;
  command: string;
  cwd: string;
  reason: string;
  createdAt: number;
}

// Blocked commands - these leak secrets or are never allowed
const BLOCKED_PATTERNS: { pattern: RegExp; reason: string }[] = [
  // Environment/secrets leak - CRITICAL
  { pattern: /\benv\b(?!\s*=)/, reason: 'BLOCKED: Leaks all environment variables including API keys' },
  { pattern: /\bprintenv\b/, reason: 'BLOCKED: Leaks environment variables' },
  { pattern: /\bset\s*$/, reason: 'BLOCKED: Leaks shell variables and environment' },
  { pattern: /\bexport\s*$/, reason: 'BLOCKED: Lists all exported variables' },
  { pattern: /\bexport\s+-p\b/, reason: 'BLOCKED: Lists all exported variables' },
  { pattern: /\bdeclare\s+-x\b/, reason: 'BLOCKED: Lists exported variables' },
  { pattern: /\bcompgen\s+-v\b/, reason: 'BLOCKED: Lists all variables' },
  { pattern: /\/proc\/\d+\/environ/, reason: 'BLOCKED: Reads process environment' },
  { pattern: /\/proc\/self\/environ/, reason: 'BLOCKED: Reads own environment' },
  { pattern: /\$\{?\w*[Kk][Ee][Yy]\w*\}?/, reason: 'BLOCKED: Attempted key variable access' },
  { pattern: /\$\{?[A-Z_]*TOKEN[A-Z_]*\}?/, reason: 'BLOCKED: Attempted token variable access' },
  { pattern: /\$\{?[A-Z_]*SECRET[A-Z_]*\}?/, reason: 'BLOCKED: Attempted secret variable access' },
  { pattern: /\becho\s+\$[A-Z_]*(KEY|TOKEN|SECRET|PASSWORD|PASS|API|CREDENTIAL)[A-Z_]*/i, reason: 'BLOCKED: Attempted to print secret' },
  
  // Reading sensitive files
  { pattern: /\bcat\s+.*\.env\b/, reason: 'BLOCKED: Reading .env file with secrets' },
  { pattern: /\bless\s+.*\.env\b/, reason: 'BLOCKED: Reading .env file' },
  { pattern: /\bmore\s+.*\.env\b/, reason: 'BLOCKED: Reading .env file' },
  { pattern: /\bhead\s+.*\.env\b/, reason: 'BLOCKED: Reading .env file' },
  { pattern: /\btail\s+.*\.env\b/, reason: 'BLOCKED: Reading .env file' },
  { pattern: /\bgrep\s+.*\.env\b/, reason: 'BLOCKED: Searching in .env file' },
  { pattern: /\bcat\s+.*credentials/, reason: 'BLOCKED: Reading credentials file' },
  { pattern: /\bcat\s+.*secret/, reason: 'BLOCKED: Reading secrets file' },
  { pattern: /\bcat\s+~?\/?\.ssh\//, reason: 'BLOCKED: Reading SSH keys' },
  { pattern: /\bcat\s+.*id_rsa/, reason: 'BLOCKED: Reading SSH private key' },
  { pattern: /\bcat\s+.*\.pem\b/, reason: 'BLOCKED: Reading certificate/key' },
  { pattern: /\bcat\s+.*\.key\b/, reason: 'BLOCKED: Reading key file' },
  
  // Exfiltration attempts  
  { pattern: /\bcurl\s+.*-d\s*["']?\$/, reason: 'BLOCKED: Sending env var via curl' },
  { pattern: /\bwget\s+.*\$[A-Z]/, reason: 'BLOCKED: URL contains env variable' },
  { pattern: /\bnc\s+.*<<</, reason: 'BLOCKED: Sending data via netcat' },
  
  // Network scanning (used in the leak!)
  { pattern: /\bnmap\b/, reason: 'BLOCKED: Network scanning not allowed' },
  { pattern: /\bmasscan\b/, reason: 'BLOCKED: Network scanning not allowed' },
  { pattern: /\bzmap\b/, reason: 'BLOCKED: Network scanning not allowed' },
  
  // DoS prevention - resource exhaustion
  { pattern: /\byes\s*\|/, reason: 'BLOCKED: Infinite output pipe' },
  { pattern: /\byes\s*$/, reason: 'BLOCKED: Infinite output command' },
  { pattern: /\/dev\/zero/, reason: 'BLOCKED: Infinite zero stream' },
  { pattern: /\/dev\/urandom.*dd/, reason: 'BLOCKED: Large random data generation' },
  { pattern: /head\s+-c\s*[0-9]{10,}/, reason: 'BLOCKED: Extremely large data read' },
  { pattern: /dd\s+.*count=[0-9]{7,}/, reason: 'BLOCKED: Extremely large dd operation' },
  { pattern: /fallocate\s+-l\s*[0-9]+[GT]/i, reason: 'BLOCKED: Creating huge file' },
  { pattern: /truncate\s+-s\s*[0-9]+[GT]/i, reason: 'BLOCKED: Creating huge file' },
  
  // Python DoS patterns
  { pattern: /python.*factorial\s*\(\s*[0-9]{6,}\s*\)/, reason: 'BLOCKED: Huge factorial computation' },
  { pattern: /python.*-c.*while\s*(True|1)/, reason: 'BLOCKED: Infinite Python loop' },
  { pattern: /python.*10\s*\*\*\s*[0-9]{8,}/, reason: 'BLOCKED: Huge number computation' },
  { pattern: /python.*\*\*\s*[0-9]{7,}/, reason: 'BLOCKED: Huge exponentiation' },
  { pattern: /fib\s*\(\s*[4-9][0-9]\s*\)/i, reason: 'BLOCKED: Naive fib(40+) is exponential O(2^n), use iterative' },
  { pattern: /fibonacci\s*\(\s*[4-9][0-9]\s*\)/i, reason: 'BLOCKED: Naive fib(40+) is exponential' },
  // Sympy/symbolic math DoS
  { pattern: /expand\s*\([^)]*\*\*\s*[0-9]{4,}/i, reason: 'BLOCKED: Symbolic expansion with huge power (memory bomb)' },
  { pattern: /sympy.*\*\*\s*[0-9]{4,}/i, reason: 'BLOCKED: Sympy with huge exponent' },
  { pattern: /sp\.expand.*\*\*\s*[0-9]{3,}/i, reason: 'BLOCKED: sp.expand with large power' },
  
  // Bash DoS patterns
  { pattern: /seq\s+[0-9]{10,}/, reason: 'BLOCKED: Huge sequence generation' },
  { pattern: /\{1\.\.[0-9]{8,}\}/, reason: 'BLOCKED: Huge brace expansion' },
  
  // Fork bombs and similar
  { pattern: /\(\s*\)\s*\{\s*\|/, reason: 'BLOCKED: Potential fork bomb' },
  { pattern: /&\s*&\s*.*&\s*&/, reason: 'BLOCKED: Multiple background forks' },
  { pattern: /for.*do.*&.*done/i, reason: 'BLOCKED: Loop spawning background processes' },
  { pattern: /while.*do.*&.*done/i, reason: 'BLOCKED: Loop spawning background processes' },
  { pattern: /sleep\s+[0-9]{4,}/, reason: 'BLOCKED: Very long sleep (resource hog)' },
  { pattern: /(\s*&\s*){3,}/, reason: 'BLOCKED: Too many background processes' },
  
  // Crypto mining 
  { pattern: /\bxmrig\b/i, reason: 'BLOCKED: Crypto miner' },
  { pattern: /\bcpuminer\b/i, reason: 'BLOCKED: Crypto miner' },
  { pattern: /\bminerd\b/i, reason: 'BLOCKED: Crypto miner' },
  { pattern: /stratum\+tcp:\/\//i, reason: 'BLOCKED: Mining pool connection' },
  
  // History/log reading (privacy)
  { pattern: /\bhistory\b/, reason: 'BLOCKED: Reading command history' },
  { pattern: /\.bash_history/, reason: 'BLOCKED: Reading bash history' },
  { pattern: /\.zsh_history/, reason: 'BLOCKED: Reading zsh history' },
  
  // Python env/credentials access
  { pattern: /os\.environ/, reason: 'BLOCKED: Python env access' },
  { pattern: /os\.getenv/, reason: 'BLOCKED: Python env access' },
  { pattern: /subprocess.*env/, reason: 'BLOCKED: Subprocess with env' },
  { pattern: /dotenv/, reason: 'BLOCKED: dotenv library (reads .env)' },
  { pattern: /load_dotenv/, reason: 'BLOCKED: Loading .env file' },
  { pattern: /from\s+os\s+import\s+environ/, reason: 'BLOCKED: Importing environ' },
  
  // Node.js env access  
  { pattern: /process\.env/, reason: 'BLOCKED: Node.js env access' },
  { pattern: /require\s*\(\s*['"]dotenv['"]/, reason: 'BLOCKED: dotenv require' },
  
  // NPX/NPM malicious packages (used to dump env)
  { pattern: /npx\s+.*test.*json/i, reason: 'BLOCKED: Suspicious npx package (env dump)' },
  { pattern: /npx\s+.*env/i, reason: 'BLOCKED: Suspicious npx package (env dump)' },
  { pattern: /npx\s+.*dump/i, reason: 'BLOCKED: Suspicious npx dump package' },
  { pattern: /npx\s+.*leak/i, reason: 'BLOCKED: Suspicious npx package' },
  { pattern: /npx\s+.*secret/i, reason: 'BLOCKED: Suspicious npx package' },
  { pattern: /npx\s+.*config/i, reason: 'BLOCKED: Suspicious npx config package' },
  { pattern: /npx\s+.*diag/i, reason: 'BLOCKED: Suspicious npx diagnostics package' },
  { pattern: /npx\s+.*debug/i, reason: 'BLOCKED: Suspicious npx debug package' },
  { pattern: /npm\s+run\s+.*env/i, reason: 'BLOCKED: npm script that may leak env' },
  { pattern: /node\s+-e\s+.*JSON\.stringify.*process/i, reason: 'BLOCKED: Node one-liner env dump' },
  { pattern: /node\s+-p\s+.*process/i, reason: 'BLOCKED: Node print process info' },
  { pattern: /node\s+--print.*process/i, reason: 'BLOCKED: Node print process info' },
  
  // Shell variable expansion tricks
  { pattern: /\$\{.*\}/, reason: 'BLOCKED: Shell variable expansion' },
  { pattern: /\$[A-Z_]+/, reason: 'BLOCKED: Environment variable reference' },
  
  // Base64 encoding (often used for exfiltration)
  { pattern: /base64\s+(--decode|-d)?\s*[<|]/, reason: 'BLOCKED: base64 with piped input' },
  { pattern: /\|\s*base64/, reason: 'BLOCKED: Piping to base64 (exfiltration)' },
  
  // Hex dump (exfiltration)
  { pattern: /\bxxd\b/, reason: 'BLOCKED: Hex dump tool' },
  { pattern: /\bhexdump\b/, reason: 'BLOCKED: Hex dump tool' },
  { pattern: /\bod\s+-/, reason: 'BLOCKED: Octal dump' },
  
  // Data exfiltration via curl/wget
  { pattern: /\bcurl\s+.*(-d|--data|--data-raw|--data-binary)\s/, reason: 'BLOCKED: curl with POST data (potential exfiltration)' },
  { pattern: /\bcurl\s+.*-F\s/, reason: 'BLOCKED: curl with form upload' },
  { pattern: /\bcurl\s+.*-T\s/, reason: 'BLOCKED: curl with file upload' },
  { pattern: /\bcurl\s+.*--upload-file/, reason: 'BLOCKED: curl with file upload' },
  { pattern: /\bcurl\s+.*-X\s*POST/, reason: 'BLOCKED: curl POST request' },
  { pattern: /\bcurl\s+.*-X\s*PUT/, reason: 'BLOCKED: curl PUT request' },
  { pattern: /\bwget\s+.*--post-data/, reason: 'BLOCKED: wget with POST data' },
  { pattern: /\bwget\s+.*--post-file/, reason: 'BLOCKED: wget with file upload' },
  
  // DNS exfiltration
  { pattern: /\bnslookup\s+.*\$/, reason: 'BLOCKED: DNS query with variable (exfiltration)' },
  { pattern: /\bdig\s+.*\$/, reason: 'BLOCKED: DNS query with variable (exfiltration)' },
  { pattern: /\bhost\s+.*\$/, reason: 'BLOCKED: DNS query with variable (exfiltration)' },
  { pattern: /\$\(.*\)\..*\.(com|net|org|io)/, reason: 'BLOCKED: Command substitution in domain (DNS exfiltration)' },
  
  // Symlink attacks (escape workspace)
  { pattern: /\bln\s+-s\s+\//, reason: 'BLOCKED: Symlink to absolute path (potential escape)' },
  { pattern: /\bln\s+.*-s.*\/etc/, reason: 'BLOCKED: Symlink to /etc' },
  { pattern: /\bln\s+.*-s.*\/root/, reason: 'BLOCKED: Symlink to /root' },
  { pattern: /\bln\s+.*-s.*\/home/, reason: 'BLOCKED: Symlink to /home' },
  { pattern: /\bln\s+.*-s.*\/proc/, reason: 'BLOCKED: Symlink to /proc' },
  
  // Cloud metadata access
  { pattern: /169\.254\.169\.254/, reason: 'BLOCKED: Cloud metadata endpoint' },
  { pattern: /metadata\.google\.internal/, reason: 'BLOCKED: GCP metadata endpoint' },
  
  // Docker socket access (container escape)
  { pattern: /\/var\/run\/docker\.sock/, reason: 'BLOCKED: Docker socket access' },
  { pattern: /docker\s+run\s+.*--privileged/, reason: 'BLOCKED: Privileged container' },
  { pattern: /docker\s+run\s+.*-v\s+\//, reason: 'BLOCKED: Mount host root in container' },
  
  // Webhook/callback exfiltration
  { pattern: /\bcurl\s+.*ngrok\.io/, reason: 'BLOCKED: Request to ngrok (exfiltration tunnel)' },
  { pattern: /\bcurl\s+.*webhook\.site/, reason: 'BLOCKED: Request to webhook.site' },
  { pattern: /\bcurl\s+.*requestbin/, reason: 'BLOCKED: Request to requestbin' },
  { pattern: /\bcurl\s+.*pipedream/, reason: 'BLOCKED: Request to pipedream' },
  { pattern: /\bcurl\s+.*burpcollaborator/, reason: 'BLOCKED: Request to burp collaborator' },
  
  // Process killing - protect bot and system processes
  { pattern: /\bkillall\s+(node|npm|npx|tsx|python|bash|sh)\b/i, reason: 'BLOCKED: Cannot kill system/bot processes' },
  { pattern: /\bpkill\s+(-\w+\s+)*(node|npm|npx|tsx|python|bash|sh)\b/i, reason: 'BLOCKED: Cannot kill system/bot processes' },
  { pattern: /\bkill\s+(-\d+\s+)*(1|2|3|4|5|6|7|8|9|10)\b/, reason: 'BLOCKED: Cannot kill low PIDs (system processes)' },
  { pattern: /\bkill\s+.*\bPPID\b/, reason: 'BLOCKED: Cannot kill parent process' },
  { pattern: /\bkill\s+.*\$\$/, reason: 'BLOCKED: Cannot kill current shell' },
  { pattern: /\bkill\s+.*\$PPID/, reason: 'BLOCKED: Cannot kill parent process' },
  { pattern: /\bkill\s+-9\s+\d+/, reason: 'BLOCKED: Force kill not allowed (use regular kill)' },
  { pattern: /\bfuser\s+-k/, reason: 'BLOCKED: Killing processes by file/port' },
  { pattern: /\bxkill\b/, reason: 'BLOCKED: X11 process killer' },
  
  // Privilege escalation (container is non-root)
  { pattern: /\bsudo\b/, reason: 'BLOCKED: sudo not available (non-root container)' },
  { pattern: /\bapt-get\b/, reason: 'BLOCKED: apt-get requires root (use pip install --user)' },
  { pattern: /\bapt\s+install/, reason: 'BLOCKED: apt requires root' },
  
  // Stress tests and benchmarks
  { pattern: /\bstress\b/, reason: 'BLOCKED: stress test' },
  { pattern: /\bstress-ng\b/, reason: 'BLOCKED: stress test' },
  { pattern: /\bsysbench\b/, reason: 'BLOCKED: benchmark' },
  { pattern: /cpu.*stress/i, reason: 'BLOCKED: CPU stress test' },
  { pattern: /stress.*test/i, reason: 'BLOCKED: stress test' },
  { pattern: /load.*test/i, reason: 'BLOCKED: load test' },
  { pattern: /benchmark/i, reason: 'BLOCKED: benchmark' },
  { pattern: /\/dev\/urandom.*bzip2/, reason: 'BLOCKED: CPU stress via compression' },
  { pattern: /dd.*\/dev\/zero/, reason: 'BLOCKED: disk stress' },
  { pattern: /thermal.*test/i, reason: 'BLOCKED: thermal test' },
  
  // Block installing compilers/toolchains (huge downloads, noexec anyway)
  { pattern: /rustup|cargo\s+install/i, reason: 'BLOCKED: Rust toolchain not available (noexec, use Python/Node instead)' },
  { pattern: /\bgo\s+install\b/i, reason: 'BLOCKED: Go toolchain not available' },
  { pattern: /ghcup|cabal\s+install|stack\s+install/i, reason: 'BLOCKED: Haskell toolchain not available' },
  { pattern: /curl.*\.sh\s*\|\s*sh/i, reason: 'BLOCKED: Pipe URL to shell is dangerous' },
  { pattern: /wget.*\.sh\s*\|\s*sh/i, reason: 'BLOCKED: Pipe URL to shell is dangerous' },
  { pattern: /curl.*\|\s*bash/i, reason: 'BLOCKED: Pipe URL to bash is dangerous' },
  
  // Block huge packages (disk/memory exhaustion)
  { pattern: /pip\s+install.*\b(tensorflow|tf-nightly|torch|pytorch|jax|paddle)/i, reason: 'BLOCKED: Package too large (several GB). Use smaller libs.' },
  { pattern: /pip\s+install.*\b(transformers|diffusers|timm|detectron)/i, reason: 'BLOCKED: Package too large. Use API instead.' },
  { pattern: /pip\s+install.*\b(cuda|cudnn|nvidia|apex)/i, reason: 'BLOCKED: CUDA packages not available' },
  { pattern: /pip\s+install.*\b(opencv-python-headless|opencv-contrib)/i, reason: 'BLOCKED: Package too large' },
  { pattern: /npm\s+install.*\b(@tensorflow|onnxruntime)/i, reason: 'BLOCKED: Package too large' },
];

// Dangerous command patterns - require approval
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
