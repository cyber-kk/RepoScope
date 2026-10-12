"""RepoScope convenience launcher.

Run from the project root:
    python run.py            # serve on http://0.0.0.0:8000
    python run.py --reload   # auto-reload during development
    python run.py --port 9000
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RepoScope locally.")
    parser.add_argument("--host", default=os.environ.get("REPOSCOPE_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("REPOSCOPE_PORT", "8000")))
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (dev mode)")
    args = parser.parse_args()

    import uvicorn

    uvicorn.run(
        "main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_dirs=[str(BACKEND_DIR)] if args.reload else None,
    )


if __name__ == "__main__":
    main()
