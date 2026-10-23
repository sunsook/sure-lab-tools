"""STATICA MCP tools over the agentic adapter."""

import sys
from pathlib import Path

from vsmmock.agentic import statica


def create_server():
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("STATICA Mock")

    @server.tool(name="statica_pre_analyze")
    def statica_pre_analyze(repo: str) -> dict:
        """Analyze supported MISRA C rules and provide correction hints."""
        return statica.pre_analyze(Path(repo))

    @server.tool(name="statica_ruleset_show")
    def statica_ruleset_show(repo: str) -> dict:
        """Show selected and supported MISRA rules."""
        return statica.ruleset_show(Path(repo))

    @server.tool(name="statica_ruleset_set")
    def statica_ruleset_set(repo: str, rules: list[str]) -> dict:
        """Request a ruleset change and report mock limitations."""
        return statica.ruleset_set(Path(repo), rules)

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
