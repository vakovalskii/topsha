"""
API Proxy - isolates secrets from agent container
Reads secrets from /run/secrets/ (Docker Secrets)
Agent sees only http://proxy:3200, no API keys
"""

import os
import asyncio
import aiohttp
from aiohttp import web
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[proxy] %(message)s'
)
log = logging.getLogger(__name__)

PORT = int(os.getenv("PROXY_PORT", "3200"))


def read_secret(name: str) -> str | None:
    """Read secret from file (Docker Secrets mount at /run/secrets/)"""
    paths = [
        f"/run/secrets/{name}",
        f"/run/secrets/{name}.txt",
        f"./secrets/{name}.txt",
        f"/app/secrets/{name}.txt",
    ]
    
    for path in paths:
        try:
            with open(path, 'r') as f:
                value = f.read().strip()
                if value:
                    log.info(f"Secret '{name}' loaded from {path}")
                    return value
        except (FileNotFoundError, PermissionError):
            continue
    
    # Fallback to env (insecure)
    env_name = name.upper()
    if os.getenv(env_name):
        log.warning(f"Secret '{name}' loaded from env (INSECURE)")
        return os.getenv(env_name)
    
    log.warning(f"WARNING: Secret '{name}' not found!")
    return None


# Load secrets at startup
LLM_BASE_URL = read_secret("base_url")
LLM_API_KEY = read_secret("api_key")
ZAI_API_KEY = read_secret("zai_api_key")


async def health(request: web.Request) -> web.Response:
    """Health check endpoint"""
    return web.json_response({
        "status": "ok",
        "llm": bool(LLM_BASE_URL),
        "zai": bool(ZAI_API_KEY)
    })


import json

LOG_RAW = os.getenv("LOG_RAW", "false").lower() == "true"

def pretty_json(data: bytes) -> str:
    """Pretty print JSON with UTF-8"""
    try:
        obj = json.loads(data)
        return json.dumps(obj, indent=2, ensure_ascii=False)
    except:
        return data.decode('utf-8', errors='replace')

async def proxy_llm(request: web.Request) -> web.StreamResponse:
    """Proxy /v1/* requests to LLM API with auth"""
    if not LLM_BASE_URL:
        return web.json_response({"error": "LLM not configured"}, status=500)
    
    # Build target URL
    path = request.match_info.get("path", "")
    target_url = LLM_BASE_URL.rstrip("/v1").rstrip("/") + "/v1/" + path
    if request.query_string:
        target_url += "?" + request.query_string
    
    log.info(f"LLM: {request.method} /v1/{path}")
    
    # Forward headers (except host and connection)
    headers = dict(request.headers)
    headers.pop("Host", None)
    headers.pop("Connection", None)
    headers["Authorization"] = f"Bearer {LLM_API_KEY}"
    
    try:
        async with aiohttp.ClientSession() as session:
            # Read request body
            body = await request.read()
            
            # Log raw request if enabled
            if LOG_RAW and body:
                log.info("=" * 80)
                log.info("RAW REQUEST JSON:")
                print(pretty_json(body))
                log.info("=" * 80)
            
            # Collect response for logging
            response_chunks = []
            
            async with session.request(
                method=request.method,
                url=target_url,
                headers=headers,
                data=body,
                timeout=aiohttp.ClientTimeout(total=300)
            ) as resp:
                # Stream response
                response = web.StreamResponse(
                    status=resp.status,
                    headers={k: v for k, v in resp.headers.items() 
                            if k.lower() not in ('transfer-encoding', 'content-encoding')}
                )
                await response.prepare(request)
                
                async for chunk in resp.content.iter_any():
                    if LOG_RAW:
                        response_chunks.append(chunk)
                    await response.write(chunk)
                
                await response.write_eof()
                
                # Log raw response
                if LOG_RAW and response_chunks:
                    full_response = b''.join(response_chunks)
                    log.info("=" * 80)
                    log.info("RAW RESPONSE JSON:")
                    print(pretty_json(full_response))
                    log.info("=" * 80)
                
                return response
                
    except asyncio.TimeoutError:
        return web.json_response({"error": "LLM request timeout"}, status=504)
    except Exception as e:
        log.error(f"LLM proxy error: {e}")
        return web.json_response({"error": "Proxy error", "message": str(e)}, status=502)


# ============ ZAI SEARCH CONFIG ============

SEARCH_CONFIG_FILE = "/data/search_config.json"

DEFAULT_SEARCH_CONFIG = {
    "mode": "coding",          # "coding" or "legacy"
    "model": "glm-4.7-flash",  # model for coding mode
    "count": 10,               # number of results
    "recency_filter": "noLimit",  # oneDay, oneWeek, oneMonth, oneYear, noLimit
    "timeout": 120,
    "response_model": ""       # model for final response after search (empty = use main model)
}


def load_search_config() -> dict:
    """Load search config from shared volume"""
    try:
        if os.path.exists(SEARCH_CONFIG_FILE):
            with open(SEARCH_CONFIG_FILE) as f:
                saved = json.load(f)
                return {**DEFAULT_SEARCH_CONFIG, **saved}
    except Exception as e:
        log.warning(f"Failed to load search config: {e}")
    return DEFAULT_SEARCH_CONFIG.copy()


