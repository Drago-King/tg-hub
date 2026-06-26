"""
Personal Automation Hub — Telegram bot entry point.

Core commands live here (/start, /help, /logs).
Everything else (ordering, calls, study) is a module in modules/
that gets auto-registered by module_registry.py.

Run:
    export BOT_TOKEN="your_token"
    export OWNER_ID="your_telegram_user_id"
    python main.py
"""
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from config import BOT_TOKEN
from utils.auth import owner_only
from utils.logger import log_event, read_recent_logs
from module_registry import register_all_modules, MODULE_NAMES
from modules.ordering.token_loader import restore_swiggy_token_from_env


@owner_only
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_event(f"/start by {update.effective_user.id}")
    await update.effective_message.reply_text(
        "Personal Automation Hub is online.\n\n"
        "Use /help to see available commands."
    )


@owner_only
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    modules_list = "\n".join(f"  • {m}" for m in MODULE_NAMES) or "  (none loaded yet)"
    await update.effective_message.reply_text(
        "Core commands:\n"
        "/start - check bot is alive\n"
        "/help - this message\n"
        "/logs - show recent activity log\n\n"
        f"Loaded modules:\n{modules_list}"
    )


@owner_only
async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(f"Recent activity:\n\n{read_recent_logs(20)}")


def main():
    log_event("Hub starting up...")
    restore_swiggy_token_from_env()
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("logs", logs_command))

    register_all_modules(application)

    log_event("Hub is now polling for updates.")
    application.run_polling()


if __name__ == "__main__":
    main()
