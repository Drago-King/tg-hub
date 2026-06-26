"""
Study module placeholder.

This shows the pattern every future module follows:
- define an owner_only handler
- expose a register(application) function that wires up commands
- the hub's module_registry.py auto-discovers this

Real version (RAG over your notes/PDFs) gets built next.
"""
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from utils.auth import owner_only
from utils.logger import log_event


@owner_only
async def study_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_event(f"/study called with args={context.args}")
    await update.effective_message.reply_text(
        "Study module placeholder — RAG-based Q&A over your notes coming soon."
    )


def register(application):
    application.add_handler(CommandHandler("study", study_command))
