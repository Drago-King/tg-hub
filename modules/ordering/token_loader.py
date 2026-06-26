"""
Writes data/swiggy_mcp_tokens.json from the SWIGGY_MCP_TOKENS_B64 env
var on startup, so swiggy_mcp.py can read it as a normal file. Mirrors
the same pattern used for the (now-removed) Playwright cookie sessions.
"""
import os
import base64

from utils.logger import log_event

TOKENS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "swiggy_mcp_tokens.json")
TOKENS_FILE = os.path.normpath(TOKENS_FILE)


def restore_swiggy_token_from_env():
    b64_value = os.environ.get("SWIGGY_MCP_TOKENS_B64")
    if not b64_value:
        return  # not set — fine for local dev if the file already exists
    try:
        decoded = base64.b64decode(b64_value)
        os.makedirs(os.path.dirname(TOKENS_FILE), exist_ok=True)
        with open(TOKENS_FILE, "wb") as f:
            f.write(decoded)
        log_event(f"Restored Swiggy MCP token -> {TOKENS_FILE}")
    except Exception as e:
        log_event(f"Failed to restore Swiggy MCP token: {e}")
