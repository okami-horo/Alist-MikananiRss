"""Module entry point for launching the WebUI via CLI tools."""

from __future__ import annotations

import argparse
import uvicorn


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
        "alist_mikananirss.webui.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )


if __name__ == "__main__":  # pragma: no cover - CLI entry
    main()
