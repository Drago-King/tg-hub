"""
Central config for the personal automation hub.
All secrets come from environment variables — never hardcode tokens.
"""
import os

# --- Required ---
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# Your Telegram numeric user ID (get it from @userinfobot on Telegram).
# Only this ID will be allowed to use the bot.
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

# --- Paths ---
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
LOG_FILE = os.path.join(DATA_DIR, "activity.log")
DB_FILE = os.path.join(DATA_DIR, "hub.db")

# --- Behavior ---
# If True, every action from a module requires an explicit "confirm" reply
# before anything irreversible happens (placing orders, sending messages, calls).
REQUIRE_CONFIRMATION = True

os.makedirs(DATA_DIR, exist_ok=True)

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN is not set. Run: export BOT_TOKEN='your_token_here'"
    )
if OWNER_ID == 0:
    raise RuntimeError(
        "OWNER_ID is not set. Message @userinfobot on Telegram to get your ID, "
        "then run: export OWNER_ID='your_id_here'"
    )
