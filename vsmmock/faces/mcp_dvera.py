"""DVERA MCP tools over the agentic adapter."""

import sys
from pathlib import Path

from vsmmock.agentic import dvera


def _optional(name: str, repo: str) -> dict:
    method = getattr(dvera, name, None)
    if method is None:
        return {"source": "MOCK", "status": "ERROR", "reason": "MOCK_UNAVAILABLE",
                "detail": f"DVERA adapter function {name} is not available."}
    return method(Path(repo))


def create_server():
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("DVERA Mock")

    @server.tool(name="ct_find_functions")
    def ct_find_functions(repo: str, query: str = "") -> dict:
        """Find C functions and signature hashes in a repository."""
        return dvera.find_functions(Path(repo), query)

    @server.tool(name="ct_ai_generate_test")
    def ct_ai_generate_test(repo: str, signatureHash: str, specs: list[str] | None = None,
                            approved_spec: str | None = None) -> dict:
        """Propose a test specification; create definitions only with approved_spec."""
        return dvera.ai_generate_test(Path(repo), signatureHash, specs, approved_spec)

    @server.tool(name="ct_execute_test")
    def ct_execute_test(repo: str) -> dict:
        """Build and run available CT definitions and C tests."""
        return dvera.execute_test(Path(repo))

    @server.tool(name="ct_get_test_results")
    def ct_get_test_results(repo: str) -> dict:
        """Return CT execution results."""
        return dvera.get_test_results(Path(repo))

    @server.tool(name="ct_get_coverage")
    def ct_get_coverage(repo: str) -> dict:
        """Return supported branch coverage and uncovered branches."""
        return _optional("get_coverage", repo)

    @server.tool(name="dvera_check_environment")
    def dvera_check_environment(repo: str) -> dict:
        """Report the compiler and coverage environment."""
        return _optional("check_environment", repo)

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
