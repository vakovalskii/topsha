# 🐧 LocalTopSH

**AI Agent with full system access — your own infrastructure, your own rules.**

> 🔥 **Battle-tested by 1500+ hackers!**
> 
> Live in [**@neuraldeepchat**](https://t.me/neuraldeepchat) — community stress-tested with **1500+ attack attempts**:
> - Token extraction (env, /proc, base64 exfil, HTTP servers)
> - RAM/CPU exhaustion (zip bombs, infinite loops, fork bombs)
> - Container escape attempts
> 
> **Result: 0 secrets leaked, 0 downtime.**

---

## Philosophy: Engineering Over Subscription Abuse

Unlike projects that rely on abusing consumer subscriptions (Claude Max, ChatGPT Plus) through browser automation and cookie theft, **LocalTopSH is built on honest engineering principles**:

| Approach | LocalTopSH ✅ | Subscription Abuse ❌ |
|----------|--------------|----------------------|
| **LLM Access** | Your own API keys | Stolen browser sessions |
| **Cost Model** | Pay for what you use | Violate ToS, risk bans |
| **Reliability** | 100% uptime (your infra) | Breaks when UI changes |
| **Security** | Full control over secrets | Cookies stored who-knows-where |
| **Ethics** | Transparent & legal | Gray area at best |

**We believe in building real infrastructure, not hacks that break tomorrow.**

---

## Agent Skills

What the agent can do out of the box:

### 💻 System & Files
| Skill | Description |
|-------|-------------|
| **Shell execution** | Run any command in isolated sandbox |
| **File operations** | Read, write, edit, delete, search files |
| **Directory navigation** | List, search by glob patterns |
| **Code execution** | Python, Node.js, bash scripts |

### 🌐 Web & Research
| Skill | Description |
|-------|-------------|
| **Web search** | Search via Z.AI API |
| **Page fetching** | Get any URL as clean markdown |
| **Link extraction** | Parse and follow links |

### 🧠 Memory & Context
| Skill | Description |
|-------|-------------|
| **Persistent memory** | Remember facts across sessions |
| **Task management** | Todo lists within session |
| **Chat history** | Full conversation context |

### ⏰ Automation
| Skill | Description |
|-------|-------------|
| **Scheduled tasks** | Cron-like reminders |
| **Background jobs** | Long-running processes |

### 📱 Telegram Integration
| Skill | Description |
|-------|-------------|
| **Send files** | Share generated files |
| **Direct messages** | Send DMs to users |
| **Message management** | Edit/delete bot messages |
| **Interactive prompts** | Ask user and wait for response |

---

## MCP Support (Planned)

> 🚧 **Coming soon** — Model Context Protocol integration

LocalTopSH will support MCP for extensible tool integration:

```
┌─────────────────────────────────────────────────────────────────┐
│                      MCP Architecture                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────┐     ┌─────────────┐     ┌─────────────────────┐  │
│   │  Agent  │────▶│  MCP Host   │────▶│  MCP Servers        │  │
│   └─────────┘     └─────────────┘     ├─────────────────────┤  │
│                                       │ • filesystem        │  │
│                                       │ • git               │  │
│                                       │ • database          │  │
│                                       │ • browser           │  │
│                                       │ • custom tools...   │  │
│                                       └─────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Planned MCP Features

- [ ] MCP server discovery and connection
- [ ] Dynamic tool registration from MCP servers
- [ ] Resource access (files, databases)
- [ ] Prompt templates from MCP
- [ ] Custom MCP server development guide

---

## Architecture

```
                              ┌─────────────────┐
                              │    Telegram     │
                              │      API        │
                              └────────┬────────┘
                                       │
              ┌────────────────────────┴────────────────────────┐
              │                                                 │
              ▼                                                 ▼
       ┌─────────────┐                                   ┌─────────────┐
       │     bot     │                                   │   userbot   │
       │   aiogram   │                                   │  telethon   │
       │   :4001     │                                   │    :8080    │
       └──────┬──────┘                                   └──────┬──────┘
              │                                                 │
              │                  HTTP API                       │
              └────────────────────┬────────────────────────────┘
                                   │
                                   ▼
       ┌─────────────┐      ╔═════════════╗
       │    admin    │      ║    CORE     ║
       │    React    │─────▶║   Agent     ║
       │    :3000    │      ║  (FastAPI)  ║────────────────────▶ proxy :3200
       └─────────────┘      ║   :4000     ║      LLM/Search      (secrets)
                            ╠═════════════╣
                            ║ • ReAct     ║
                            ║ • Security  ║
                            ║ • Scheduler ║─────────▶ tools-api :8100
                            ╚══════┬══════╝           (shared tools)
                                   │
                      ┌────────────┼────────────┐
                      │            │            │
                      ▼            ▼            ▼
               ┌───────────┐ ┌───────────┐ ┌───────────┐
               │ sandbox_1 │ │ sandbox_2 │ │ sandbox_N │
               │  user123  │ │  user456  │ │   user... │
               └─────┬─────┘ └─────┬─────┘ └─────┬─────┘
                     │             │             │
                     ▼             ▼             ▼
               ┌───────────────────────────────────────┐
               │           /workspace (volume)         │
               │  /123/  │  /456/  │  /.../ │ /_shared │
               └───────────────────────────────────────┘
```

## Services

| Service | Stack | Port | Description |
|---------|-------|------|-------------|
| **core** | FastAPI | 4000 | ReAct Agent, security, scheduler |
| **bot** | aiogram | 4001 | Telegram Bot API, reactions, thoughts |
| **userbot** | Telethon | 8080 | User account bot (optional) |
| **proxy** | aiohttp | 3200 | Secrets isolation, LLM/search proxy |
| **tools-api** | FastAPI | 8100 | Shared tools registry (single source of truth) |
| **admin** | React | 3000 | Web admin panel |
| **sandbox_*** | python:slim | 5000-5999 | Per-user isolated containers |

## Tools

### Shared Tools (13)

| Tool | Description |
|------|-------------|
| `run_command` | Execute shell in user's sandbox |
| `read_file` | Read file content |
| `write_file` | Create/overwrite file |
| `edit_file` | Edit file (find & replace) |
| `delete_file` | Delete file |
| `search_files` | Find files by glob |
| `search_text` | Grep in files |
| `list_directory` | List directory |
| `search_web` | Web search (Z.AI) |
| `fetch_page` | Fetch URL as markdown |
| `memory` | Persistent user notes |
| `schedule_task` | Schedule reminders/cron |
| `manage_tasks` | Session todo list |

### Bot-Only Tools (4)

| Tool | Description |
|------|-------------|
| `send_file` | Send file to chat |
| `send_dm` | Send private message |
| `manage_message` | Edit/delete bot messages |
| `ask_user` | Ask question, wait answer |

## Security

> 📖 **Full documentation:** [SECURITY.md](SECURITY.md)

### Five Layers of Protection

| Layer | Protection | Details |
|-------|------------|---------|
| **Access Control** | DM Policy | admin/allowlist/pairing/public modes |
| **Input Validation** | Blocked patterns | 247 dangerous commands blocked |
| **Injection Defense** | Pattern matching | 19 prompt injection patterns |
| **Sandbox Isolation** | Docker per-user | 512MB RAM, 50% CPU, 100 PIDs |
| **Secrets Protection** | Proxy architecture | 0 secrets visible to agent |

### Security Audit

```bash
# Run security doctor
python scripts/doctor.py

# Output as JSON
python scripts/doctor.py --json
```

## Access Control

Four modes managed via bot commands or admin panel:

| Mode | Description |
|------|-------------|
| **Admin Only** | Only admin can use (default, safest) |
| **Allowlist** | Admin + configured user IDs |
| **Pairing** | Unknown users get pairing code for approval |
| **Public** | Anyone can use (⚠️ requires rate limiting) |

### Bot Commands

```bash
/access              # Show access status (admin only)
/access_mode admin   # Set mode
/approve ABC123      # Approve pairing code
/revoke 123456789    # Revoke user access
/allow 123456789     # Add to allowlist
```

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

# 4. Admin panel
open http://localhost:3000
```

## Admin Panel

Web panel at `:3000` for managing the system:

- **Dashboard** — stats, active users, sandboxes
- **Services** — start/stop bot, userbot containers
- **Config** — agent settings, rate limits
- **Security** — blocked patterns management
- **Tools** — enable/disable shared tools
- **Users** — sessions, chat history, memory
- **Logs** — real-time service logs
- **Access Control** — public/admin-only/allowlist modes

## Dynamic Sandbox

Each user gets isolated Docker container:

- **Image**: `python:3.11-slim`
- **Ports**: 10 ports per user (5000-5999)
- **Resources**: 512MB RAM, 50% CPU, 100 PIDs
- **Workspace**: Only own `/workspace/{user_id}/`
- **TTL**: 10 min inactivity → auto-cleanup
- **Security**: `no-new-privileges`, no secrets access

## Project Structure

```
LocalTopSH/
├── docker-compose.yml
├── secrets/              # API keys (gitignored)
│
├── core/                 # ReAct Agent (Python/FastAPI)
│   ├── main.py
│   ├── agent.py         # ReAct loop
│   ├── api.py           # HTTP API
│   ├── admin_api.py     # Admin panel API
│   ├── security.py      # Blocked patterns
│   ├── tools/           # Tool executors
│   │   └── permissions.py  # Tool allowlist/denylist
│   └── Dockerfile
│
├── scripts/              # CLI tools
│   └── doctor.py        # Security audit
│
├── bot/                  # Telegram Bot (Python/aiogram)
│   ├── main.py
│   ├── handlers.py
│   ├── access.py        # DM Policy
│   ├── thoughts.py      # Autonomous messages
│   ├── security.py      # Prompt injection
│   └── Dockerfile
│
├── userbot/              # Telegram Userbot (Python/Telethon)
│   ├── main.py
│   └── Dockerfile
│
├── proxy/                # API Proxy (Python/aiohttp)
│   ├── main.py
│   └── Dockerfile
│
├── tools-api/            # Shared Tools Registry (Python/FastAPI)
│   ├── main.py
│   └── Dockerfile
│
├── admin/                # Admin Panel (React/Vite)
│   ├── src/
│   │   ├── pages/       # Dashboard, Config, Security, Tools, Users, Logs
│   │   └── api.js
│   └── Dockerfile
│
└── workspace/            # User data (gitignored)
    ├── {user_id}/       # Per-user workspace
    └── _shared/         # Shared config (tools, access)
```

## Secrets

| Secret | Required | Description |
|--------|----------|-------------|
| `telegram_token.txt` | ✅ | Bot token from @BotFather |
| `base_url.txt` | ✅ | LLM API URL |
| `api_key.txt` | ✅ | LLM API key |
| `zai_api_key.txt` | ✅ | Z.AI search key |
| `telegram_api_id.txt` | Userbot | Telegram API ID |
| `telegram_api_hash.txt` | Userbot | Telegram API Hash |
| `telegram_phone.txt` | Userbot | Phone number |

## License

MIT
