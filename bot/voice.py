"""Voice message transcription via Faster-Whisper ASR API"""

import os
import json
import aiohttp
from config import ASR_URL, ASR_TIMEOUT, ASR_LANGUAGE


def _get_asr_config() -> dict:
    """Get ASR config from shared file or env defaults"""
    config = {"url": ASR_URL, "timeout": ASR_TIMEOUT, "language": ASR_LANGUAGE, "enabled": bool(ASR_URL)}
    try:
        path = "/data/asr_config.json"
        if os.path.exists(path):
            with open(path) as f:
                saved = json.load(f)
                config.update(saved)
    except:
        pass
    return config


async def transcribe_voice(file_url: str, duration: int) -> str:
    """Download voice from Telegram and transcribe via Faster-Whisper API
    
    Args:
        file_url: Telegram file URL
        duration: Voice duration in seconds
    
    Returns:
        Transcribed text
    
    Raises:
        Exception on failure
    """
    cfg = _get_asr_config()
    asr_url = cfg.get("url", "")
    if not asr_url or not cfg.get("enabled", True):
        raise Exception("ASR not configured or disabled")

    asr_timeout = cfg.get("timeout", 60)
    asr_language = cfg.get("language", "ru")

    timeout = aiohttp.ClientTimeout(total=asr_timeout)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        # 1. Download OGG from Telegram
        async with session.get(file_url) as resp:
            if resp.status != 200:
                raise Exception(f"Failed to download audio: {resp.status}")
            audio_data = await resp.read()

        print(f"[voice] Downloaded {len(audio_data) / 1024:.1f}KB, duration: {duration}s")

        # 2. Send to Faster-Whisper API (multipart/form-data)
        form = aiohttp.FormData()
        form.add_field("file", audio_data, filename="voice.ogg", content_type="audio/ogg")
        if asr_language:
            form.add_field("language", asr_language)

        async with session.post(f"{asr_url}/api/v1/transcribe", data=form) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise Exception(f"ASR error: {resp.status} {error_text[:200]}")
            result = await resp.json()

    # 3. Extract text
    full_text = result.get("full_text", "")
    if not full_text:
        segments = result.get("segments", [])
        full_text = " ".join(s.get("text", "") for s in segments).strip()

    if not full_text:
        raise Exception("Empty ASR response")

    model = result.get("model", "?")
    proc_time = result.get("processing_time", 0)
    print(f'[voice] Transcribed ({model}, {proc_time:.1f}s): "{full_text[:80]}{"..." if len(full_text) > 80 else ""}"')

    return full_text


async def check_asr_health() -> dict:
    """Check ASR server health. Returns status dict or error."""
    if not ASR_URL:
        return {"status": "disabled", "url": ""}
    
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{ASR_URL}/health/ready") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    data["url"] = ASR_URL
                    return data
                return {"status": "error", "url": ASR_URL, "http_status": resp.status}
    except Exception as e:
        return {"status": "error", "url": ASR_URL, "error": str(e)}
