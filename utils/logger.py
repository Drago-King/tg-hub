"""
Lightweight activity logger.
Keeps a running log of every command/action, same pattern as EchoFlix's
admin activity log — useful for debugging and for reviewing what the
bot did while you weren't watching (especially once ordering/calls are live).
"""
import datetime
import os

from config import LOG_FILE


def log_event(message: str) -> None:
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}\n"
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)
    print(line, end="")


def read_recent_logs(n: int = 20) -> str:
    if not os.path.exists(LOG_FILE):
        return "No activity logged yet."
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    return "".join(lines[-n:]) or "No activity logged yet."
