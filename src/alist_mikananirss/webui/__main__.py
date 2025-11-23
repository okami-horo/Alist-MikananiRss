"""Module entry point for launching the WebUI via CLI tools.

This entry uses a direct import of the FastAPI application object to ensure
packagers like PyInstaller can statically analyze and include the module
graph (avoiding string-based dynamic imports).
"""

from __future__ import annotations

import argparse
import uvicorn
try:
    # Prefer absolute import so PyInstaller can resolve package graph.
    from alist_mikananirss.webui import server as webui_server
except Exception:  # pragma: no cover - defensive fallback
    # Fallback to relative import when running via `python -m`.
    from . import server as webui_server  # type: ignore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Alist-MikananiRss WebUI server.")
    parser.add_argument("--host", default="0.0.0.0", help="Host address to bind (default: 0.0.0.0).")
    parser.add_argument("--port", type=int, default=8080, help="TCP port to listen on (default: 8080).")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload. Intended for development only.",
    )
    parser.add_argument(
        "--log-level",
        default="info",
        choices=["critical", "error", "warning", "info", "debug", "trace"],
        help="Log level passed to Uvicorn (default: info).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    uvicorn.run(
        webui_server.app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )


if __name__ == "__main__":  # pragma: no cover - CLI entry
    main()
