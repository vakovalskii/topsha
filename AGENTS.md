# LocalTopSH Agent Guide

## Overview

Telegram бот с ReAct агентом, который даёт пользователям доступ к изолированному Linux окружению.

**Battle-tested:** 1500+ хакеров, 7 часов стресс-теста, 0 утечек, 0 даунтайма.

## Security Model

### Five Layers of Protection

| Layer | Component | Function | Details |
|-------|-----------|----------|---------|
| **ACCESS** | DM Policy | Who can use | admin/allowlist/pairing/public |
| **INPUT** | Validators | What they send | 247 + 19 patterns |
| **SANDBOX** | Docker | Isolation | 512MB, 50% CPU, 100 PIDs |
| **SECRETS** | Proxy | Key protection | 0 secrets in agent |
| **OUTPUT** | Sanitizer | What goes out | base64/hex detection |

### Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Gateway   │────▶│    Proxy    │────▶│  External   │
│  (Bot+Agent)│     │ (API Keys)  │     │    APIs     │
│  0 secrets  │     │             │     │             │
└─────────────┘     └─────────────┘     └─────────────┘
       │
       ▼
┌─────────────┐
│  /workspace │
│  per-user   │
│  isolated   │
└─────────────┘
```

## Evolution Cycle

When monitoring and patching the system:

```
┌─────────────────────────────────────────────────────────────────┐
│                    EVOLUTION CYCLE                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. OBSERVE                                                     │
│     └─ docker logs gateway -f | grep SECURITY                  │
│     └─ Check CHAT_HISTORY.md for suspicious patterns           │
│                                                                 │
│  2. ANALYZE                                                     │
│     └─ Identify attack vector                                  │
│     └─ Understand bypass technique                             │
│                                                                 │
│  3. PATCH                                                       │
│     └─ Add pattern to blocked-patterns.json                    │
│     └─ Or update prompt-injection-patterns.json                │
│     └─ Or modify system prompt                                 │
│                                                                 │
│  4. DEPLOY                                                      │
│     └─ docker compose up -d --build                            │
│                                                                 │
│  5. VERIFY                                                      │
│     └─ python scripts/doctor.py                                │
│     └─ Test that attack is blocked                             │
│     └─ Test that legitimate commands work                      │
│                                                                 │
│  6. REPEAT                                                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Key Files for Patching

| File | What to patch |
|------|---------------|
| `core/src/approvals/blocked-patterns.json` | 247 security patterns |
| `bot/prompt-injection-patterns.json` | 19 injection patterns |
| `core/tools/permissions.py` | Tool allowlist/denylist |
| `bot/access.py` | DM Policy (pairing/allowlist) |
| `core/src/agent/system.txt` | System prompt |
| `scripts/doctor.py` | Security audit CLI |

## Access Control Commands

```bash
# Show access status (admin only)
/access

# Change mode
/access_mode admin      # Only admin
/access_mode allowlist  # Admin + allowed users
/access_mode pairing    # Pairing codes for approval
/access_mode public     # Anyone (⚠️ risky)

# Approve pairing code
/approve ABC123

# Revoke user
/revoke 123456789

# Add to allowlist
/allow 123456789
```

## Security Audit

```bash
# Run security doctor
python scripts/doctor.py

# Output as JSON
python scripts/doctor.py --json

# Checks performed:
# - Secrets configuration
# - Docker compose security
# - Blocked patterns (247)
# - Injection patterns (19)
# - Network exposure
# - File permissions
# - Access mode
# - Resource limits
```

## Tool Permissions by Session Type

| Session | Available Tools | Denied Tools |
|---------|----------------|--------------|
| **Main (DM)** | All 17 | - |
| **Group** | 14 | send_dm, manage_message, schedule_task |
| **Sandbox** | 10 | telegram tools, scheduler |
| **Userbot** | 13 | send_file, send_dm, manage_message, ask_user |

## Monitoring Commands

```bash
# Security audit
python scripts/doctor.py

# Real-time logs
docker logs gateway -f --tail 100

# Check containers are running
docker ps

# Restart after patch
docker compose down && docker compose up -d --build

# View chat history
cat workspace/_shared/CHAT_HISTORY.md | tail -100

# View pairing codes (admin)
cat workspace/_shared/pairing.json
```

## Troubleshooting

### Bot not responding / No requests to model API

Access is checked in two places: in the **bot** (who can send messages) and in **core** (who gets agent/LLM). If core denies access, the bot gets `access_denied`, shows a block reaction, and the request never reaches the proxy/LLM.

1. Set your Telegram user ID as admin: in `.env` or docker-compose set `ADMIN_USER_ID=<your_telegram_id>`. Get your ID from @userinfobot or from bot logs when you send a message.
2. For "anyone can use" set `ACCESS_MODE=public` (default in docker-compose). Core then uses the same env for its default config (no admin_config.json).
3. If you use Admin panel (port 3002): Config / Access - set Mode to "Public" or add your user_id to allowlist; ensure "Bot enabled" is on.
4. Check core logs: `docker logs core --tail 50`. Look for "Access denied for &lt;user_id&gt;" - if present, adjust admin_id or mode as above.
5. If you already have `workspace/_shared/admin_config.json`, either remove it so env defaults apply after restart, or set Access mode and admin in Admin panel (Config / Access).

### Server Down

1. `docker ps` - all containers should be Up
2. `docker logs gateway` - check errors
3. `python scripts/doctor.py` - security audit
4. If OOM - increase memory limit in docker-compose.yml
5. If rate limit - increase intervals in `src/config.ts`

### Attack Detected

1. Check logs for `[SECURITY]` or `[BLOCKED]` tags
2. Identify the attack pattern
3. Add to blocked-patterns.json or prompt-injection-patterns.json
4. Rebuild and deploy
5. Verify with doctor.py

## Centralized Config

All settings in `src/config.ts`:
- Rate limits, timeouts, agent behavior
- Reactions, thoughts, messages
- Storage limits (chat history, memory)
- Admin ID, valid emojis

## Comparison with Similar Projects

| Feature | LocalTopSH | OpenClaw |
|---------|------------|----------|
| DM Policy | ✅ admin/allowlist/public/pairing | ✅ pairing/allowlist/open |
| Sandbox | ✅ Docker per-user | ✅ Docker per-session |
| Blocked Patterns | 247 | ~200 |
| Prompt Injection | 19 patterns | ~20 patterns |
| Tool Permissions | ✅ by session type | ✅ similar |
| Security Audit CLI | ✅ `python scripts/doctor.py` | ✅ `openclaw doctor` |
| Multi-channel | Telegram only | 12+ channels |
| Admin Panel | ✅ React :3000 | ✅ Control UI |
| **Philosophy** | Own API keys | Subscription abuse |