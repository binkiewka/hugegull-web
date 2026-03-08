from __future__ import annotations

#   _    _ _    _  _____  ______     _____ _    _ _      _
#  | |  | | |  | |/ ____||  ____|   / ____| |  | | |    | |
#  | |__| | |  | | |  __ | |__     | |  __| |  | | |    | |
#  |  __  | |  | | | |_ ||  __|    | | |_ | |  | | |    | |
#  | |  | | |__| | |__| || |____   | |__| | |__| | |____| |____
#  |_|  |_|\____/ \_____||______|   \_____|\____/|______|______|

import sys
import time

from config import config
from utils import utils
from engine import engine
from info import info


def show_info() -> None:
    msg = f"{info.name} v{info.version}"
    utils.print(msg)
    utils.print("")
    utils.print("Usage: hugegull-web <url> [name] [options]")
    utils.print("   or: hugegull-web --url <url> [--url <url2> ...] [--name <name>]")
    utils.print("")
    utils.print("Environment variables:")
    utils.print("  HUGE_URL    - Default video URL")
    utils.print("  HUGE_NAME   - Default output name")
    utils.print("")
    utils.print("Core options:")
    utils.print("  --config <path>          - Use custom config file")
    utils.print("  --gpu <amd|nvidia|intel> - Use hardware encoding")
    utils.print("  --open                   - Open video when complete")
    utils.print("")
    utils.print("Scene detection (smart clips):")
    utils.print("  --scene-detection        - Detect scene changes instead of random")
    utils.print("  --scene-threshold <n>    - Scene sensitivity (0.1-0.5, default: 0.3)")
    utils.print("  --sort-by scene_score    - Sort clips by action intensity")
    utils.print("")
    utils.print("Preview & planning:")
    utils.print("  --preview, --dry-run     - Show planned clips without generating")
    utils.print("")
    utils.print("Skip intros/outros:")
    utils.print("  --skip-start <seconds>   - Skip first N seconds")
    utils.print("  --skip-end <seconds>     - Skip last N seconds")
    utils.print("")
    utils.print("Resume & ordering:")
    utils.print("  --resume                 - Resume interrupted job")
    utils.print("  --shuffle                - Randomize clip order")
    utils.print("")
    utils.print("Output options:")
    utils.print("  --aspect-ratio <ratio>   - 16:9, 9:16 (vertical), 1:1, 4:5")
    utils.print("  --format <ext>           - Output format: mp4, webm, mov")
    utils.print("")
    utils.print("Web UI:")
    utils.print("  hugegull-web-ui          - Start web interface")
    utils.print("")
    utils.print("Examples:")
    utils.print("  hugegull-web https://youtube.com/watch?v=... highlights")
    utils.print("  hugegull-web stream.m3u8 --scene-detection --skip-start 30")
    utils.print("  hugegull-web vid.mp4 --preview  # See what would be extracted")
    utils.print("  hugegull-web <url> --aspect-ratio 9:16 --format mp4")


def main() -> None:
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        show_info()
        sys.exit(0)
        
    if "--version" in args or "-v" in args:
        utils.print(f"{info.name} v{info.version}")
        sys.exit(0)

    if not config.urls or not config.urls[0]:
        show_info()
        sys.exit(1)

    start_time = time.perf_counter()

    if engine.start():
        end_time = time.perf_counter()
        duration = end_time - start_time
        utils.info(f"Done in {int(duration)} seconds")

        if config.open:
            utils.open_file(engine.file)
        else:
            utils.notify("Video Complete")


if __name__ == "__main__":
    main()
