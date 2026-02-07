# LocalTopSH Architecture

## Overview

LocalTopSH — AI Agent Framework для self-hosted LLM. Позволяет развернуть полноценного AI-агента на своей инфраструктуре с любой OpenAI-совместимой моделью.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         YOUR INFRASTRUCTURE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────────────────┐  │
│   │ Telegram │    │  Admin   │    │   Your   │    │    MCP Servers       │  │
│   │   Bot    │    │  Panel   │    │   LLM    │    │  ┌────────────────┐  │  │
│   │  :4001   │    │  :3000   │    │ Backend  │    │  │  docker-mcp    │  │  │
│   └────┬─────┘    └────┬─────┘    └────┬─────┘    │  │  :8300         │  │  │
│        │               │               │          │  ├────────────────┤  │  │
│        │               │               │          │  │  mcp-test      │  │  │
│        ▼               ▼               │          │  │  :8200         │  │  │
│   ┌────────────────────────────────┐   │          │  ├────────────────┤  │  │
│   │           CORE :4000           │   │          │  │  custom MCP... │  │  │
│   │  ┌──────────────────────────┐  │   │          │  └────────────────┘  │  │
│   │  │      ReAct Agent         │  │   │          └──────────┬───────────┘  │
│   │  │  (think → act → observe) │◀─┼───┘                     │              │
│   │  └──────────────────────────┘  │                         │              │
│   │              │                  │                         │              │
│   │              ▼                  │                         │              │
│   │  ┌──────────────────────────┐  │    ┌──────────────────┐ │              │
│   │  │     Security Layer       │  │    │   tools-api      │◀┘              │
│   │  │  • 247 blocked patterns  │  │    │   :8100          │                │
│   │  │  • 19 injection patterns │  │    │  ┌────────────┐  │                │
│   │  │  • Output sanitization   │  │    │  │ Built-in   │  │                │
│   │  └──────────────────────────┘  │    │  │ Tools (19) │  │                │
│   │              │                  │    │  ├────────────┤  │                │
│   │              ▼                  │    │  │ MCP Tools  │  │                │
│   │  ┌──────────────────────────┐  │    │  ├────────────┤  │                │
│   │  │   Sandbox Orchestrator   │  │    │  │ Skills     │  │                │
│   │  │  (Docker per-user)       │  │    │  └────────────┘  │                │
│   │  └──────────────────────────┘  │    └──────────────────┘                │
│   └────────────────────────────────┘                                        │
│                    │                                                         │
│                    ▼                                                         │
│   ┌────────────────────────────────┐                                        │
│   │         PROXY :3200            │                                        │
│   │   (API keys isolation)         │                                        │
│   │   Agent never sees secrets     │                                        │
│   └────────────────────────────────┘                                        │
│                    │                                                         │
│                    ▼                                                         │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │                    SANDBOXES (per-user)                             │    │
│   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │    │
│   │  │ sandbox_123 │  │ sandbox_456 │  │ sandbox_789 │  ...            │    │
│   │  │ 512MB, 50%  │  │ 512MB, 50%  │  │ 512MB, 50%  │                 │    │
│   │  │ CPU, 100PID │  │ CPU, 100PID │  │ CPU, 100PID │                 │    │
│   │  └─────────────┘  └─────────────┘  └─────────────┘                 │    │
│   └────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Services

### Core Services

| Service | Port | Image | Role | Volumes |
|---------|------|-------|------|---------|
| **core** | 4000 | Python 3.11 | ReAct Agent, API, Security, Sandbox orchestration | `/workspace`, `/var/run/docker.sock` |
| **bot** | 4001 | Python 3.11 | Telegram Bot (aiogram), rate limiting, access control | `/data` (pairing.json) |
| **proxy** | 3200 | Python 3.11 | Secrets isolation, LLM API proxy | Secrets only |
| **tools-api** | 8100 | Python 3.11 | Tool registry, MCP integration, Skills | `/data`, `/workspace` |
| **admin** | 3000 | nginx + React | Web admin panel (Basic Auth) | - |

### Scheduler

| Service | Port | Role | Features |
|---------|------|------|----------|
| **scheduler** | 8400 | Persistent task scheduling | Survives restarts, recurring tasks, JSON storage |

### MCP Servers

| Service | Port | Role | Tools |
|---------|------|------|-------|
| **docker-mcp** | 8300 | Docker management | 17 tools (ps, run, stop, logs, exec, compose...) |
| **mcp-test** | 8200 | Test server | 3 tools (echo, time, random) |

### Dynamic Containers

| Container | Ports | Role | Limits |
|-----------|-------|------|--------|
| **sandbox_{user_id}** | 5000-5999 | Per-user isolated execution | 512MB RAM, 50% CPU, 100 PIDs |

---

## Data Flow

### 1. Message Processing

