import argparse
import sys

from pcu.check import cmd_check
from pcu.upgrade import cmd_upgrade


def main() -> None:
    parser = argparse.ArgumentParser(prog="pcu", description="Python Check Updates")
    parser.add_argument("-u", "--upgrade", action="store_true", help="upgrade pinned versions to latest")
    parser.add_argument("--major", action="store_true", help="include major bumps (use with -u)")
    parser.add_argument("--minor", action="store_true", help="include minor bumps (use with -u)")
    parser.add_argument("--patch", action="store_true", help="include patch bumps (use with -u)")
    parser.add_argument("--pin", action="store_true", help="include pin-only bumps (use with -u)")
    parser.add_argument(
        "--drop",
        nargs="+",
        default=[],
        metavar="PKG",
        help="exclude named packages from upgrade (use with -u)",
    )
    args = parser.parse_args()

    upgrade_only_flags = args.major or args.minor or args.patch or args.pin or args.drop
    if upgrade_only_flags and not args.upgrade:
        parser.error("--major/--minor/--patch/--pin/--drop require -u")

    if args.upgrade:
        severities: set[str] = set()
        if args.major:
            severities.add("major")
        if args.minor:
            severities.add("minor")
        if args.patch:
            severities.add("patch")
        if args.pin:
            severities.add("pin")
        cmd_upgrade(severities=severities, drops=args.drop)
    else:
        cmd_check()

    sys.exit(0)
