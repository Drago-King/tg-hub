"""
Config specific to the ordering module.
Session files store logged-in browser state (cookies/localStorage) so
Playwright doesn't need your password each run.

SECURITY NOTE: session files are equivalent to being logged into your
account. Treat them like passwords:
  - never commit them to git
  - never upload/share them
  - data/sessions/ is already meant to be gitignored
"""
import os

ORDERING_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "sessions")
ORDERING_DATA_DIR = os.path.normpath(ORDERING_DATA_DIR)
os.makedirs(ORDERING_DATA_DIR, exist_ok=True)

SWIGGY_SESSION_FILE = os.path.join(ORDERING_DATA_DIR, "swiggy_session.json")
ZOMATO_SESSION_FILE = os.path.join(ORDERING_DATA_DIR, "zomato_session.json")

# How long to wait for page navigation/elements before giving up (ms)
DEFAULT_TIMEOUT_MS = 20000

# Run with a visible browser window the first time (login), headless after.
# On Termux there's no display, so first login must happen on a PC/laptop
# once, then copy the session file over to your phone.
HEADLESS = True

# --- Price comparison settings ---
# Both platforms get searched and their carts built before any total is
# trusted. If a restaurant isn't found on one platform, that platform is
# simply excluded from the comparison rather than treated as "0 cost".
COMPARISON_TIMEOUT_MS = 35000  # each platform gets its own budget to load/search
REQUIRE_BOTH_PLATFORMS_MATCH = False  # if True, only compares when same restaurant exists on both
