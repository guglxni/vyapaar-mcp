"""Vyapaar MCP — Agentic Financial Governance Server."""

# Internal prototype identifier — not for public display.
__version__ = "0.0.0-prototype"


def main() -> None:
    """CLI entrypoint for the Vyapaar MCP server."""
    from vyapaar_mcp.server import run_server_sync

    run_server_sync()
