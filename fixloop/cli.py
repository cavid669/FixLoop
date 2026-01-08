import argparse
import os
from pathlib import Path

from . import __version__


def _config_dir() -> Path:
    # Windows: C:\Users\<name>\.fixloop
    return Path.home() / ".fixloop"


def _config_path() -> Path:
    return _config_dir() / "config.yaml"


def _write_default_config(openai_key: str = "") -> None:
    cfg_dir = _config_dir()
    cfg_dir.mkdir(parents=True, exist_ok=True)

    content = (
        "# FixLoop configuration\n"
        "provider: openai\n"
        f"openai_api_key: {openai_key}\n"
        "model: gpt-4o-mini\n"
    )
    _config_path().write_text(content, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        prog="fixloop",
        description="FixLoop — Your Personal Code Guard",
    )

    subparsers = parser.add_subparsers(dest="command")

    # fix command
    fix_cmd = subparsers.add_parser("fix", help="Run FixLoop on a command")
    fix_cmd.add_argument("--cmd", required=True, help="Command to run")
    fix_cmd.add_argument("--verify", help="Verification command (optional)")

    # init command
    subparsers.add_parser("init", help="Initialize FixLoop configuration")

    # version command
    subparsers.add_parser("version", help="Show FixLoop version")

    args = parser.parse_args()

    if args.command == "fix":
        print("FixLoop running...")
        print(f"Command: {args.cmd}")
        if args.verify:
            print(f"Verify: {args.verify}")
        return 0

    if args.command == "init":
        # Try env var first (BYOK)
        key = os.getenv("OPENAI_API_KEY", "").strip()
        _write_default_config(openai_key=key)
        print(f"FixLoop config created: {_config_path()}")
        if key:
            print("OPENAI_API_KEY found in environment and written to config.yaml")
        else:
            print("OPENAI_API_KEY not found. Add it to config.yaml or set env var OPENAI_API_KEY.")
        return 0

    if args.command == "version":
        print(__version__)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    main()
