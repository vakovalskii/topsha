# LocalTopSH 🐧

**Production-ready ReAct agent for Telegram group chats.**

> 🔥 **Battle-tested by 1450+ hackers for 7 hours straight!**
> 
> Live in [**@neuraldeepchat**](https://t.me/neuraldeepchat) — community stress-tested with **1500+ attack attempts**:
> - API key extraction (env, /proc, base64 exfil)
> - RAM/CPU exhaustion (huge factorials, infinite loops)
> - Process killing, fork bombs
> - Container escape attempts
> 
> **Result: 0 secrets leaked, 0 downtime.**
> 
> Join and try to break it!

## Features

- ReAct agent with 13 tools (shell, files, web search, memes, scheduler)
- Per-user isolated workspaces in Docker
- Secrets isolation via Docker Secrets + internal Proxy
- Smart reactions on messages (LLM-powered)
- Autonomous "thoughts" in chat
- Anti-abuse: rate limits, DoS prevention, command blocking
- 42 security tests passing

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Telegram  │────▶│   Gateway   │────▶│    Proxy    │
│   1450+     │     │  (bot+agent)│     │  (secrets)  │
│   users     │◀────│             │◀────│             │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                    ┌──────┴──────┐
                    │  /workspace │
                    │  per-user   │
                    │  isolation  │
                    └─────────────┘
```

**Secrets never exposed to agent!** Agent only sees `PROXY_URL`.

## Tools (13)

| Tool | Description |
|------|-------------|
| `run_command` | Execute shell commands |
| `read_file` | Read file content |
| `write_file` | Create/overwrite file |
| `edit_file` | Edit file (find & replace) |
| `delete_file` | Delete file |
| `search_files` | Find files by glob |
| `search_text` | Search text in files |
| `list_directory` | List directory contents |
| `search_web` | Web search (Z.AI) |
| `fetch_page` | Fetch URL content |
| `send_file` | Send file to chat |
| `get_meme` | Random meme/dog/cat |
| `schedule_task` | Delayed messages/commands |

## Quick Start

```bash
# 1. Create secrets
mkdir secrets
echo "your-telegram-token" > secrets/telegram_token.txt
echo "http://your-llm:8000/v1" > secrets/base_url.txt
echo "your-llm-key" > secrets/api_key.txt
echo "your-zai-key" > secrets/zai_api_key.txt
chmod 644 secrets/*.txt

# 2. Start
docker compose up -d
```

## Security

**217 regex patterns** protecting against attacks:
- 161 BLOCKED (never allowed)
- 56 DANGEROUS (require approval in DM)

Categories:
- Secrets: env, printenv, /proc/environ, /run/secrets, process.env, os.environ
- Exfiltration: base64, xxd, hexdump, curl POST, DNS tunneling
- DoS: fork bombs, stress tests, huge factorials, infinite loops
- Packages: tensorflow, pytorch (multi-GB), compiler toolchains
- Network: cloud metadata, internal services, port scanning
- Files: .env, credentials, SSH keys, symlink attacks

Architecture:
- Docker Secrets for all API keys
- Internal proxy isolates secrets from agent
- Per-user workspace isolation
- Rate limiting (Telegram API)

## Structure

```
├── docker-compose.yml    # Gateway + Proxy containers
├── secrets/              # API keys (gitignored)
├── proxy/                # Internal API proxy
│   └── index.js
└── src/
    ├── agent/            # ReAct loop
    ├── bot/              # Telegram bot
    ├── approvals/        # Command security
    └── tools/            # 13 tools
```

## License

MIT
