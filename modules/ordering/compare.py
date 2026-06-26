"""
Runs both platform searches and compares totals.
Both run regardless of whether one fails — a failure on one platform
just excludes it from comparison rather than blocking the other.
"""
import asyncio

from modules.ordering import swiggy, zomato
from modules.ordering.base import CartResult
from utils.logger import log_event


async def compare_platforms(restaurant_name: str, items: list[str]) -> tuple[list[CartResult], CartResult | None]:
    """
    Returns (all_results, cheapest_result_or_None).
    cheapest is None if neither platform found the restaurant/items.
    """
    log_event(f"Comparing '{restaurant_name}' {items} across Swiggy + Zomato")

    results = await asyncio.gather(
        swiggy.search_and_get_cart_total(restaurant_name, items),
        zomato.search_and_get_cart_total(restaurant_name, items),
        return_exceptions=True,
    )

    # Convert any raised exceptions into a found=False CartResult so one
    # platform crashing never breaks the other's result.
    clean_results: list[CartResult] = []
    platform_names = ["swiggy", "zomato"]
    for name, r in zip(platform_names, results):
        if isinstance(r, Exception):
            log_event(f"{name} comparison raised exception: {r}")
            clean_results.append(CartResult(platform=name, found=False, error=str(r)))
        else:
            clean_results.append(r)

    available = [r for r in clean_results if r.found and r.grand_total is not None]
    cheapest = min(available, key=lambda r: r.grand_total) if available else None

    return clean_results, cheapest
