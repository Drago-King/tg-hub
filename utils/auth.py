"""
Simple owner-only auth guard.
Since this bot will eventually touch orders, messages, and calls,
nobody except OWNER_ID should ever be able to trigger a command.
"""
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes

from config import OWNER_ID
from utils.logger import log_event


def owner_only(handler_func):
    @wraps(handler_func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if user is None or user.id != OWNER_ID:
            log_event(f"BLOCKED unauthorized access attempt from user_id={getattr(user, 'id', 'unknown')}")
            if update.effective_message:
                await update.effective_message.reply_text(
                    "This bot is private and not available for public use."
                )
            return
        return await handler_func(update, context, *args, **kwargs)
    return wrapper
