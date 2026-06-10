"""CLI entry points for ingest and MCP server."""

from caseware_kb.pipeline import run_ingest


def ingest_main() -> None:
    import json

    summary = run_ingest()
    print(json.dumps(summary, indent=2))


def mcp_main() -> None:
    from mcp_server.server import main

    main()
