"""Text formatting utilities"""

import re
import html


def escape_html(text: str) -> str:
    return html.escape(text)


def md_to_html(text: str) -> str:
    """Convert Markdown to Telegram HTML"""
    if not text:
        return ""
    
    # Protect code blocks
    code_blocks = []
    def save_code(m):
        idx = len(code_blocks)
        lang = m.group(1) or ""
        code = m.group(2).strip()
        lang_attr = f' class="language-{lang}"' if lang else ""
        block = f"<pre><code{lang_attr}>{escape_html(code)}</code></pre>"
        code_blocks.append(block)
        return f"\x00CODE{idx}\x00"
    
    result = re.sub(r'```(\w*)\n?([\s\S]*?)```', save_code, text)
    
    # Protect inline code
    inline_codes = []
    def save_inline(m):
        idx = len(inline_codes)
        inline_codes.append(f"<code>{escape_html(m.group(1))}</code>")
        return f"\x00INLINE{idx}\x00"
    
    result = re.sub(r'`([^`]+)`', save_inline, result)
    
    # Protect URLs
    urls = []
    def save_url(m):
        idx = len(urls)
        urls.append(m.group(0))
        return f"\x00URL{idx}\x00"
    
    result = re.sub(r'https?://[^\s<>]+', save_url, result)
    
    # Protect @mentions
    mentions = []
    def save_mention(m):
        idx = len(mentions)
        mentions.append(m.group(0))
        return f"\x00MENTION{idx}\x00"
    
    result = re.sub(r'@[\w_]+', save_mention, result)
    
    # Escape HTML
    result = escape_html(result)
    
    # Apply markdown formatting
    result = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', result)
    result = re.sub(r'\*(.+?)\*', r'<i>\1</i>', result)
    result = re.sub(r'__(.+?)__', r'<b>\1</b>', result)
    result = re.sub(r'_(.+?)_', r'<i>\1</i>', result)
    result = re.sub(r'~~(.+?)~~', r'<s>\1</s>', result)
    
    # Restore protected content
    for i, block in enumerate(code_blocks):
        result = result.replace(f"\x00CODE{i}\x00", block)
    for i, code in enumerate(inline_codes):
        result = result.replace(f"\x00INLINE{i}\x00", code)
    for i, url in enumerate(urls):
        result = result.replace(f"\x00URL{i}\x00", url)
    for i, mention in enumerate(mentions):
        result = result.replace(f"\x00MENTION{i}\x00", mention)
    
    return result


def split_message(text: str, max_len: int = 4000) -> list[str]:
    """Split long message into parts"""
    if not text:
        return [""]
    if len(text) <= max_len:
        return [text]
    
    parts = []
    current = ""
    
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > max_len:
            if current:
                parts.append(current)
            current = line
        else:
            current += ("\n" if current else "") + line
    
    if current:
        parts.append(current)
    
    return parts


def clean_model_artifacts(text: str) -> str:
    """Remove LLM artifacts like </final> tags and <thinking> blocks"""
    import re
    # Remove thinking blocks with content
    text = re.sub(r'<thinking>[\s\S]*?</thinking>', '', text, flags=re.IGNORECASE)
    # Remove standalone tags
    text = re.sub(r'</?(final|response|answer|output|reply|thinking)>', '', text, flags=re.IGNORECASE)
    return text.strip()
