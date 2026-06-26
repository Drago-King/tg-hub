"""
Deep link builder.

Instead of automating a browser to build a cart (blocked by bot
detection on both platforms), this constructs search deep links that
open Swiggy/Zomato directly to search results for a restaurant. You
tap through and complete checkout yourself — no login session needed,
no bot-detection risk, nothing to break when the sites update their UI.

Trade-off: no live price comparison since we never load the page.
You'll see actual prices once you tap into the app.
"""
import urllib.parse
from dataclasses import dataclass


@dataclass
class DeepLink:
    platform: str
    url: str


def build_swiggy_link(restaurant_name: str) -> DeepLink:
    query = urllib.parse.quote(restaurant_name)
    url = f"https://www.swiggy.com/search?query={query}"
    return DeepLink(platform="swiggy", url=url)


def build_zomato_link(restaurant_name: str) -> DeepLink:
    query = urllib.parse.quote(restaurant_name)
    url = f"https://www.zomato.com/search?q={query}"
    return DeepLink(platform="zomato", url=url)


def build_links(restaurant_name: str) -> list[DeepLink]:
    return [
        build_swiggy_link(restaurant_name),
        build_zomato_link(restaurant_name),
    ]
