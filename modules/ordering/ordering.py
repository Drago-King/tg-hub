"""
Ordering module — Telegram-facing entry point.

Usage in Telegram:
    /order <restaurant name> | <item 1>, <item 2>

Example:
    /order Sangeetha Veg Restaurant | Veg Biryani, Gobi Manchurian

Flow:
    1. Searches both Swiggy and Zomato in parallel
    2. Builds a cart on whichever platforms have the restaurant/items
    3. Reports both totals + which is cheaper
    4. Sends a button to open the cheaper cart's URL
    5. NEVER places the order — you always complete checkout yourself
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler

from utils.auth import owner_only
from utils.logger import log_event
from modules.ordering.compare import compare_platforms


@owner_only
async def order_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_text = " ".join(context.args)
    if "|" not in raw_text:
        await update.effective_message.reply_text(
            "Usage:\n/order <restaurant name> | <item1>, <item2>\n\n"
            "Example:\n/order Sangeetha Veg Restaurant | Veg Biryani, Gobi Manchurian"
        )
        return

    restaurant_part, items_part = raw_text.split("|", 1)
    restaurant_name = restaurant_part.strip()
    items = [i.strip() for i in items_part.split(",") if i.strip()]

    if not restaurant_name or not items:
        await update.effective_message.reply_text(
            "Couldn't parse restaurant name or items. Check the format and try again."
        )
        return

    status_msg = await update.effective_message.reply_text(
        f"Searching '{restaurant_name}' for {', '.join(items)} on Swiggy + Zomato..."
    )

    log_event(f"/order requested: restaurant='{restaurant_name}' items={items}")

    try:
        results, cheapest = await compare_platforms(restaurant_name, items)
    except Exception as e:
        log_event(f"/order comparison failed: {e}")
        await status_msg.edit_text(f"Something went wrong while comparing: {e}")
        return

    summary_lines = [r.summary_line() for r in results]
    summary_text = "\n".join(summary_lines)

    if cheapest is None:
        await status_msg.edit_text(
            f"Couldn't build a cart on either platform:\n\n{summary_text}\n\n"
            "Try a more exact restaurant name, or check it's available on either app."
        )
        return

    other = [r for r in results if r.platform != cheapest.platform and r.found]
    savings_note = ""
    if other and other[0].grand_total:
        diff = abs(other[0].grand_total - cheapest.grand_total)
        savings_note = f"\n\nCheaper by ₹{diff:.2f} on {cheapest.platform.title()}."

    reply_text = f"{summary_text}{savings_note}\n\nTap below to open the cheaper cart and complete checkout yourself."

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Open {cheapest.platform.title()} cart", url=cheapest.cart_url)]
    ])

    await status_msg.edit_text(reply_text, reply_markup=keyboard)

    # Send screenshot of the cheaper cart so you can sanity-check before tapping through
    if cheapest.screenshot_path:
        try:
            with open(cheapest.screenshot_path, "rb") as f:
                await update.effective_message.reply_photo(f, caption=f"{cheapest.platform.title()} cart preview")
        except Exception as e:
            log_event(f"Could not send cart screenshot: {e}")

    log_event(f"/order result: cheapest={cheapest.platform} total={cheapest.grand_total}")


def register(application):
    application.add_handler(CommandHandler("order", order_command))