def save_search_config(config: dict):
    """Save search config to shared volume"""
    os.makedirs(os.path.dirname(SEARCH_CONFIG_FILE), exist_ok=True)
    with open(SEARCH_CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


async def zai_search_coding(query: str, config: dict) -> tuple[int, dict]:
    """ZAI search via Coding Plan (Chat Completions + tools)"""
    url = "https://api.z.ai/api/coding/paas/v4/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ZAI_API_KEY}"
    }
    body = {
        "model": config.get("model", "glm-4.7-flash"),
        "messages": [{"role": "user", "content": query}],
        "stream": False,
        "tools": [{
            "type": "web_search",
            "web_search": {
                "enable": True,
                "search_engine": "search-prime",
                "search_result": True,
                "count": config.get("count", 10),
                "search_recency_filter": config.get("recency_filter", "noLimit")
            }
        }]
    }
    timeout = aiohttp.ClientTimeout(total=config.get("timeout", 120))
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=body, headers=headers, timeout=timeout) as resp:
            try:
                data = await resp.json()
            except:
                raw = await resp.text()
                log.error(f"ZAI coding: failed to parse JSON, status={resp.status}, raw={raw[:200]}")
                data = {"raw": raw}
            
            log.info(f"ZAI coding: status={resp.status}, has_choices={'choices' in data}, has_web_search={'web_search' in data}, results={len(data.get('web_search', []))}")
            
            # Normalize response to match what core/tools/web.py expects
            if resp.status == 200 and "choices" in data:
                web_results = data.get("web_search", [])
                normalized = []
                for r in web_results:
                    normalized.append({
                        "title": r.get("title", ""),
                        "link": r.get("link", ""),
                        "content": r.get("content", ""),
                        "refer": r.get("refer", "")
                    })
                return resp.status, {
                    "search_result": normalized,
                    "ai_summary": data["choices"][0]["message"].get("content", ""),
                    "usage": data.get("usage", {})
                }
            return resp.status, data


async def zai_search_legacy(query: str, config: dict) -> tuple[int, dict]:
    """ZAI search via legacy separate endpoint"""
    url = "https://api.z.ai/api/paas/v4/web_search"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ZAI_API_KEY}"
    }
    body = {
        "search_engine": "search-prime",
        "search_query": query,
        "count": config.get("count", 10)
    }
    timeout = aiohttp.ClientTimeout(total=config.get("timeout", 60))
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=body, headers=headers, timeout=timeout) as resp:
            try:
                data = await resp.json()
            except:
                data = {"raw": await resp.text()}
            return resp.status, data


async def zai_search(request: web.Request) -> web.Response:
    """Z.AI Web Search: /zai/search?q=..."""
    if not ZAI_API_KEY:
        return web.json_response({"error": "ZAI not configured"}, status=500)
    
    query = request.query.get("q", "")
    config = load_search_config()
    mode = config.get("mode", "coding")
    
    log.info(f'ZAI search ({mode}): "{query[:50]}..."')
    
    try:
        if mode == "coding":
            status, data = await zai_search_coding(query, config)
        else:
            status, data = await zai_search_legacy(query, config)
        return web.json_response(data, status=status)
    except asyncio.TimeoutError:
        log.error("ZAI search timeout")
        return web.json_response({"error": "Search timeout"}, status=504)
    except Exception as e:
        log.error(f"ZAI error: {e}")
        return web.json_response({"error": "ZAI request failed", "message": str(e)}, status=502)


async def zai_read(request: web.Request) -> web.Response:
    """Z.AI Web Reader: /zai/read?url=..."""
    if not ZAI_API_KEY:
        return web.json_response({"error": "ZAI not configured"}, status=500)
    
    page_url = request.query.get("url", "")
    log.info(f'ZAI read: "{page_url[:50]}..."')
    
    try:
        url = "https://api.z.ai/api/paas/v4/reader"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {ZAI_API_KEY}"
        }
        body = {
            "url": page_url,
            "return_format": "markdown",
            "retain_images": False,
            "timeout": 30
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                try:
                    data = await resp.json()
                except:
                    data = {"raw": await resp.text()}
                return web.json_response(data, status=resp.status)
    except Exception as e:
        log.error(f"ZAI error: {e}")
        return web.json_response({"error": "ZAI request failed", "message": str(e)}, status=502)


async def search_config_handler(request: web.Request) -> web.Response:
    """GET/PUT /zai/config - manage search configuration"""
    if request.method == "GET":
        return web.json_response(load_search_config())
    
    # PUT - update config
    try:
        body = await request.json()
        config = load_search_config()
        # Only allow known keys
        for key in ["mode", "model", "count", "recency_filter", "timeout", "response_model"]:
            if key in body:
                config[key] = body[key]
        # Validate mode
        if config["mode"] not in ("coding", "legacy"):
            return web.json_response({"error": "mode must be 'coding' or 'legacy'"}, status=400)
        save_search_config(config)
        log.info(f"Search config updated: {config}")
        return web.json_response({"success": True, **config})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)


async def not_found(request: web.Request) -> web.Response:
    """Handle unknown routes"""
    return web.json_response({
        "error": "Not found",
        "routes": ["/v1/*", "/zai/search?q=...", "/zai/read?url=...", "/health"]
    }, status=404)


def create_app() -> web.Application:
    """Create aiohttp application"""
    app = web.Application()
    
    # Routes
    app.router.add_get("/health", health)
    app.router.add_route("*", "/v1/{path:.*}", proxy_llm)
    app.router.add_get("/zai/search", zai_search)
    app.router.add_get("/zai/read", zai_read)
    app.router.add_route("*", "/zai/config", search_config_handler)
    
    # Catch-all for 404
    app.router.add_route("*", "/{path:.*}", not_found)
    
    return app


def main():
    log.info("Starting API proxy...")
    log.info(f"LLM endpoint: {'✓ configured' if LLM_BASE_URL else '✗ NOT SET'}")
    log.info(f"ZAI API: {'✓ configured' if ZAI_API_KEY else '✗ NOT SET'}")
    
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=PORT, print=lambda x: log.info(x))


if __name__ == "__main__":
    main()
