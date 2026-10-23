"""ADS MCP tools over the agentic adapter."""

import sys
from pathlib import Path

from vsmmock.agentic import ads


def create_server():
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("ADS Mock")

    @server.tool(name="ads_generate_docs")
    def ads_generate_docs(repo: str) -> dict:
        """Generate SRS and Test Spec documents from repository evidence."""
        return ads.generate_docs(Path(repo))

    @server.tool(name="ads_trace")
    def ads_trace(repo: str) -> dict:
        """Check the requirement, SRS, and test ID chain."""
        return ads.trace(Path(repo))

    return server


def main() -> int:
    try:
        server = create_server()
    except ModuleNotFoundError as error:
        if error.name != "mcp":
            raise
        print("MCP SDK가 없습니다. pip install vsmmock[mcp]", file=sys.stderr)
        return 2
    server.run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
