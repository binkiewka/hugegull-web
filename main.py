import subprocess
import sys

from config import config
from utils import utils
from engine import engine


def main():
    if not config.url:
        utils.print("Usage: python main.py [<url>] [<name>]")
        utils.print("Or set HUGE_URL and HUGE_NAME env vars.")
        sys.exit(1)

    engine.start()
    utils.notify("Video Complete")


if __name__ == "__main__":
    main()
