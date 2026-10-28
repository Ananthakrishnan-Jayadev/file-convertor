"""`fileconvert` command, installed into the venv by `pip install -e backend`.

    fileconvert serve    build the UI, then serve UI + API on http://localhost:8000
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
FRONTEND = BACKEND.parent / "frontend"


def main() -> None:
    parser = argparse.ArgumentParser(prog="fileconvert", description="File converter web app")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="build the UI and start the server")
    serve.add_argument("--host", default="127.0.0.1", help="address to listen on (use 0.0.0.0 to allow other devices)")
    serve.add_argument("--port", type=int, default=8000, help="port (default 8000)")
    args = parser.parse_args()

    if args.command == "serve":
        sys.exit(cmd_serve(args.host, args.port))


def cmd_serve(host: str, port: int) -> int:
    if (code := build_frontend()) != 0:
        return code

    import uvicorn

    print(f"Open http://localhost:{port}")
    # Backend code changes reload automatically; UI changes need a restart to rebuild.
    uvicorn.run("app.main:app", host=host, port=port, reload=True, reload_dirs=[str(BACKEND / "app")])
    return 0


def build_frontend() -> int:
    npm = shutil.which("npm")
    if npm is None:
        print("npm isn't on your PATH. Install Node.js, then try again.", file=sys.stderr)
        return 1
    if not (FRONTEND / "node_modules").is_dir():
        print(f"Frontend packages missing. Run: cd {FRONTEND} && npm install", file=sys.stderr)
        return 1
    return subprocess.run([npm, "run", "build"], cwd=FRONTEND).returncode


if __name__ == "__main__":
    main()
