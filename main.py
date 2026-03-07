from __future__ import annotations

#   _    _ _    _  _____  ______     _____ _    _ _      _
#  | |  | | |  | |/ ____||  ____|   / ____| |  | | |    | |
#  | |__| | |  | | |  __ | |__     | |  __| |  | | |    | |
#  |  __  | |  | | | |_ ||  __|    | | |_ | |  | | |    | |
#  | |  | | |__| | |__| || |____   | |__| | |__| | |____| |____
#  |_|  |_|\____/ \_____||______|   \_____|\____/|______|______|

import re
import sys

from config import config
from utils import utils
from engine import engine


def get_info() -> tuple[str, str]:
    name = ""
    version = ""

    try:
        with open("setup.py", "r") as f:
            content = f.read()
            match = re.search(r'name="([^"]+)"', content)

            if match:
                name = match.group(1)

            match = re.search(r'version="([^"]+)"', content)

            if match:
                version = match.group(1)
    except FileNotFoundError:
        pass

    return name, version


def show_usage() -> None:
    utils.print("Usage: python /path/to/main.py <url> <name>")
    utils.print("Or set HUGE_URL and HUGE_NAME env vars.")
    utils.print("Suggested alias: hgg")


def main() -> None:
    args = sys.argv[1:]

    if "--help" in args or "--version" in args:
        name, version = get_info()
        utils.print(f"{name} v{version}")
        show_usage()
        sys.exit(0)

    if not config.url:
        show_usage()
        sys.exit(1)

    engine.start()
    utils.notify("Video Complete")


if __name__ == "__main__":
    main()
