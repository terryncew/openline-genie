"""Official MCP v2 stdio handshake test, never replaced by fallback mode.

Execute only in an isolated installation of openline-connect[mcp].
"""
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from mcp import Client, StdioServerParameters
from openline_connect.onboarding import initialize


async def main():
    with tempfile.TemporaryDirectory(prefix="openline-mcp-official-") as directory:
        home = Path(directory) / "receiver"
        info = initialize(home)
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "openline_connect.cli", "serve", "--home", str(home)],
            env={"PYTHONUNBUFFERED": "1"},
        )
        async with Client(params) as client:
            listing = await client.list_tools()
            names = sorted(tool.name for tool in listing.tools)
            required = {
                "openline_inspect_system",
                "openline_check_authorization",
                "openline_verify_receipt",
                "openline_list_unresolved",
                "openline_execute_protected_action",
                "openline_recover_operation",
            }
            assert set(names) == required, names
            inspect = await client.call_tool("openline_inspect_system", {})
            assert not inspect.is_error, inspect
            decision = await client.call_tool(
                "openline_check_authorization",
                {"action": "record.update", "params": {"target": "customer-1", "amount_cents": 1}, "authorization": "bogus"},
            )
            assert not decision.is_error, decision
            print(json.dumps({
                "official_mcp": True,
                "handshake": True,
                "tools": names,
                "default_deny": True,
                "receiver_public": info["seller_public"],
                "check_auth_result": decision.structured_content,
            }, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
