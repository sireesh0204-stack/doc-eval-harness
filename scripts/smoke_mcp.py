"""End-to-end MCP round-trip: spawn the server over stdio, list tools, and
validate fixtures across the wire (bug4 must be caught, good must pass)."""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> int:
    fx = ROOT / "fixtures"
    params = StdioServerParameters(command=sys.executable, args=["-m", "mcp_server"],
                                   cwd=str(ROOT))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("tools:", sorted(t.name for t in tools.tools))

            res = await session.call_tool("list_forms", {})
            print("list_forms:", res.content[0].text)

            xml = (fx / "xml" / "bug4.xml").read_text(encoding="utf-8")
            payload = (fx / "inputs" / "bug4.json").read_text(encoding="utf-8")
            res = await session.call_tool("validate_output", {
                "form": "wv_nipa2", "xml": xml, "input_payload": payload})
            data = json.loads(res.content[0].text)
            print("bug4 caught over MCP:", data["caught"])
            assert "rules.precision" in data["caught"], data

            good = (fx / "xml" / "good_corporate.xml").read_text(encoding="utf-8")
            payload = (fx / "inputs" / "good_corporate.json").read_text(encoding="utf-8")
            res = await session.call_tool("validate_output", {
                "form": "wv_nipa2", "xml": good, "input_payload": payload})
            data = json.loads(res.content[0].text)
            print("good_corporate verdict over MCP:", data["verdict"])
            assert data["verdict"] == "pass", data

            print("MCP round-trip OK")
            return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
