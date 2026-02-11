"""HTTP server for core callbacks"""

import os
import logging
from aiohttp import web
from aiogram.types import FSInputFile, BufferedInputFile

from state import bot, resolve_username, get_all_usernames
from formatters import md_to_html

logger = logging.getLogger("bot.server")


async def handle_health(request):
    """Health check endpoint"""
    return web.json_response({"status": "ok"})


async def handle_send(request):
    """Send message to chat"""
    try:
        data = await request.json()
        chat_id = data.get("chat_id")
        text = data.get("text") or data.get("message", "")
        
        if not chat_id or not text:
            return web.json_response({"success": False, "error": "Missing chat_id or text"}, status=400)
        
        html_msg = md_to_html(text)
        result = await bot.send_message(chat_id, html_msg)
        logger.info(f"[server] Sent message to {chat_id}")
        
        return web.json_response({"success": True, "message_id": result.message_id})
    except Exception as e:
        logger.error(f"[server] Send error: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_send_file(request):
    """Send file to chat
    
    Accepts multipart form with:
    - chat_id: target chat
    - caption: optional caption
    - file: file bytes (from core, not a path)
    
    Security: Bot does NOT have workspace volume access.
    Core reads file and sends bytes here.
    """
    try:
        # Parse multipart form
        reader = await request.multipart()
        
        chat_id = None
        caption = ""
        file_content = None
        filename = "file"
        
        async for part in reader:
            if part.name == "chat_id":
                chat_id = int(await part.text())
            elif part.name == "caption":
                caption = await part.text()
            elif part.name == "file":
                filename = part.filename or "file"
                file_content = await part.read()
        
        if not chat_id or file_content is None:
            return web.json_response({"success": False, "error": "Missing chat_id or file"}, status=400)
        
        if len(file_content) > 50 * 1024 * 1024:  # 50MB limit
            return web.json_response({"success": False, "error": "File too large (max 50MB)"}, status=413)
        
        # Send using BufferedInputFile (from bytes, not path)
        file = BufferedInputFile(file_content, filename=filename)
        result = await bot.send_document(chat_id, file, caption=caption[:1024] if caption else None)
        logger.info(f"[server] Sent file {filename} ({len(file_content)} bytes) to {chat_id}")
        
        return web.json_response({"success": True, "message_id": result.message_id})
    except Exception as e:
        logger.error(f"[server] Send file error: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_send_dm(request):
    """Send private message to user"""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        text = data.get("text", "")
        
        if not user_id or not text:
            return web.json_response({"success": False, "error": "Missing user_id or text"}, status=400)
        
        html_msg = md_to_html(text)
        result = await bot.send_message(user_id, html_msg)
        logger.info(f"[server] Sent DM to {user_id}")
        
        return web.json_response({"success": True, "message_id": result.message_id})
    except Exception as e:
        logger.error(f"[server] Send DM error: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_edit_message(request):
    """Edit bot message"""
    try:
        data = await request.json()
        chat_id = data.get("chat_id")
        message_id = data.get("message_id")
        text = data.get("text", "")
        
        if not chat_id or not message_id or not text:
            return web.json_response({"success": False, "error": "Missing chat_id, message_id or text"}, status=400)
        
        html_msg = md_to_html(text)
        await bot.edit_message_text(html_msg, chat_id=chat_id, message_id=message_id)
        logger.info(f"[server] Edited message {message_id} in {chat_id}")
        
        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"[server] Edit error: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_delete_message(request):
    """Delete bot message"""
    try:
        data = await request.json()
        chat_id = data.get("chat_id")
        message_id = data.get("message_id")
        
        if not chat_id or not message_id:
            return web.json_response({"success": False, "error": "Missing chat_id or message_id"}, status=400)
        
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.info(f"[server] Deleted message {message_id} in {chat_id}")
        
        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"[server] Delete error: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


# Pending questions for ask_user tool
pending_questions: dict[str, dict] = {}


async def handle_ask_user(request):
    """Register a question waiting for user answer"""
    try:
        data = await request.json()
        question_id = data.get("question_id")
        chat_id = data.get("chat_id")
        user_id = data.get("user_id")
        question = data.get("question", "")
        
        if not all([question_id, chat_id, user_id, question]):
            return web.json_response({"success": False, "error": "Missing required fields"}, status=400)
        
        # Store pending question
        pending_questions[question_id] = {
            "chat_id": chat_id,
            "user_id": user_id,
            "question": question,
            "answer": None
        }
        
        # Send question to user
        html_msg = md_to_html(f"❓ {question}")
        await bot.send_message(chat_id, html_msg)
        logger.info(f"[server] Asked question {question_id} to {user_id}")
        
        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"[server] Ask error: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_get_answer(request):
    """Get answer to pending question"""
    try:
        question_id = request.match_info.get("question_id")
        
        if question_id not in pending_questions:
            return web.json_response({"success": False, "error": "Question not found"}, status=404)
        
        q = pending_questions[question_id]
        if q["answer"] is None:
            return web.json_response({"success": True, "answered": False})
        
        answer = q["answer"]
        del pending_questions[question_id]  # Clean up
        
        return web.json_response({"success": True, "answered": True, "answer": answer})
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=500)


def check_pending_answer(user_id: int, chat_id: int, text: str) -> bool:
    """Check if message is answer to pending question. Returns True if handled."""
    for qid, q in list(pending_questions.items()):
        if q["user_id"] == user_id and q["chat_id"] == chat_id and q["answer"] is None:
            q["answer"] = text
            logger.info(f"[server] Got answer for {qid}: {text[:50]}...")
            return True
    return False


async def handle_resolve_username(request):
    """Resolve @username to user_id from known users registry"""
    try:
        data = await request.json()
        username = data.get("username", "")
        
        if not username:
            return web.json_response({"success": False, "error": "Missing username"}, status=400)
        
        user_id = resolve_username(username)
        if user_id:
            return web.json_response({"success": True, "user_id": user_id, "username": username.lower().lstrip("@")})
        else:
            return web.json_response({"success": False, "error": f"Unknown user @{username.lstrip('@')}. User must have messaged the bot at least once."})
    except Exception as e:
        logger.error(f"[server] Resolve username error: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_known_users(request):
    """List all known username -> user_id mappings"""
    try:
        users = get_all_usernames()
        return web.json_response({"success": True, "users": users, "count": len(users)})
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=500)


def create_http_app() -> web.Application:
    """Create HTTP application"""
    app = web.Application()
    app.router.add_get("/health", handle_health)
    app.router.add_post("/send", handle_send)
    app.router.add_post("/send_file", handle_send_file)
    app.router.add_post("/send_dm", handle_send_dm)
    app.router.add_post("/edit", handle_edit_message)
    app.router.add_post("/delete", handle_delete_message)
    app.router.add_post("/ask", handle_ask_user)
    app.router.add_get("/answer/{question_id}", handle_get_answer)
    app.router.add_post("/resolve_username", handle_resolve_username)
    app.router.add_get("/known_users", handle_known_users)
    return app
