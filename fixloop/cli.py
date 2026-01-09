import argparse
import os
from pathlib import Path

from . import __version__


def _config_dir() -> Path:
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
    fix_cmd.add_argument("--yes", action="store_true", help="Auto-apply patch without prompting")
    fix_cmd.add_argument("--max-iters", type=int, default=1, help="Max fix attempts (default: 1)")

    # init command
    subparsers.add_parser("init", help="Initialize FixLoop configuration")

    # version command
    subparsers.add_parser("version", help="Show FixLoop version")

    # ai-test command
    ai_cmd = subparsers.add_parser("ai-test", help="Test OpenAI connection (BYOK)")
    ai_cmd.add_argument("--prompt", default="Return only the word OK.", help="Prompt to send")

    args = parser.parse_args()

    if args.command == "init":
        key = os.getenv("OPENAI_API_KEY", "").strip()
        _write_default_config(openai_key=key)
        print(f"FixLoop config created: {_config_path()}")
        if key:
            print("OPENAI_API_KEY found in environment and written to config.yaml")
        else:
            print("OPENAI_API_KEY not found. Add it to config.yaml or set env var OPENAI_API_KEY.")
        return 0

    if args.command == "ai-test":
        from .ai import ai_test
        try:
            out = ai_test(prompt=args.prompt)
            print(out)
            return 0
        except Exception as e:
            print(f"[FixLoop] AI test failed: {e}")
            return 1

    if args.command == "fix":
        from .fixer import fix_loop
        outcome = fix_loop(
            cmd=args.cmd,
            verify_cmd=args.verify,
            yes=args.yes,
            max_iters=args.max_iters,
        )
        print(outcome.message)
        return 0 if outcome.ok else 1

    if args.command == "version":
        print(__version__)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    main()
