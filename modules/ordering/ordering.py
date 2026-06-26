"""
Ordering module — Telegram-facing entry point (deep link version).

Usage in Telegram:
    /order <restaurant name>

Example:
    /order Sangeetha Veg Restaurant

Flow:
    1. Builds direct search links for both Swiggy and Zomato
    2. Sends both as tappable buttons
    3. You open whichever app, search result, build your cart, and
       complete checkout yourself — no automation, no bot-detection risk
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler

from utils.auth import owner_only
from utils.logger import log_event
from modules.ordering.deeplinks import build_links
from modules.ordering import swiggy_mcp


@owner_only
async def swiggy_test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Diagnostic command: confirms the Swiggy MCP token + connection work."""
    await update.effective_message.reply_text("Connecting to Swiggy MCP server...")
    try:
        tools = await swiggy_mcp.list_tools()
        await update.effective_message.reply_text(
            f"Connected. Available tools:\n" + "\n".join(f"- {t}" for t in tools)
        )
        log_event(f"/swiggytest succeeded, {len(tools)} tools found")
    except Exception as e:
        await update.effective_message.reply_text(f"Connection failed: {e}")
        log_event(f"/swiggytest failed: {e}")


@owner_only
async def order_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    restaurant_name = " ".join(context.args).strip()

    if not restaurant_name:
        await update.effective_message.reply_text(
            "Usage:\n/order <restaurant name>\n\n"
            "Example:\n/order Sangeetha Veg Restaurant\n\n"
            "I'll send you direct search links for Swiggy and Zomato — "
            "open whichever has the better price and finish checkout there."
        )
        return

    log_event(f"/order requested: restaurant='{restaurant_name}'")

    links = build_links(restaurant_name)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Search on {link.platform.title()}", url=link.url)]
        for link in links
    ])

    await update.effective_message.reply_text(
        f"Search links for '{restaurant_name}':\n\n"
        "Tap to open each app, compare the total (items + fees), "
        "and complete checkout on whichever is cheaper.",
        reply_markup=keyboard,
    )

    log_event(f"/order links sent for '{restaurant_name}'")


def register(application):
    application.add_handler(CommandHandler("order", order_command))
    application.add_handler(CommandHandler("swiggytest", swiggy_test_command))
