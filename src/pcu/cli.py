import argparse
import sys

from pcu.check import cmd_check
from pcu.upgrade import cmd_upgrade


def main() -> None:
    parser = argparse.ArgumentParser(prog="pcu", description="Python Check Updates")
    parser.add_argument("-u", "--upgrade", action="store_true", help="upgrade pinned versions to latest")
    args = parser.parse_args()

    if args.upgrade:
        cmd_upgrade()
    else:
        cmd_check()

    sys.exit(0)
