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
MODEL_NAME = read_secret("model_name") or "gpt-4"  # Model for classifier


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


async def zai_request(endpoint: str, body: dict) -> tuple[int, dict]:
    """Make request to Z.AI API"""
    url = f"https://api.z.ai/api/paas/v4/{endpoint}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ZAI_API_KEY}"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                try:
                    data = await resp.json()
                except:
                    data = {"raw": await resp.text()}
                return resp.status, data
    except Exception as e:
        raise Exception(f"ZAI request failed: {e}")


async def zai_search(request: web.Request) -> web.Response:
    """Z.AI Web Search: /zai/search?q=..."""
    if not ZAI_API_KEY:
        return web.json_response({"error": "ZAI not configured"}, status=500)
    
    query = request.query.get("q", "")
    log.info(f'ZAI search: "{query[:50]}..."')
    
    try:
        status, data = await zai_request("web_search", {
            "search_engine": "search-prime",
            "search_query": query,
            "count": 10
        })
        return web.json_response(data, status=status)
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
        status, data = await zai_request("reader", {
            "url": page_url,
            "return_format": "markdown",
            "retain_images": False,
            "timeout": 30
        })
        return web.json_response(data, status=status)
    except Exception as e:
        log.error(f"ZAI error: {e}")
        return web.json_response({"error": "ZAI request failed", "message": str(e)}, status=502)


