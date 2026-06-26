"""
On Railway, there's no way to manually drop a session file into the
container filesystem the way you could on Termux or a PC. Instead,
session files are stored as base64-encoded environment variables and
written to disk once when the bot starts up.

Setup (after running login_setup.py locally on a PC):

    base64 -w 0 data/sessions/swiggy_session.json
    # copy the output

On Railway dashboard -> Variables, add:
    SWIGGY_SESSION_B64 = <paste the base64 string>
    ZOMATO_SESSION_B64 = <paste the base64 string>

This module runs automatically at bot startup (called from main.py) and
writes the decoded files to the same paths swiggy.py/zomato.py expect.
If the env vars aren't set, it just skips silently — useful for local
dev where you already have the real files on disk.
"""
import os
import base64

from modules.ordering.config import SWIGGY_SESSION_FILE, ZOMATO_SESSION_FILE
from utils.logger import log_event

SESSION_ENV_MAP = {
    "SWIGGY_SESSION_B64": SWIGGY_SESSION_FILE,
    "ZOMATO_SESSION_B64": ZOMATO_SESSION_FILE,
}


def restore_sessions_from_env():
    for env_var, target_path in SESSION_ENV_MAP.items():
        b64_value = os.environ.get(env_var)
        if not b64_value:
            continue  # not set — likely local dev with real files already present
        try:
            decoded = base64.b64decode(b64_value)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "wb") as f:
                f.write(decoded)
            log_event(f"Restored session file from {env_var} -> {target_path}")
        except Exception as e:
            log_event(f"Failed to restore session from {env_var}: {e}")
