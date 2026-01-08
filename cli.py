import argparse

from . import __version__


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
        return

    if args.command == "init":
        print("FixLoop initialized (placeholder).")
        return

    if args.command == "version":
        print(__version__)
        return

    parser.print_help()
