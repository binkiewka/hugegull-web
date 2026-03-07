from __future__ import annotations

#   _    _ _    _  _____  ______     _____ _    _ _      _
#  | |  | | |  | |/ ____||  ____|   / ____| |  | | |    | |
#  | |__| | |  | | |  __ | |__     | |  __| |  | | |    | |
#  |  __  | |  | | | |_ ||  __|    | | |_ | |  | | |    | |
#  | |  | | |__| | |__| || |____   | |__| | |__| | |____| |____
#  |_|  |_|\____/ \_____||______|   \_____|\____/|______|______|

import sys

from config import config
from utils import utils
from engine import engine
from info import info


def show_info() -> None:
    msg = f"{info.name} v{info.version}"
    utils.print(msg)
    utils.print("Usage: python /path/to/main.py <url> <name>")
    utils.print("Or set HUGE_URL and HUGE_NAME env vars.")
    utils.print("Suggested alias: hgg")


def main() -> None:
    args = sys.argv[1:]

    if "--help" in args or "--version" in args:
        show_info()
        sys.exit(0)

    if not config.url:
        show_info()
        sys.exit(1)

    engine.start()

    if config.open:
        utils.open_file(engine.file)
    else:
        utils.notify("Video Complete")


if __name__ == "__main__":
    main()
