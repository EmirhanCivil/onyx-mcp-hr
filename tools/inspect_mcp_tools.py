import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.server import mcp


async def main():
    tools = await mcp.list_tools()
    print(f"tool_count={len(tools)}")
    for tool in tools:
        print(tool.name)
        print(getattr(tool, "inputSchema", None) or getattr(tool, "parameters", None))


asyncio.run(main())
