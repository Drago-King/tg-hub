"""
Standard Playwright stealth measures.

Headless Chromium is detectable by default — navigator.webdriver is True,
missing plugins/languages that real browsers have, and a flagged
user-agent string. This module patches the most common fingerprint
signals. It improves odds against basic bot detection (most sites) but
won't reliably bypass enterprise-grade WAFs (Akamai/Cloudflare with
behavioral analysis) — those often need residential proxies or real
browser automation tools, which is a different tier of effort/cost.
"""

REALISTIC_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36"
)

STEALTH_INIT_SCRIPT = """
// Hide the most common automation fingerprints
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['en-IN', 'en'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
window.chrome = { runtime: {} };
"""


async def new_stealth_context(browser, storage_state_path: str):
    """
    Creates a browser context with stealth tweaks applied, loaded from
    a saved session file (cookies).
    """
    context = await browser.new_context(
        storage_state=storage_state_path,
        user_agent=REALISTIC_USER_AGENT,
        viewport={"width": 412, "height": 915},  # common Android viewport
        locale="en-IN",
        timezone_id="Asia/Kolkata",
        extra_http_headers={
            "Accept-Language": "en-IN,en;q=0.9",
        },
    )
    await context.add_init_script(STEALTH_INIT_SCRIPT)
    return context
