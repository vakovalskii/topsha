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
                              ┌─────────────────┐
                              │    Telegram     │
                              │      API        │
                              └────────┬────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              │                        │                        │
              ▼                        ▼                        ▼
       ┌─────────────┐          ┌─────────────┐          ┌─────────────┐
       │     bot     │          │   userbot   │          │    admin    │
       │   aiogram   │          │  telethon   │          │    React    │
       │   :4001     │          │    :8080    │          │    :3000    │
       └──────┬──────┘          └──────┬──────┘          └──────┬──────┘
              │                        │                        │
              │         HTTP API       │                        │
              └────────────┬───────────┘                        │
                           │                                    │
                           ▼                                    │
                    ╔═════════════╗                             │
                    ║    CORE     ║◀────────────────────────────┘
                    ║   Agent     ║
                    ║  (FastAPI)  ║────────────────────▶ proxy :3200
                    ║   :4000     ║      LLM/Search      (secrets)
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

## Tools Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Tools API (:8100)                        │
│                                                             │
│  SHARED TOOLS (13) - можно вкл/выкл в админке:             │
│  run_command, read_file, write_file, edit_file,            │
│  delete_file, search_files, search_text, list_directory,   │
│  search_web, fetch_page, memory, schedule_task,            │
│  manage_tasks                                               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                         Core Agent                          │
├─────────────────────────────────────────────────────────────┤
│  source=bot:     13 shared + 4 bot-only = 17 tools         │
│  source=userbot: 13 shared              = 13 tools         │
├─────────────────────────────────────────────────────────────┤
│  BOT-ONLY (4) - always available for telegram bot:         │
│  send_file, send_dm, manage_message, ask_user              │
└─────────────────────────────────────────────────────────────┘
```

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

## Admin Panel

Web panel at `:3000` for managing the system:

- **Dashboard** — stats, active users, sandboxes
- **Services** — start/stop bot, userbot containers
- **Config** — agent settings, rate limits
- **Security** — 247 blocked patterns
- **Tools** — enable/disable shared tools
- **Users** — sessions, chat history, memory
- **Logs** — real-time service logs
- **Access Control** — public/admin-only/allowlist modes

## Access Control

Three modes managed via admin panel:

| Mode | Description |
|------|-------------|
| **Public** | Anyone can use bot/userbot |
| **Admin Only** | Only admin (ID 809532582) |
| **Allowlist** | Admin + configured user IDs |

## Dynamic Sandbox

Each user gets isolated Docker container:

- **Image**: `python:3.11-slim`
- **Ports**: 10 ports per user (5000-5999)
- **Resources**: 512MB RAM, 50% CPU, 100 PIDs
- **Workspace**: Only own `/workspace/{user_id}/`
- **TTL**: 10 min inactivity → auto-cleanup
- **Security**: `no-new-privileges`, no secrets access

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

## Security

**266+ protection patterns:**
- 247 blocked shell command patterns
- 19 prompt injection patterns

**Layers:**
1. **Sandbox isolation** — each user in separate container
2. **Workspace separation** — users can't access each other's files
3. **Secrets via Proxy** — agent never sees API keys
4. **Command blocking** — env, /proc, secrets paths blocked
5. **Output sanitization** — secrets redacted from output
6. **Rate limiting** — Telegram API, groups, reactions
7. **Access control** — public/admin/allowlist modes

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
│   └── Dockerfile
│
├── bot/                  # Telegram Bot (Python/aiogram)
│   ├── main.py
│   ├── handlers.py
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
