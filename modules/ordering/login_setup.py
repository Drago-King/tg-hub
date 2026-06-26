"""
ONE-TIME SETUP — run this on a PC/laptop, NOT on Termux.

Termux has no display, so Playwright can't show you a real browser
window to log in (and you'll likely need to solve a CAPTCHA / OTP,
which needs a visible page). This script opens a real visible Chromium
window, you log in manually, then it saves the session so the headless
automation on your phone/server can reuse it without ever seeing your
password again.

Usage (on a PC with Python + this repo):
    pip install playwright
    playwright install chromium
    python modules/ordering/login_setup.py swiggy
    python modules/ordering/login_setup.py zomato

After each run, copy the resulting .json file from data/sessions/
to the same path on your Termux device (e.g. via Telegram file transfer,
scp, or syncthing).

Session files expire periodically (exact duration varies by platform) —
when automation starts failing with "no saved session" type errors
even though the file exists, it likely means the session went stale
and you need to redo this step.
"""
import sys
import asyncio
from playwright.async_api import async_playwright

from modules.ordering.config import SWIGGY_SESSION_FILE, ZOMATO_SESSION_FILE

PLATFORMS = {
    "swiggy": ("https://www.swiggy.com", SWIGGY_SESSION_FILE),
    "zomato": ("https://www.zomato.com", ZOMATO_SESSION_FILE),
}


async def run_login(platform: str):
    url, session_file = PLATFORMS[platform]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # visible window
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(url)

        print(f"\nA browser window has opened to {url}")
        print("Log in manually (enter phone/OTP/password as needed).")
        print("Once you're fully logged in and see your account/home screen,")
        input("press Enter here to save the session... ")

        await context.storage_state(path=session_file)
        await browser.close()
        print(f"Session saved to: {session_file}")
        print("Copy this file to the same path on your Termux device.")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in PLATFORMS:
        print("Usage: python modules/ordering/login_setup.py [swiggy|zomato]")
        sys.exit(1)

    asyncio.run(run_login(sys.argv[1]))
