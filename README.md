# LocalTopSH 🐧

**AI Agent with full system access, sandboxed per user.**

> 🔥 **Battle-tested by 1500+ hackers!**
> 
> Live in [**@neuraldeepchat**](https://t.me/neuraldeepchat) — community stress-tested with **1500+ attack attempts**:
> - Token extraction (env, /proc, base64 exfil, HTTP servers)
> - RAM/CPU exhaustion (zip bombs, infinite loops, fork bombs)
> - Container escape attempts
> 
> **Result: 0 secrets leaked, 0 downtime.**

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         HOST (Docker)                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐      ┌─────────────┐      ┌─────────────┐     │
│  │   Telegram  │      │   Gateway   │      │    Proxy    │     │
│  │   Users     │◄────►│  (bot+LLM)  │─────►│  (secrets)  │     │
│  └─────────────┘      └──────┬──────┘      └─────────────┘     │
│                              │                                  │
│              Docker API      │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Dynamic Sandbox Containers                  │   │
│  ├─────────────┬─────────────┬─────────────┬───────────────┤   │
│  │ sandbox_    │ sandbox_    │ sandbox_    │               │   │
│  │ user_123    │ user_456    │ user_789    │     ...       │   │
│  │ ports:5000  │ ports:5010  │ ports:5020  │               │   │
│  │ ┌─────────┐ │ ┌─────────┐ │ ┌─────────┐ │               │   │
│  │ │workspace│ │ │workspace│ │ │workspace│ │               │   │
│  │ │ /123    │ │ │ /456    │ │ │ /789    │ │               │   │
│  │ └─────────┘ │ └─────────┘ │ └─────────┘ │               │   │
│  └─────────────┴─────────────┴─────────────┴───────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Key Security:**
- Each user runs in **isolated Docker container**
- Container sees only **own workspace** (not others)
- **No access** to `/run/secrets`, `/app`, host filesystem
- Limits: 512MB RAM, 50% CPU, 100 processes
- Auto-cleanup: 60 min inactive → container removed
- Secrets isolated via internal Proxy (agent never sees API keys)

## Features

- **ReAct Agent** with 13 tools (shell, files, web search, scheduler)
- **Per-user Docker sandbox** with resource limits
- **Secrets isolation** via Docker Secrets + internal Proxy
- **Smart reactions** on messages (LLM-powered)
- **Autonomous "thoughts"** in chat (LLM-generated from context)
- **Anti-abuse**: 247 regex patterns, rate limits, DoS prevention

## Tools (13)

| Tool | Description |
|------|-------------|
| `run_command` | Execute shell (runs in sandbox container) |
| `read_file` | Read file content |
| `write_file` | Create/overwrite file |
| `edit_file` | Edit file (find & replace) |
| `delete_file` | Delete file |
| `search_files` | Find files by glob |
| `search_text` | Search text in files |
| `list_directory` | List directory |
| `search_web` | Web search (Z.AI) |
| `fetch_page` | Fetch URL content |
| `send_file` | Send file to chat |
| `send_dm` | Send private message |
| `memory` | Persistent notes across sessions |

## Quick Start

```bash
# 1. Create secrets
mkdir secrets
echo "your-telegram-token" > secrets/telegram_token.txt
echo "http://your-llm:8000/v1" > secrets/base_url.txt
echo "your-llm-key" > secrets/api_key.txt
echo "your-zai-key" > secrets/zai_api_key.txt

# 2. Start
docker compose up -d

# 3. Check
docker compose logs -f
```

## Configuration

All settings in `src/config.ts`:

| Section | What it controls |
|---------|------------------|
| `rateLimit` | Telegram API limits |
| `timeouts` | Tool execution, API calls |
| `agent` | Max iterations, history |
| `sandbox` | Container limits, TTL |
| `reactions` | Emoji chance, weights |
| `thoughts` | Autonomous messages interval |

## Security

**247 regex patterns** protecting against attacks:
- 191 BLOCKED (never allowed)
- 56 DANGEROUS (require approval)

Categories:
- Secrets: env, /proc/environ, /run/secrets, process.env
- Exfiltration: base64 encode, curl POST, HTTP servers reading secrets
- DoS: fork bombs, zip bombs, huge allocations
- Escape: other workspaces, host filesystem, Docker socket

Architecture:
- **Docker sandbox** per user (dynamic containers)
- **Docker Secrets** for all API keys  
- **Internal proxy** isolates secrets from agent
- **Per-user workspace** isolation (only own dir mounted)

## Structure

```
├── docker-compose.yml    # Gateway + Proxy
├── secrets/              # API keys (gitignored)
├── proxy/                # Internal API proxy
└── src/
    ├── config.ts         # All settings
    ├── agent/            # ReAct loop
    ├── bot/              # Telegram bot
    ├── approvals/        # Security patterns
    └── tools/            # 13 tools + Docker sandbox
```

## License

MIT
