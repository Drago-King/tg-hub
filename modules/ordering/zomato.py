"""
Zomato automation. Same caveats as swiggy.py — selectors are starting
points, not guaranteed current. Expect to inspect+adjust via devtools
when Zomato updates their site.
"""
import os
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

from modules.ordering.config import ZOMATO_SESSION_FILE, DEFAULT_TIMEOUT_MS, HEADLESS
from modules.ordering.base import CartResult
from utils.logger import log_event

PLATFORM_NAME = "zomato"
BASE_URL = "https://www.zomato.com"


async def search_and_get_cart_total(restaurant_name: str, items: list[str]) -> CartResult:
    if not os.path.exists(ZOMATO_SESSION_FILE):
        return CartResult(platform=PLATFORM_NAME, found=False,
                           error="no saved session — run login setup first")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        context = await browser.new_context(storage_state=ZOMATO_SESSION_FILE)
        page = await context.new_page()
        page.set_default_timeout(DEFAULT_TIMEOUT_MS)

        try:
            await page.goto(BASE_URL)

            search_box = page.locator('input[placeholder*="Search for restaurant"]')
            await search_box.click()
            await search_box.fill(restaurant_name)
            await page.wait_for_timeout(1500)

            first_result = page.locator('a[href*="/order"]').first
            if await first_result.count() == 0:
                await browser.close()
                return CartResult(platform=PLATFORM_NAME, found=False,
                                   error=f"'{restaurant_name}' not found in search")
            await first_result.click()
            await page.wait_for_load_state("networkidle")

            added_any = False
            for item_name in items:
                item_locator = page.locator(f'text="{item_name}"').first
                if await item_locator.count() > 0:
                    add_button = item_locator.locator(
                        'xpath=following::button[contains(text(),"Add")][1]'
                    )
                    if await add_button.count() > 0:
                        await add_button.click()
                        added_any = True
                        await page.wait_for_timeout(500)

            if not added_any:
                await browser.close()
                return CartResult(platform=PLATFORM_NAME, found=False,
                                   error="none of the requested items matched on menu")

            cart_button = page.locator('text="View Cart"').first
            await cart_button.click()
            await page.wait_for_timeout(1000)

            item_total = await _extract_price(page, '[class*="item-total"]')
            delivery_fee = await _extract_price(page, '[class*="delivery-fee"]')
            platform_fee = await _extract_price(page, '[class*="platform-fee"]')
            grand_total = await _extract_price(page, '[class*="grand-total"], [class*="to-pay"]')

            screenshot_path = "/home/claude/tg-hub/data/sessions/zomato_cart_screenshot.png"
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
            log_event(f"Zomato automation timeout: {e}")
            await browser.close()
            return CartResult(platform=PLATFORM_NAME, found=False,
                               error="page took too long to respond (timeout)")
        except Exception as e:
            log_event(f"Zomato automation error: {e}")
            await browser.close()
            return CartResult(platform=PLATFORM_NAME, found=False, error=str(e))


async def _extract_price(page, selector: str) -> float | None:
    try:
        locator = page.locator(selector).first
        if await locator.count() == 0:
            return None
        text = await locator.inner_text()
        cleaned = text.replace("₹", "").replace(",", "").strip()
        return float(cleaned)
    except (ValueError, Exception):
        return None
