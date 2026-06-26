"""
Common interface both platform automations follow.

Every platform module (swiggy.py, zomato.py) implements:
    async def search_and_get_cart_total(playwright, restaurant_name, items) -> CartResult

This lets ordering.py (the Telegram-facing handler) treat both platforms
identically when comparing prices, and makes it easy to add a third
platform later without touching the comparison logic.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class CartResult:
    platform: str               # "swiggy" or "zomato"
    found: bool                 # restaurant/items were found on this platform
    item_total: Optional[float] = None
    delivery_fee: Optional[float] = None
    platform_fee: Optional[float] = None
    discount: Optional[float] = None
    grand_total: Optional[float] = None
    cart_url: Optional[str] = None     # deep link to reopen this exact cart
    screenshot_path: Optional[str] = None
    error: Optional[str] = None

    def summary_line(self) -> str:
        if not self.found:
            reason = self.error or "restaurant/items not found"
            return f"{self.platform.title()}: unavailable ({reason})"
        return f"{self.platform.title()}: ₹{self.grand_total:.2f} (items ₹{self.item_total:.2f} + fees ₹{(self.delivery_fee or 0) + (self.platform_fee or 0):.2f})"