async def classify_response(request: web.Request) -> web.Response:
    """
    LLM-based classifier: should the userbot respond to this message?
    Uses structured output to get a simple yes/no decision with reasoning.
    """
    if not LLM_BASE_URL:
        return web.json_response({"error": "LLM not configured"}, status=500)
    
    try:
        data = await request.json()
    except:
        return web.json_response({"error": "Invalid JSON"}, status=400)
    
    messages = data.get("messages", [])  # Last N messages for context
    current_message = data.get("current_message", "")
    sender_name = data.get("sender_name", "user")
    chat_type = data.get("chat_type", "group")  # "private" or "group"
    bot_username = data.get("bot_username", "")
    is_reply_to_bot = data.get("is_reply_to_bot", False)
    is_mention = data.get("is_mention", False)
    
    # Build context string from recent messages
    context_lines = []
    for msg in messages[-10:]:  # Last 10 messages
        author = msg.get("author", "unknown")
        text = msg.get("text", "")[:200]  # Truncate long messages
        context_lines.append(f"{author}: {text}")
    
    context = "\n".join(context_lines) if context_lines else "(no previous context)"
    
    # Classifier prompt
    classifier_prompt = f"""You are a response classifier for a Telegram userbot. 
Analyze the conversation and decide if the bot should respond to the latest message.

CONTEXT (recent messages):
{context}

CURRENT MESSAGE from {sender_name}:
"{current_message}"

METADATA:
- Chat type: {chat_type}
- Bot username: @{bot_username}
- Is reply to bot: {is_reply_to_bot}
- Is @mention of bot: {is_mention}

RESPOND with JSON only:
{{"should_respond": true/false, "confidence": 0.0-1.0, "reason": "brief explanation"}}

GUIDELINES for should_respond=true:
- Direct questions or requests for help
- Technical discussions where bot can add value
- When explicitly mentioned or replied to
- Interesting conversations where bot has relevant knowledge

GUIDELINES for should_respond=false:
- Casual chat between humans (greetings, jokes, small talk)
- Messages not directed at anyone specific
- Spam, ads, or off-topic content
- When someone else is clearly being addressed
- Very short messages like "ok", "lol", "да", "+1"
- Bot already responded recently to similar topic

Respond ONLY with valid JSON, no other text."""

    # Make fast LLM call with low tokens
    llm_payload = {
        "model": data.get("model", MODEL_NAME),
        "messages": [
            {"role": "system", "content": "You are a response classifier. Output only valid JSON."},
            {"role": "user", "content": classifier_prompt}
        ],
        "max_tokens": 200,
        "temperature": 0.1,  # Low temperature for consistent decisions
    }
    
    # Note: response_format=json_object not always supported, relying on prompt instead
    
    target_url = LLM_BASE_URL.rstrip("/v1").rstrip("/") + "/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LLM_API_KEY}"
    }
    
    log.info(f"Classifier: {chat_type} from {sender_name}: {current_message[:50]}...")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                target_url,
                json=llm_payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)  # Fast timeout
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    log.error(f"Classifier LLM error: {resp.status} - {error_text[:200]}")
                    # Fallback: respond if mentioned or replied to
                    return web.json_response({
                        "should_respond": is_mention or is_reply_to_bot,
                        "confidence": 0.5,
                        "reason": "LLM error, using fallback",
                        "fallback": True
                    })
                
                result = await resp.json()
                
                # Debug log
                log.info(f"LLM response: {str(result)[:500]}")
                
                # Extract content from various response formats
                content = None
                if "choices" in result and result["choices"]:
                    choice = result["choices"][0]
                    if "message" in choice and choice["message"]:
                        content = choice["message"].get("content")
                    elif "text" in choice:
                        content = choice["text"]
                
                if not content:
                    # Fallback for unusual response formats
                    log.warning(f"No content in LLM response, using fallback")
                    return web.json_response({
                        "should_respond": is_mention or is_reply_to_bot,
                        "confidence": 0.5,
                        "reason": "No content in LLM response",
                        "fallback": True
                    })
                
                # Parse JSON response
                try:
                    # Clean content - remove markdown code blocks if present
                    clean_content = content.strip()
                    if clean_content.startswith("```"):
                        # Remove ```json and ``` markers
                        lines = clean_content.split("\n")
                        clean_content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
                    
                    decision = json.loads(clean_content)
                    should_respond = decision.get("should_respond", False)
                    confidence = decision.get("confidence", 0.5)
                    reason = decision.get("reason", "no reason")
                    
                    log.info(f"Classifier decision: {should_respond} ({confidence:.0%}) - {reason}")
                    
                    return web.json_response({
                        "should_respond": should_respond,
                        "confidence": confidence,
                        "reason": reason
                    })
                except json.JSONDecodeError as e:
                    # Try to extract yes/no from text
                    log.warning(f"JSON parse error: {e}, content: {content[:200]}")
                    content_lower = content.lower()
                    should_respond = "true" in content_lower or "\"should_respond\": true" in content_lower
                    return web.json_response({
                        "should_respond": should_respond,
                        "confidence": 0.5,
                        "reason": f"Parsed from text: {content[:80]}...",
                        "parse_fallback": True
                    })
                    
    except asyncio.TimeoutError:
        log.warning("Classifier timeout, using fallback")
        return web.json_response({
            "should_respond": is_mention or is_reply_to_bot,
            "confidence": 0.5,
            "reason": "Timeout, using fallback",
            "fallback": True
        })
    except Exception as e:
        log.error(f"Classifier error: {e}")
        return web.json_response({
            "should_respond": is_mention or is_reply_to_bot,
            "confidence": 0.5,
            "reason": f"Error: {e}",
            "fallback": True
        })


async def not_found(request: web.Request) -> web.Response:
    """Handle unknown routes"""
    return web.json_response({
        "error": "Not found",
        "routes": ["/v1/*", "/zai/search?q=...", "/zai/read?url=...", "/classify", "/health"]
    }, status=404)


def create_app() -> web.Application:
    """Create aiohttp application"""
    app = web.Application()
    
    # Routes
    app.router.add_get("/health", health)
    app.router.add_route("*", "/v1/{path:.*}", proxy_llm)
    app.router.add_get("/zai/search", zai_search)
    app.router.add_get("/zai/read", zai_read)
    app.router.add_post("/classify", classify_response)
    
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
