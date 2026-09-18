"""Check the connection to the Sanity Context MCP endpoint.

Makes two calls:
  1. tools/list      -> which tools the endpoint exposes
  2. initial_context -> the knowledge base outline

Usage: python scripts/check_connection.py
"""

import json
import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

MCP_URL = os.getenv("SANITY_MCP_URL")
API_TOKEN = os.getenv("SANITY_API_TOKEN")

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def check_env() -> None:
    """Fail early if the .env file is incomplete."""
    missing = [
        name
        for name, value in (
            ("SANITY_MCP_URL", MCP_URL),
            ("SANITY_API_TOKEN", API_TOKEN),
        )
        if not value
    ]
    if missing:
        print(f"ERROR: missing from .env: {', '.join(missing)}")
        sys.exit(1)


def parse_response(body: str) -> dict:
    """Parse a response that may be plain JSON or server-sent events.

    SSE responses carry the payload on lines prefixed with 'data: '.
    MCP servers use either format, so handle both.
    """
    body = body.strip()
    if body.startswith("data:"):
        for line in body.splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
    return json.loads(body)


def call(client: httpx.Client, method: str, params: dict | None = None) -> dict:
    """Send a JSON-RPC call to the endpoint and return its result."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or {},
    }
    response = client.post(MCP_URL, json=payload, headers=HEADERS, timeout=60.0)
    response.raise_for_status()
    data = parse_response(response.text)

    if "error" in data:
        error = data["error"]
        raise RuntimeError(f"[{error.get('code')}] {error.get('message')}")

    return data.get("result", {})


def main() -> None:
    check_env()
    print(f"Endpoint: {MCP_URL}\n")

    with httpx.Client() as client:
        print("1. Available tools")
        print("-" * 40)
        try:
            result = call(client, "tools/list")
            tools = result.get("tools", [])
            if not tools:
                print("   no tools returned")
            for tool in tools:
                description = (tool.get("description") or "").split("\n")[0]
                print(f"   {tool['name']}: {description[:70]}")
        except Exception as error:
            print(f"   FAILED: {error}")
            sys.exit(1)

        print("\n2. Knowledge base outline")
        print("-" * 40)
        try:
            result = call(
                client,
                "tools/call",
                {"name": "initial_context", "arguments": {}},
            )
            for block in result.get("content", []):
                if block.get("type") == "text":
                    text = block["text"]
                    print(text[:1500])
                    if len(text) > 1500:
                        print(f"\n   ... (+{len(text) - 1500} more characters)")
        except Exception as error:
            print(f"   FAILED: {error}")
            sys.exit(1)

    print("\nConnection OK.")


if __name__ == "__main__":
    main()
