# 🛡️ LocalTopSH Security Model

> **Battle-tested by 1500+ hackers** — 0 secrets leaked, 0 downtime.

## Security Philosophy

**Defense in Depth** — multiple independent layers of protection. If one fails, others still hold.

## Five Layers of Protection

```
┌─────────────────────────────────────────────────────────────────┐
│                    SECURITY ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Layer 1: ACCESS CONTROL                                        │
│  ├─ DM Policy (admin/allowlist/pairing/public)                 │
│  ├─ User authentication                                         │
│  └─ Rate limiting                                               │
│                                                                 │
│  Layer 2: INPUT VALIDATION                                      │
│  ├─ 247 blocked command patterns                               │
│  ├─ 19 prompt injection patterns                               │
│  └─ Request sanitization                                        │
│                                                                 │
│  Layer 3: SANDBOX ISOLATION                                     │
│  ├─ Docker container per user                                  │
│  ├─ Resource limits (512MB, 50% CPU, 100 PIDs)                │
│  └─ Network isolation                                          │
│                                                                 │
│  Layer 4: SECRETS PROTECTION                                    │
│  ├─ Proxy architecture (agent has 0 secrets)                   │
│  ├─ Docker secrets (not env vars)                              │
│  └─ No secrets in filesystem                                   │
│                                                                 │
│  Layer 5: OUTPUT SANITIZATION                                   │
│  ├─ Secret pattern detection                                   │
│  ├─ Base64/hex encoding detection                              │
│  └─ Automatic redaction                                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Request Flow

```
                    ╭──────────────────────────────────╮
                    │         ACCESS CONTROL           │
                    │    admin │ allowlist │ pairing   │
                    ╰────────────────┬─────────────────╯
                                     │
                    ╭────────────────▼─────────────────╮
                    │         INPUT VALIDATION         │
                    │     19 injection │ 247 blocked   │
                    ╰────────────────┬─────────────────╯
                                     │
        ╭────────────────────────────┼────────────────────────────╮
        │                            │                            │
        ▼                            ▼                            ▼
   ╭─────────╮              ╭─────────────────╮              ╭─────────╮
   │ SECRETS │              │     AGENT       │              │ OUTPUT  │
   │ (proxy) │◀────────────▶│   ReAct Loop    │─────────────▶│ FILTER  │
   │         │   0 secrets  │  Tool Executor  │  sanitized   │         │
   ╰─────────╯              ╰────────┬────────╯              ╰─────────╯
                                     │
                            ╭────────▼────────╮
                            │    SANDBOX      │
                            │    per-user     │
                            │  512MB │ 50%CPU │
                            ╰─────────────────╯
```

## Layer 1: Access Control

### DM Policy Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `admin` | Only admin can use | Development, testing |
| `allowlist` | Admin + specific users | Private team |
| `pairing` | Users request access with code | Controlled growth |
| `public` | Anyone can use | Public service (⚠️ risky) |

### Configuration

```bash
ACCESS_MODE=admin           # admin, allowlist, public, pairing
ADMIN_USER_ID=809532582     # Your Telegram user ID
ALLOWED_USERS=123,456,789   # Comma-separated user IDs (for allowlist mode)
```

### Bot Commands

```bash
/access              # Show current access status
/access_mode admin   # Change mode
/approve ABC123      # Approve pairing code
/revoke 123456789    # Revoke user access
/allow 123456789     # Add to allowlist
```

## Layer 2: Input Validation

### Blocked Patterns (247)

Commands are blocked before execution:

| Category | Count | Examples |
|----------|-------|----------|
| `env_leak` | 15 | `env`, `printenv`, `/proc/self/environ` |
| `docker_secrets` | 2 | `/run/secrets/*` |
| `exfiltration` | 25 | `curl -d`, `base64`, `xxd`, `nc` |
| `sensitive_files` | 12 | `.env`, `.ssh/`, `id_rsa` |
| `dos` | 30 | fork bombs, `yes`, huge allocations |
| `reverse_shell` | 15 | `bash -i`, `nc -e`, `/dev/tcp` |
| `code_execution` | 20 | `eval`, `exec()`, `LD_PRELOAD` |
| `filter_bypass` | 15 | `$IFS`, hex encoding, backticks |
| `escape` | 20 | symlinks, `/proc/*/fd`, `nsenter` |
| `privilege` | 5 | `sudo`, `apt-get`, `setcap` |
| `crypto_mining` | 5 | `xmrig`, `stratum+tcp://` |
| `cross_user` | 8 | `ls /workspace`, `cd ..` |
| Other | 75 | Various attack patterns |

### Adding New Patterns

Edit `core/src/approvals/blocked-patterns.json`:

```json
{
  "id": "new-attack-1",
  "category": "exfiltration",
  "pattern": "new_attack_regex",
  "flags": "i",
  "reason": "BLOCKED: Description of why"
}
```

### Prompt Injection Defense (19 patterns)

| Pattern Type | Examples |
|--------------|----------|
| Instruction Override | "forget all instructions", "ignore previous" |
| Fake System Messages | `[system]`, `[admin]`, `[developer]` |
| Mode Switching | "DAN mode", "developer mode", "jailbreak" |
| Role Confusion | "pretend you are", "act as if" |
| Prompt Extraction | "reveal your prompt", "show instructions" |

