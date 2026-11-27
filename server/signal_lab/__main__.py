"""Entry point: ``python -m signal_lab [api|runner|scenario]``."""

from __future__ import annotations

import logging
import os
import sys

import uvicorn


def main() -> None:
    role = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("SIGNAL_LAB_ROLE", "api")).lower()
    logging.basicConfig(level=os.getenv("SIGNAL_LAB_LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    host = os.getenv("SIGNAL_LAB_HOST", "0.0.0.0")
    if role == "api":
        from .api import create_app
        from .config import Settings

        settings = Settings()
        uvicorn.run(create_app(settings), host=host, port=settings.port, log_level="warning")
    elif role == "runner":
        from .runner import create_runner_app

        uvicorn.run(create_runner_app(), host=host, port=int(os.getenv("SIGNAL_LAB_PORT", "8001")), log_level="warning")
    else:
        sys.exit(f"unknown role {role!r}; expected api or runner")


if __name__ == "__main__":
    main()
