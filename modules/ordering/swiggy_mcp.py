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

_session_id_cache = None


def _load_access_token() -> str:
    """
    Reads the access token either from a local file (if already written
    by session_loader-style env var restoration) or directly from the
    SWIGGY_MCP_TOKENS_B64 env var as a fallback.
    """
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
    """
    Server may reply with plain JSON or an SSE stream containing one
    'data: {...}' event — handle both per the Streamable HTTP spec.
    """
    content_type = response.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        for line in response.text.splitlines():
            if line.startswith("data:"):
                return json.loads(line[len("data:"):].strip())
        raise RuntimeError(f"No data event in SSE response: {response.text}")
    return response.json()


async def _ensure_session(client: httpx.AsyncClient) -> str | None:
    global _session_id_cache
    if _session_id_cache:
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

    if not session_id:
        # Some MCP servers are stateless and never issue a session ID —
        # that's valid per spec ("MAY assign"), not necessarily an error.
        # Surface the actual response so we can tell which case this is.
        parsed_body = _parse_response(resp)
        raise RuntimeError(
            f"No Mcp-Session-Id header returned. "
            f"Status={resp.status_code}, "
            f"Headers={dict(resp.headers)}, "
            f"Body={parsed_body}"
        )

    # Required follow-up per spec — confirms client is ready
    notify_body = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    await client.post(SWIGGY_MCP_URL, json=notify_body, headers=_headers(session_id))

    _session_id_cache = session_id
    return session_id


async def call_tool(tool_name: str, arguments: dict, timeout: float = 30.0) -> dict:
    """
    Calls a single Swiggy MCP tool (e.g. 'search_restaurants', 'add_to_cart')
    and returns the parsed result. Raises on HTTP or JSON-RPC errors.
    """
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