```
User Message (Telegram)
        │
        ▼
┌───────────────────┐
│       Bot         │  Access control, rate limiting
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│       Core        │  
│  ┌─────────────┐  │
│  │ Security    │  │  Prompt injection detection (19 patterns)
│  │ Validator   │  │  Blocked commands check (247 patterns)
│  └──────┬──────┘  │
│         │         │
│  ┌──────▼──────┐  │
│  │ ReAct Agent │  │  Think → Act → Observe loop
│  │             │  │  Max 30 iterations
│  └──────┬──────┘  │
│         │         │
│  ┌──────▼──────┐  │
│  │ Tool Router │  │  Route to appropriate tool
│  └─────────────┘  │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│    tools-api      │  Tool definitions, MCP, Skills
└─────────┬─────────┘
          │
    ┌─────┴─────┐
    │           │
    ▼           ▼
Built-in    MCP Tools
 Tools      (docker-mcp, etc.)
```

### 2. LLM Request Flow

```
Core Agent
    │
    ▼
┌─────────┐
│  Proxy  │  Injects API key from Docker secret
└────┬────┘
     │
     ▼
┌─────────────────┐
│   Your LLM      │  vLLM / Ollama / llama.cpp / etc.
│   Backend       │
└─────────────────┘
```

### 3. Sandbox Execution

```
Tool: run_command("pip install pandas")
            │
            ▼
┌───────────────────────────┐
│   Sandbox Orchestrator    │
│   (in Core)               │
└───────────┬───────────────┘
            │
            ▼
┌───────────────────────────┐
│  Docker API               │
│  • Create container       │
│  • Set limits             │
│  • Mount workspace        │
│  • Execute command        │
│  • Stream output          │
└───────────────────────────┘
            │
            ▼
┌───────────────────────────┐
│  sandbox_809532582        │
│  ├── /workspace (mounted) │
│  ├── 512MB RAM limit      │
│  ├── 50% CPU limit        │
│  └── 100 PIDs limit       │
└───────────────────────────┘
```

---

## Security Model

### Five Layers

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: ACCESS CONTROL                                    │
│  ─────────────────────────────────────────────────────────  │
│  DM Policy: admin / allowlist / pairing / public            │
│  Implemented in: bot/access.py                              │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: INPUT VALIDATION                                  │
│  ─────────────────────────────────────────────────────────  │
│  247 blocked patterns for dangerous commands                │
│  File: core/src/approvals/blocked-patterns.json             │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: PROMPT INJECTION DEFENSE                          │
│  ─────────────────────────────────────────────────────────  │
│  19 patterns: "forget instructions", "DAN mode", etc.       │
│  File: bot/prompt-injection-patterns.json                   │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  Layer 4: SANDBOX ISOLATION                                 │
│  ─────────────────────────────────────────────────────────  │
│  Docker per-user: 512MB RAM, 50% CPU, 100 PIDs              │
│  Network: internal only, no host access                     │
│  Filesystem: /workspace/{user_id} only                      │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  Layer 5: SECRETS PROTECTION                                │
│  ─────────────────────────────────────────────────────────  │
│  Proxy architecture: agent never sees API keys              │
│  Docker secrets: mounted at /run/secrets/                   │
│  Output sanitization: base64/hex detection                  │
└─────────────────────────────────────────────────────────────┘
```

### Tool Permissions by Session Type

| Tool | main (DM) | group | sandbox | userbot |
|------|-----------|-------|---------|---------|
| run_command | ✅ | ✅ | ✅ | ✅ |
| read_file | ✅ | ✅ | ✅ | ✅ |
| write_file | ✅ | ✅ | ✅ | ✅ |
| send_file | ✅ | ✅ | ❌ | ❌ |
| send_dm | ✅ | ❌ | ❌ | ❌ |
| manage_message | ✅ | ❌ | ❌ | ❌ |
| ask_user | ✅ | ✅ | ❌ | ❌ |
| schedule_task | ✅ | ❌ | ❌ | ❌ |
| MCP tools | ✅ | ✅ | ✅ | ✅ |

---

## Tools Architecture

### Built-in Tools (19)

| Category | Tools |
|----------|-------|
| **System** | `run_command`, `read_file`, `write_file`, `edit_file`, `delete_file`, `list_directory`, `search_files`, `search_text` |
| **Web** | `web_search`, `fetch_page`, `extract_links` |
| **Memory** | `memory` (persistent notes) |
| **Tasks** | `manage_tasks` |
| **Telegram** | `send_file`, `send_dm`, `manage_message`, `ask_user` |
| **Scheduler** | `schedule_task` |

### MCP Tools (Dynamic)

```
tools-api
    │
    ├── GET /mcp/servers          → List configured MCP servers
    ├── POST /mcp/servers         → Add new MCP server
    ├── POST /mcp/refresh-all     → Refresh tools from all servers
    │
    └── MCP Server (JSON-RPC 2.0)
            │
            ├── tools/list        → Get available tools
            └── tools/call        → Execute a tool
```

### Skills (Anthropic-compatible)

```
/workspace/_shared/skills/
    └── pptx/
        ├── skill.json           # Metadata
        ├── SKILL.md             # Full instructions (loaded on-demand)
        ├── pptxgenjs.md         # Additional docs
        └── scripts/             # Helper scripts
