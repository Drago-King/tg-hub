"""
Real Swiggy ordering flow via MCP, following Swiggy's own documented
tool sequencing exactly:

    get_addresses -> search_restaurants -> search_menu ->
    update_food_cart -> get_food_cart -> [explicit confirm] -> place_food_order

State is kept per-chat in context.user_data["swiggy_order"] since this
is a genuinely multi-step conversation (pick address, pick restaurant,
pick dish, confirm cart, confirm order) rather than a single command.

Hard safety rules enforced here, matching Swiggy's own tool descriptions:
    - place_food_order is NEVER called without the user explicitly
      confirming after seeing the real cart total and address
    - orders >= ₹1000 are blocked (Swiggy MCP beta restriction)
    - cancellation requests are redirected to Swiggy customer care,
      since there's no cancel tool
"""
import json

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from utils.auth import owner_only
from utils.logger import log_event
from modules.ordering import swiggy_mcp

ORDER_LIMIT_PAISE = 1000 * 100  # ₹1000, Swiggy MCP beta restriction


def _state(context: ContextTypes.DEFAULT_TYPE) -> dict:
    if "swiggy_order" not in context.user_data:
        context.user_data["swiggy_order"] = {}
    return context.user_data["swiggy_order"]


@owner_only
async def swiggy_order_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point: /swiggyorder <dish or restaurant query>"""
    query = " ".join(context.args).strip()
    if not query:
        await update.effective_message.reply_text(
            "Usage: /swiggyorder <restaurant or dish>\n\n"
            "Example: /swiggyorder veg biryani"
        )
        return

    state = _state(context)
    state.clear()
    state["query"] = query

    await update.effective_message.reply_text("Fetching your saved addresses...")

    try:
        result = await swiggy_mcp.call_tool("get_addresses", {})
        data = swiggy_mcp.extract_structured_data(result)
    except Exception as e:
        await update.effective_message.reply_text(f"Couldn't fetch addresses: {e}")
        log_event(f"/swiggyorder get_addresses failed: {e}")
        return

    addresses = data.get("addresses") or data.get("data") or []
    if not addresses:
        await update.effective_message.reply_text(
            "No saved addresses found on your Swiggy account. "
            "Add one in the Swiggy app first, then try again."
        )
        return

    state["addresses"] = addresses

    buttons = []
    for addr in addresses[:8]:  # cap to keep the keyboard usable
        addr_id = addr.get("id") or addr.get("addressId")
        label = addr.get("name") or addr.get("addressLine1") or addr.get("annotation") or "Address"
        label = str(label)[:40]
        buttons.append([InlineKeyboardButton(label, callback_data=f"swg_addr:{addr_id}")])

    await update.effective_message.reply_text(
        "Which address should this be delivered to?",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def handle_address_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    address_id = query.data.split(":", 1)[1]

    state = _state(context)
    state["address_id"] = address_id

    await query.edit_message_text(f"Searching for '{state['query']}'...")

    try:
        result = await swiggy_mcp.call_tool(
            "search_restaurants", {"addressId": address_id, "query": state["query"]}
        )
        data = swiggy_mcp.extract_structured_data(result)
    except Exception as e:
        await query.message.reply_text(f"Search failed: {e}")
        log_event(f"search_restaurants failed: {e}")
        return

    restaurants = data.get("restaurants") or data.get("data") or []
    open_restaurants = [r for r in restaurants if r.get("availabilityStatus") == "OPEN"]

    if not open_restaurants:
        await query.message.reply_text(
            f"No open restaurants found for '{state['query']}'. Try a different search."
        )
        return

    state["restaurants"] = {str(r.get("restaurantId") or r.get("id")): r for r in open_restaurants}

    buttons = []
    for r in open_restaurants[:8]:
        rid = r.get("restaurantId") or r.get("id")
        name = r.get("name", "Restaurant")
        distance = r.get("distanceKm")
        label = f"{name} ({distance}km)" if distance else name
        buttons.append([InlineKeyboardButton(label[:50], callback_data=f"swg_rest:{rid}")])

    await query.message.reply_text(
        "Pick a restaurant:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def handle_restaurant_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    restaurant_id = query.data.split(":", 1)[1]

    state = _state(context)
    restaurant = state.get("restaurants", {}).get(restaurant_id, {})
    state["restaurant_id"] = restaurant_id
    state["restaurant_name"] = restaurant.get("name", "")

    await query.edit_message_text(f"Searching menu for '{state['query']}' at {state['restaurant_name']}...")

    try:
        result = await swiggy_mcp.call_tool(
            "search_menu",
            {
                "addressId": state["address_id"],
                "query": state["query"],
                "restaurantIdOfAddedItem": restaurant_id,
            },
        )
        data = swiggy_mcp.extract_structured_data(result)
    except Exception as e:
        await query.message.reply_text(f"Menu search failed: {e}")
        log_event(f"search_menu failed: {e}")
        return

    items = data.get("items") or data.get("data") or []
    if not items:
        await query.message.reply_text(
            f"No matching dishes found at {state['restaurant_name']}. Try a different search."
        )
        return

    state["menu_items"] = {str(i.get("menu_item_id") or i.get("id")): i for i in items}

    buttons = []
    for item in items[:8]:
        item_id = item.get("menu_item_id") or item.get("id")
        name = item.get("name", "Item")
        price = item.get("price")
        label = f"{name} - ₹{price}" if price else name
        buttons.append([InlineKeyboardButton(label[:50], callback_data=f"swg_item:{item_id}")])

    await query.message.reply_text(
        "Pick a dish to add to your cart:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def handle_item_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    item_id = query.data.split(":", 1)[1]

    state = _state(context)
    item = state.get("menu_items", {}).get(item_id, {})

    await query.edit_message_text(f"Adding {item.get('name', 'item')} to cart...")

    cart_item = {"menu_item_id": item_id, "quantity": 1}
    # Pass through variants in whichever format the item actually has,
    # per Swiggy's own schema note: never both, use whichever is present.
    if item.get("variants"):
        cart_item["variants"] = item["variants"]
    elif item.get("variantsV2"):
        cart_item["variantsV2"] = item["variantsV2"]

    try:
        await swiggy_mcp.call_tool(
            "update_food_cart",
            {"restaurantId": state["restaurant_id"], "cartItems": [cart_item]},
        )
    except Exception as e:
        await query.message.reply_text(f"Failed to add item to cart: {e}")
        log_event(f"update_food_cart failed: {e}")
        return

    await show_cart_and_confirm(query.message, context)


async def show_cart_and_confirm(message, context: ContextTypes.DEFAULT_TYPE):
    """Fetches the real cart (required before placing per Swiggy's own
    docs) and shows the total, asking for explicit confirmation."""
    state = _state(context)

    try:
        result = await swiggy_mcp.call_tool(
            "get_food_cart",
            {"addressId": state["address_id"], "restaurantName": state.get("restaurant_name", "")},
        )
        cart = swiggy_mcp.extract_structured_data(result)
    except Exception as e:
        await message.reply_text(f"Couldn't fetch cart: {e}")
        log_event(f"get_food_cart failed: {e}")
        return

    state["cart"] = cart
    total = cart.get("total") or cart.get("grandTotal") or cart.get("totalAmount")
    payment_methods = cart.get("availablePaymentMethods", [])
    items_summary = cart.get("items") or cart.get("cartItems") or []

    item_lines = "\n".join(
        f"  {i.get('quantity', 1)}x {i.get('name', 'item')}" for i in items_summary
    )

    over_limit = total is not None and float(total) >= 1000

    text = (
        f"Cart at {state.get('restaurant_name', '')}:\n{item_lines}\n\n"
        f"Total: ₹{total}\n"
        f"Payment options: {', '.join(payment_methods) if payment_methods else 'Cash on Delivery'}\n\n"
    )

    if over_limit:
        text += (
            "This order is ₹1000 or more — Swiggy's MCP ordering is in beta and "
            "doesn't allow placing orders at this value. Please use the Swiggy app "
            "directly to complete this order."
        )
        await message.reply_text(text)
        return

    text += "Place this order with Cash on Delivery?"
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("Yes, place order", callback_data="swg_confirm:yes")],
        [InlineKeyboardButton("No, cancel", callback_data="swg_confirm:no")],
    ])
    await message.reply_text(text, reply_markup=buttons)


async def handle_order_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data.split(":", 1)[1]
    state = _state(context)

    if choice == "no":
        await query.edit_message_text("Order cancelled — nothing was placed.")
        state.clear()
        return

    await query.edit_message_text("Placing your order...")

    try:
        result = await swiggy_mcp.call_tool(
            "place_food_order",
            {"addressId": state["address_id"], "paymentMethod": "Cash"},
        )
        data = swiggy_mcp.extract_structured_data(result)
    except Exception as e:
        await query.message.reply_text(f"Order placement failed: {e}")
        log_event(f"place_food_order failed: {e}")
        return

    status = data.get("status", "")
    if status == "PENDING_PAYMENT":
        await query.message.reply_text(
            "Payment is pending — complete it in your UPI app. "
            "I'll confirm once payment succeeds."
        )
    else:
        await query.message.reply_text("Order placed successfully with Swiggy.")
        log_event(f"Order placed: {state.get('restaurant_name')} for query '{state.get('query')}'")

    state.clear()


@owner_only
async def swiggy_cancel_note_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """If asked to cancel — no cancel tool exists, redirect to support."""
    await update.effective_message.reply_text(
        "To cancel a placed Swiggy order, please call Swiggy customer care "
        "at 080-67466729 — there's no automated cancellation available."
    )


def register(application):
    application.add_handler(CommandHandler("swiggyorder", swiggy_order_command))
    application.add_handler(CommandHandler("swiggycancel", swiggy_cancel_note_command))
    application.add_handler(CallbackQueryHandler(handle_address_choice, pattern=r"^swg_addr:"))
    application.add_handler(CallbackQueryHandler(handle_restaurant_choice, pattern=r"^swg_rest:"))
    application.add_handler(CallbackQueryHandler(handle_item_choice, pattern=r"^swg_item:"))
    application.add_handler(CallbackQueryHandler(handle_order_confirmation, pattern=r"^swg_confirm:"))
