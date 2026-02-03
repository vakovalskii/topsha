# LocalTopSH Agent Evolution

## Что это
Telegram бот с ReAct агентом, который дает пользователям доступ к изолированному Linux окружению.
Протестирован 1450+ хакерами в группе @neuraldeepchat в течение 7 часов.
Результат: 0 утечек секретов, 0 даунтайма.

## Цикл эволюции

```
┌─────────────────────────────────────────────────────────────┐
│                    EVOLUTION CYCLE                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   1. MONITOR                                                │
│      ├─ Читать логи контейнера (docker logs gateway -f)    │
│      ├─ Смотреть CHAT_HISTORY.md в workspace/_shared/      │
│      └─ Анализировать паттерны атак                        │
│                                                             │
│   2. DETECT                                                 │
│      ├─ Новый вектор атаки?                                │
│      ├─ Попытка утечки env/secrets?                        │
│      ├─ DoS/resource exhaustion?                           │
│      └─ Prompt injection?                                   │
│                                                             │
│   3. PATCH                                                  │
│      ├─ Добавить regex в BLOCKED_PATTERNS                  │
│      ├─ Обновить system.txt prompt                         │
│      ├─ Добавить sanitization в bash.ts                    │
│      └─ Обновить security.ts (prompt injection)            │
│                                                             │
│   4. DEPLOY                                                 │
│      ├─ docker compose build --no-cache                    │
│      ├─ docker compose up -d                               │
│      └─ Мониторить логи после деплоя                       │
│                                                             │
│   5. REPEAT                                                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Ключевые файлы для патчинга

| Файл | Что патчить |
|------|-------------|
| `src/approvals/index.ts` | BLOCKED_PATTERNS, DANGEROUS_PATTERNS |
| `src/tools/bash.ts` | SECRET_PATTERNS, sanitizeOutput() |
| `src/bot/security.ts` | PROMPT_INJECTION_PATTERNS |
| `src/agent/system.txt` | Системный промпт агента |
| `proxy/index.js` | Прокси для API ключей |

## Архитектура безопасности

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Gateway   │────▶│    Proxy    │────▶│  External   │
│  (Bot+Agent)│     │ (API Keys)  │     │    APIs     │
│  0 secrets  │     │  /run/sec/  │     │             │
└─────────────┘     └─────────────┘     └─────────────┘
       │
       ▼
┌─────────────┐
│  /workspace │
│  per-user   │
│  isolated   │
└─────────────┘
```

## Команды мониторинга

```bash
# Логи в реальном времени
docker logs gateway -f --tail 100

# Проверить что контейнеры живы
docker ps

# Перезапуск после патча
docker compose down && docker compose up -d --build

# Посмотреть историю чата
cat workspace/_shared/CHAT_HISTORY.md | tail -100
```

## При падении сервера

1. Проверить `docker ps` - все контейнеры должны быть Up
2. Проверить `docker logs gateway` на ошибки
3. Если OOM - увеличить memory limit в docker-compose.yml
4. Если rate limit - подождать или увеличить интервалы в rate-limiter.ts
