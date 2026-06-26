"""
Direct MCP client for Swiggy's food-ordering MCP server.

No Node.js needed at runtime — the OAuth dance was already done once
(via the separate login.js script on a PC/Termux), and we just have a
plain Bearer access token now. From here, MCP-over-HTTP is just JSON-RPC
POST requests, which httpx handles fine.

Protocol flow (per MCP Streamable HTTP spec):
    1. POST "initialize" -> capture Mcp-Session-Id response header
    2. POST "notifications/initialized" (no response expected)
    3. POST "tools/call" with that session ID on every subsequent call

Token expires in ~5 days (see login_setup). When it does, every call
here will start failing with an auth error — that's the signal to
re-run login.js and update SWIGGY_MCP_TOKENS_B64 on Railway.
"""
import os
import json
import base64
import uuid
import httpx

SWIGGY_MCP_URL = "https://mcp.swiggy.com/food"
TOKENS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "swiggy_mcp_tokens.json")
TOKENS_FILE = os.path.normpath(TOKENS_FILE)

_UNSET = object()
_session_id_cache = _UNSET


def _load_access_token() -> str:
    if os.path.exists(TOKENS_FILE):
        with open(TOKENS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data["access_token"]

    b64_value = os.environ.get("SWIGGY_MCP_TOKENS_B64")
    if not b64_value:
        raise RuntimeError(
            "No Swiggy MCP token found. Set SWIGGY_MCP_TOKENS_B64 on Railway, "
            "or run login.js locally and copy swiggy_tokens.json into data/."
        )
    decoded = base64.b64decode(b64_value)
    data = json.loads(decoded)
    return data["access_token"]


def _headers(session_id: str | None = None) -> dict:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {_load_access_token()}",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    return headers


def _parse_response(response: httpx.Response) -> dict:
    content_type = response.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        for line in response.text.splitlines():
            if line.startswith("data:"):
                return json.loads(line[len("data:"):].strip())
        raise RuntimeError(f"No data event in SSE response: {response.text}")
    return response.json()


async def _ensure_session(client: httpx.AsyncClient) -> str | None:
    global _session_id_cache
    if _session_id_cache is not _UNSET:
        return _session_id_cache

    init_body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "personal-tg-hub", "version": "1.0.0"},
        },
    }
    resp = await client.post(SWIGGY_MCP_URL, json=init_body, headers=_headers())
    resp.raise_for_status()
    session_id = resp.headers.get("Mcp-Session-Id")

    notify_body = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    await client.post(SWIGGY_MCP_URL, json=notify_body, headers=_headers(session_id))

    _session_id_cache = session_id
    return session_id


async def call_tool(tool_name: str, arguments: dict, timeout: float = 30.0) -> dict:
    async with httpx.AsyncClient(timeout=timeout) as client:
        session_id = await _ensure_session(client)

        call_body = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        resp = await client.post(SWIGGY_MCP_URL, json=call_body, headers=_headers(session_id))
        resp.raise_for_status()
        parsed = _parse_response(resp)

        if "error" in parsed:
            raise RuntimeError(f"Swiggy MCP error calling {tool_name}: {parsed['error']}")
        return parsed.get("result", {})


async def list_tools(timeout: float = 30.0) -> list[str]:
    """Diagnostic helper — returns the names of all tools this server exposes."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        session_id = await _ensure_session(client)
        body = {"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "tools/list"}
        resp = await client.post(SWIGGY_MCP_URL, json=body, headers=_headers(session_id))
        resp.raise_for_status()
        parsed = _parse_response(resp)
        return [t["name"] for t in parsed.get("result", {}).get("tools", [])]


# ---------------------------------------------------------------------------
# Typed wrappers — one per MCP tool
# These extract the "content" text and parse JSON so callers get clean dicts.
# ---------------------------------------------------------------------------

def _text_content(result: dict) -> str:
    """Pull the first text block out of an MCP tool result."""
    content = result.get("content", [])
    for block in content:
        if block.get("type") == "text":
            return block.get("text", "")
    return json.dumps(result)


def _json_content(result: dict) -> dict | list:
    """Pull first text block and JSON-parse it."""
    raw = _text_content(result)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}


async def get_addresses() -> list[dict]:
    result = await call_tool("get_addresses", {})
    data = _json_content(result)
    return data if isinstance(data, list) else data.get("addresses", [data])


async def search_restaurants(query: str, address_id: str = "") -> list[dict]:
    args = {"query": query}
    if address_id:
        args["address_id"] = address_id
    result = await call_tool("search_restaurants", args)
    data = _json_content(result)
    return data if isinstance(data, list) else data.get("restaurants", [data])


async def search_menu(query: str, restaurant_id: str) -> list[dict]:
    result = await call_tool("search_menu", {"query": query, "restaurant_id": restaurant_id})
    data = _json_content(result)
    return data if isinstance(data, list) else data.get("items", [data])


async def get_restaurant_menu(restaurant_id: str) -> dict:
    result = await call_tool("get_restaurant_menu", {"restaurant_id": restaurant_id})
    return _json_content(result)


async def get_food_cart() -> dict:
    result = await call_tool("get_food_cart", {})
    return _json_content(result)


async def update_food_cart(item_id: str, quantity: int, restaurant_id: str) -> dict:
    result = await call_tool("update_food_cart", {
        "item_id": item_id,
        "quantity": quantity,
        "restaurant_id": restaurant_id,
    })
    return _json_content(result)


async def flush_food_cart() -> dict:
    result = await call_tool("flush_food_cart", {})
    return _json_content(result)


async def fetch_food_coupons() -> list[dict]:
    result = await call_tool("fetch_food_coupons", {})
    data = _json_content(result)
    return data if isinstance(data, list) else data.get("coupons", [])


async def apply_food_coupon(coupon_code: str) -> dict:
    result = await call_tool("apply_food_coupon", {"coupon_code": coupon_code})
    return _json_content(result)


async def place_food_order(address_id: str, payment_method: str = "wallet") -> dict:
    result = await call_tool("place_food_order", {
        "address_id": address_id,
        "payment_method": payment_method,
    })
    return _json_content(result)


async def get_food_orders(limit: int = 5) -> list[dict]:
    result = await call_tool("get_food_orders", {"limit": limit})
    data = _json_content(result)
    return data if isinstance(data, list) else data.get("orders", [data])


async def get_food_order_details(order_id: str) -> dict:
    result = await call_tool("get_food_order_details", {"order_id": order_id})
    return _json_content(result)


async def track_food_order(order_id: str) -> dict:
    result = await call_tool("track_food_order", {"order_id": order_id})
    return _json_content(result)


async def get_food_delivery_status(order_id: str) -> dict:
    result = await call_tool("get_food_delivery_status", {"order_id": order_id})
    return _json_content(result)


async def report_error(error_description: str, order_id: str = "") -> dict:
    args = {"error_description": error_description}
    if order_id:
        args["order_id"] = order_id
    result = await call_tool("report_error", args)
    return _json_content(result)