```

Skills are mentioned in system prompt, full instructions loaded by agent via `read_file`.

---

## Configuration

### Docker Secrets

| Secret | File | Used By |
|--------|------|---------|
| `telegram_token` | `secrets/telegram_token.txt` | bot |
| `base_url` | `secrets/base_url.txt` | proxy |
| `api_key` | `secrets/api_key.txt` | proxy |
| `model_name` | `secrets/model_name.txt` | core, bot |
| `zai_api_key` | `secrets/zai_api_key.txt` | proxy |
| `admin_password` | `secrets/admin_password.txt` | admin |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ACCESS_MODE` | `admin` | DM policy: admin/allowlist/pairing/public |
| `ADMIN_USER_ID` | `809532582` | Telegram admin user ID |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `ADMIN_USER` | `admin` | Admin panel username |

### Resource Limits

| Container | CPU | Memory | PIDs |
|-----------|-----|--------|------|
| core | 2.0 | 2GB | 300 |
| bot | 0.5 | 512MB | - |
| proxy | 0.5 | 256MB | - |
| tools-api | 0.3 | 192MB | - |
| admin | 0.2 | 128MB | - |
| sandbox_* | 0.5 | 512MB | 100 |

---

## Networks

```
agent-net (bridge)
    │
    ├── core ◄──► proxy ◄──► [External LLM]
    │     │
    │     ├──► bot
    │     ├──► tools-api ◄──► docker-mcp
    │     │                   mcp-test
    │     └──► sandbox_* (dynamic)
    │
    └── admin ◄──► core
```

All services communicate via internal Docker network. Only exposed ports:
- `3000` — Admin panel (Basic Auth protected)
- `4001` — Bot HTTP (internal callbacks only)

---

## File Structure

```
LocalTopSH/
├── core/                    # ReAct Agent + API
│   ├── agent.py             # Agent loop
│   ├── api.py               # HTTP API
│   ├── config.py            # Configuration
│   ├── tools/               # Tool implementations
│   └── src/
│       ├── agent/system.txt # System prompt
│       └── approvals/       # Security patterns
│
├── bot/                     # Telegram Bot
│   ├── main.py              # Entry point
│   ├── handlers.py          # Message handlers
│   ├── access.py            # Access control
│   └── security.py          # Prompt injection detection
│
├── proxy/                   # Secrets proxy
│   └── main.py              # LLM API proxy
│
├── tools-api/               # Tool registry
│   ├── app.py               # Entry point
│   └── src/
│       ├── routes/          # API routes
│       ├── mcp.py           # MCP client
│       └── skills.py        # Skills manager
│
├── docker-mcp/              # Docker MCP server
│   └── main.py              # 17 Docker tools
│
├── admin/                   # Web panel
│   └── src/
│       └── pages/           # React pages
│
├── workspace/               # User workspaces
│   ├── _shared/             # Shared data
│   │   ├── skills/          # Installed skills
│   │   └── mcp_servers.json # MCP config
│   └── {user_id}/           # Per-user workspace
│
├── secrets/                 # Docker secrets
│   ├── telegram_token.txt
│   ├── base_url.txt
│   ├── api_key.txt
│   └── ...
│
├── scripts/
│   ├── doctor.py            # Security audit
│   └── e2e_test.py          # E2E tests
│
└── docker-compose.yml       # All services
```

---

## Monitoring

### Health Checks

All services expose `/health` endpoint:

```bash
curl http://localhost:4000/health  # core
curl http://localhost:4001/health  # bot
curl http://localhost:3200/health  # proxy
curl http://localhost:8100/health  # tools-api
curl http://localhost:3000/health  # admin (no auth)
curl http://localhost:8300/health  # docker-mcp
```

### Logs

```bash
# All services
docker compose logs -f

# Specific service
docker logs core -f --tail 100

# Security events
docker logs core -f | grep -E "(SECURITY|BLOCKED|INJECTION)"
```

### Security Audit

```bash
# Run security doctor (46 checks)
python scripts/doctor.py

# E2E tests (10 checks)
python scripts/e2e_test.py --verbose
```

---

## Extending

### Adding MCP Server

1. Create server with JSON-RPC 2.0 endpoints:
   - `POST /` with `method: "tools/list"` → returns tools
   - `POST /` with `method: "tools/call"` → executes tool

2. Add to `docker-compose.yml`

3. Register via API or config:
   ```bash
   curl -X POST http://localhost:8100/mcp/servers \
     -H "Content-Type: application/json" \
     -d '{"name":"myserver","url":"http://myserver:8000"}'
   ```

### Adding Skill

1. Create directory in `/workspace/_shared/skills/{name}/`
2. Add `skill.json` with metadata
3. Add `SKILL.md` with full instructions
4. Skill will be auto-discovered on next agent run

### Adding Built-in Tool

1. Implement in `core/tools/`
2. Register in `tools-api/src/config.py` SHARED_TOOLS
3. Add permissions in `core/tools/permissions.py`
