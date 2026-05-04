from fastmcp import FastMCP

mcp = FastMCP("Minimal MCP Test")


@mcp.tool()
def ping(message: str = "ok") -> str:
    """Simple connectivity test tool."""
    return f"pong: {message}"


if __name__ == "__main__":
    mcp.run(transport="sse", host="0.0.0.0", port=8010)
