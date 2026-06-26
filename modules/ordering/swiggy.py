"""
Swiggy automation.

IMPORTANT — selectors will need adjustment:
Swiggy's DOM structure changes periodically and isn't publicly documented
for automation. The selectors below are starting points based on typical
structure as of mid-2026, not guaranteed to be current. You WILL need to
inspect the live page (via browser devtools) and adjust selectors if
this breaks — that's normal maintenance for this kind of automation,
not a sign something is broken in the code's logic.

Login: this module assumes data/sessions/swiggy_session.json already
exists from a one-time manual login (see ordering/login_setup.py).
"""
import os
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

from modules.ordering.config import SWIGGY_SESSION_FILE, DEFAULT_TIMEOUT_MS, HEADLESS
from modules.ordering.base import CartResult
from utils.logger import log_event

PLATFORM_NAME = "swiggy"
BASE_URL = "https://www.swiggy.com"


async def search_and_get_cart_total(restaurant_name: str, items: list[str]) -> CartResult:
    if not os.path.exists(SWIGGY_SESSION_FILE):
        return CartResult(platform=PLATFORM_NAME, found=False,
                           error="no saved session — run login setup first")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        context = await browser.new_context(storage_state=SWIGGY_SESSION_FILE)
        page = await context.new_page()
        page.set_default_timeout(DEFAULT_TIMEOUT_MS)

        try:
            await page.goto(BASE_URL)

            # Search for the restaurant
            search_box = page.locator('input[placeholder*="Search for restaurant"]')
            await search_box.click()
            await search_box.fill(restaurant_name)
            await page.wait_for_timeout(1500)  # let search results render

            # Click first matching restaurant result
            first_result = page.locator('[data-testid="restaurant-card"]').first
            if await first_result.count() == 0:
                await browser.close()
                return CartResult(platform=PLATFORM_NAME, found=False,
                                   error=f"'{restaurant_name}' not found in search")
            await first_result.click()
            await page.wait_for_load_state("networkidle")

            # Add each requested item to cart
            added_any = False
            for item_name in items:
                item_locator = page.locator(f'text="{item_name}"').first
                if await item_locator.count() > 0:
                    # Most Swiggy menu items have an "ADD" button near the item
                    add_button = item_locator.locator(
                        'xpath=following::button[contains(text(),"ADD")][1]'
                    )
                    if await add_button.count() > 0:
                        await add_button.click()
                        added_any = True
                        await page.wait_for_timeout(500)

            if not added_any:
                await browser.close()
                return CartResult(platform=PLATFORM_NAME, found=False,
                                   error="none of the requested items matched on menu")

            # Open cart and read totals
            cart_button = page.locator('[data-testid="cart-icon"], text="View Cart"').first
            await cart_button.click()
            await page.wait_for_timeout(1000)

            item_total = await _extract_price(page, '[data-testid="item-total"]')
            delivery_fee = await _extract_price(page, '[data-testid="delivery-fee"]')
            platform_fee = await _extract_price(page, '[data-testid="platform-fee"]')
            grand_total = await _extract_price(page, '[data-testid="grand-total"]')

            screenshot_path = "/home/claude/tg-hub/data/sessions/swiggy_cart_screenshot.png"
            await page.screenshot(path=screenshot_path)

            cart_url = page.url

            await browser.close()

            return CartResult(
                platform=PLATFORM_NAME,
                found=True,
                item_total=item_total,
                delivery_fee=delivery_fee,
                platform_fee=platform_fee,
                grand_total=grand_total or (item_total or 0) + (delivery_fee or 0) + (platform_fee or 0),
                cart_url=cart_url,
                screenshot_path=screenshot_path,
            )

        except PWTimeout as e:
            log_event(f"Swiggy automation timeout: {e}")
            await browser.close()
            return CartResult(platform=PLATFORM_NAME, found=False,
                               error="page took too long to respond (timeout)")
        except Exception as e:
            log_event(f"Swiggy automation error: {e}")
            await browser.close()
            return CartResult(platform=PLATFORM_NAME, found=False, error=str(e))


async def _extract_price(page, selector: str) -> float | None:
    """Pulls a rupee amount out of an element's text, e.g. '₹245.00' -> 245.0"""
    try:
        locator = page.locator(selector).first
        if await locator.count() == 0:
            return None
        text = await locator.inner_text()
        cleaned = text.replace("₹", "").replace(",", "").strip()
        return float(cleaned)
    except (ValueError, Exception):
        return None
