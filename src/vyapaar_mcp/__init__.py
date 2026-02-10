"""Vyapaar MCP — Agentic Financial Governance Server."""

__version__ = "3.0.0"


def main() -> None:
    """CLI entrypoint for the Vyapaar MCP server."""
    import asyncio

    from vyapaar_mcp.server import run_server

    asyncio.run(run_server())