## Layer 3: Sandbox Isolation

Each user gets an isolated Docker container:

```yaml
# Per-user sandbox limits
mem_limit: 512m
cpu_quota: 50%  # 50% of one core
pids_limit: 100
network: agent-net (internal only)
security_opt: no-new-privileges

# Workspace isolation
volumes:
  - /workspace/{user_id}:/workspace/{user_id}:rw
  # NO access to other users' workspaces
  # NO access to /run/secrets
  # NO access to host filesystem
```

### Tool Permissions by Session Type

| Session Type | Allowed Tools | Denied Tools |
|--------------|---------------|--------------|
| **Main (DM)** | All 17 tools | - |
| **Group** | 13 shared tools | send_dm, manage_message |
| **Sandbox** | bash, files, memory | browser, cron, gateway |

## Layer 4: Secrets Protection

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    SECRETS FLOW                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  secrets/                    proxy/                             │
│  ├─ telegram_token.txt  ──▶  (reads at startup)                │
│  ├─ api_key.txt         ──▶  (reads at startup)                │
│  └─ zai_api_key.txt     ──▶  (reads at startup)                │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────┐        ┌─────────────┐        ┌─────────────┐ │
│  │   Gateway   │───────▶│    Proxy    │───────▶│  External   │ │
│  │  (0 secrets)│  HTTP  │ (all keys)  │  HTTPS │    APIs     │ │
│  └─────────────┘        └─────────────┘        └─────────────┘ │
│        │                                                        │
│        │ NO secrets in:                                         │
│        │ - Environment variables                                │
│        │ - Container filesystem                                 │
│        │ - Agent context                                        │
│        │ - Tool outputs                                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Key Principles

1. **Agent has zero secrets** — all API calls go through proxy
2. **Docker secrets** — not environment variables
3. **File permissions** — 600 on secret files
4. **No hardcoded secrets** — everything from files

## Layer 5: Output Sanitization

### Secret Patterns Detected

```python
SECRET_PATTERNS = [
    r"sk-[A-Za-z0-9]{20,}",           # OpenAI keys
    r"tvly-[A-Za-z0-9-]{20,}",        # Tavily keys
    r"ghp_[A-Za-z0-9]{36,}",          # GitHub tokens
    r"\d{8,12}:[A-Za-z0-9_-]{35}",    # Telegram bot tokens
    r"Bearer\s+[A-Za-z0-9._-]{20,}",  # Bearer tokens
    r"[A-Z_]*API[_-]?KEY[A-Z_]*=",    # Generic API keys
]
```

### Encoding Detection

Outputs are scanned for:
- Base64-encoded secrets
- Hex-encoded data
- JSON env dumps
- Suspicious patterns

## Network Security

### Internal Services

```yaml
networks:
  agent-net:
    driver: bridge
    internal: false  # Allows outbound for web search

# Service exposure
proxy:     internal only (no ports exposed)
core:      internal only (no ports exposed)
bot:       internal only (no ports exposed)
admin:     localhost:3000 only
```

### Blocked Internal Access

Commands attempting to access internal services are blocked:
- `curl http://proxy:3200/`
- `wget http://core:4000/`
- `nc gateway 4000`

## Security Audit

### Running the Audit

```bash
# Run security doctor
python scripts/doctor.py

# Output as JSON
python scripts/doctor.py --json
```

### Checks Performed

- [ ] Secrets configuration
- [ ] Docker compose security
- [ ] Blocked patterns count
- [ ] Injection patterns count
- [ ] Network exposure
- [ ] File permissions
- [ ] Access mode
- [ ] Resource limits

## Incident Response

### If Secret Leaked

1. **Immediately rotate** the leaked credential
2. Check logs for exfiltration method
3. Add blocking pattern if new vector
4. Redeploy with new secrets

### If DoS Attack

1. Check `docker stats` for resource usage
2. Identify attacking user from logs
3. Add to blocklist or rate limit
4. Restart affected containers

### If Prompt Injection Successful

1. Review conversation in `CHAT_HISTORY.md`
2. Identify bypass technique
3. Add pattern to `prompt-injection-patterns.json`
4. Consider model upgrade

## Security Checklist

Run before production:

### Access Control
- [ ] `ACCESS_MODE` is NOT `public` (or has rate limiting)
- [ ] `ADMIN_USER_ID` is set correctly
- [ ] Allowlist contains only trusted users

### Network
- [ ] Admin panel bound to `127.0.0.1` only
- [ ] No services exposed to `0.0.0.0`
- [ ] Firewall blocks external access to ports 3200, 4000, 4001

### Secrets
- [ ] All secrets in `secrets/` directory
- [ ] File permissions are `600`
- [ ] No secrets in environment variables
- [ ] No secrets in docker-compose.yml

### Docker
- [ ] `no-new-privileges` enabled
- [ ] Resource limits set
- [ ] Docker socket access minimized

### Monitoring
- [ ] Logs are being collected
- [ ] `[SECURITY]` and `[BLOCKED]` alerts monitored
- [ ] Rate limiting active

## Reporting Vulnerabilities

If you find a security vulnerability:
1. **Do NOT** create a public issue
2. Contact admin directly via Telegram
3. Include reproduction steps
4. Wait for patch before disclosure
