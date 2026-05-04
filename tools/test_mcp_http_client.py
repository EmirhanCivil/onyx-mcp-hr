import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main():
    async with streamablehttp_client("http://127.0.0.1:8005/mcp") as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            tools = await session.list_tools()
            print(f"tool_count={len(tools.tools)}")
            for tool in tools.tools:
                print(tool.name)


asyncio.run(main())
