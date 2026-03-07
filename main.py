import subprocess
import sys

from config import config
from utils import utils
from engine import engine


def main():
    if not config.url:
        utils.print("Usage: python main.py [<m3u8_url>] [<output_name>]")
        utils.print("Or set HUGE_URL environment variable.")
        sys.exit(1)

    engine.start()
    notify("Video Complete")


def notify(message):
    title = "🤯 hugegull"

    try:
        subprocess.run(["notify-send", title, message], check=True)
    except subprocess.CalledProcessError as e:
        utils.print(f"Error sending notification: {e}")


if __name__ == "__main__":
    main()
