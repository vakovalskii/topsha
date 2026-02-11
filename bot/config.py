"""Bot configuration and constants"""

import os
from dataclasses import dataclass


def read_secret(name: str, env_key: str) -> str:
    """Read secret from Docker Secrets or env"""
    paths = [f"/run/secrets/{name}", f"/run/secrets/{name}.txt"]
    for path in paths:
        if os.path.exists(path):
            try:
                with open(path) as f:
                    value = f.read().strip()
                    if value:
                        return value
            except:
                pass
    return os.getenv(env_key, "")


# Secrets & Environment
TELEGRAM_TOKEN = read_secret("telegram_token", "TELEGRAM_TOKEN")
MODEL = read_secret("model_name", "MODEL_NAME") or "gpt-4"
CORE_URL = os.getenv("CORE_URL", "http://core:4000")
PROXY_URL = os.getenv("PROXY_URL", "http://proxy:3200")
BOT_PORT = int(os.getenv("BOT_PORT", "4001"))
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT_USERS", "10"))
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))


@dataclass
class Config:
    # Rate limits
    global_min_interval: float = 0.2
    group_min_interval: float = 5.0
    max_retries: int = 3
    
    # Messages
    max_length: int = 4000
    
    # Bot behavior
    typing_interval: float = 4.0
    think_delay_min: float = 0.5
    think_delay_max: float = 2.0
    ignore_chance: float = 0.05
    ignore_private_chance: float = 0.02
    
    # Reactions
    reaction_chance: float = 0.15
    reaction_min_interval: float = 5.0
    reaction_min_text_length: int = 10
    
    # Triggers
    random_reply_chance: float = 0.08
    min_text_for_random: int = 30
    
    # Users
    max_concurrent: int = MAX_CONCURRENT
    
    # AFK
    afk_default_minutes: int = 30
    afk_max_minutes: int = 480


CONFIG = Config()

# ASR (Speech-to-Text) settings
ASR_URL = os.getenv("ASR_URL", "")  # empty = disabled
ASR_MAX_DURATION = int(os.getenv("ASR_MAX_DURATION", "120"))  # seconds
ASR_TIMEOUT = int(os.getenv("ASR_TIMEOUT", "60"))  # seconds
ASR_LANGUAGE = os.getenv("ASR_LANGUAGE", "ru")

# Reactions lists
POSITIVE_REACTIONS = ['👍', '❤️', '🔥', '🎉', '💯', '🏆', '👏', '😍', '🤗']
NEGATIVE_REACTIONS = ['👎', '💩', '🤡', '🗿', '😴', '🤮']
NEUTRAL_REACTIONS = ['👀', '🤔', '😈', '🤯', '😱']
ALL_REACTIONS = POSITIVE_REACTIONS + NEUTRAL_REACTIONS + NEGATIVE_REACTIONS
DONE_EMOJIS = ['👍', '✅', '🔥', '💯', '🎉', '👏', '🏆']

# Anti-loop settings
USERBOT_ID = 6009985969  # @markkovalskii userbot
MAX_BOT_REPLIES = 3
BOT_COOLDOWN = 120
