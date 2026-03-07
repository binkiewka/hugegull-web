import subprocess
import os
import sys
import time
import shutil

from config import config
from utils import utils
from engine import engine


def main():
    if not config.url:
        utils.print("Usage: python main.py [<m3u8_url>] [<output_name>]")
        utils.print("Or set HUGE_URL environment variable.")
        sys.exit(1)

    run_id = str(int(time.time() * 1000))
    run_temp_dir = os.path.join(config.temp_dir, f"project_{run_id}")

    os.makedirs(run_temp_dir, exist_ok=True)
    os.makedirs(config.output_dir, exist_ok=True)

    output_file = os.path.join(config.output_dir, f"{config.name}.mp4")
    counter = 1

    while os.path.exists(output_file):
        output_file = os.path.join(config.output_dir, f"{config.name}_{counter}.mp4")
        counter += 1

    utils.info("Starting...")
    total_duration = 0.0

    if utils.is_site(config.url):
        config.url, total_duration = engine.resolve_with_ytdlp(config.url)
    else:
        total_duration = engine.get_stream_duration(config.url)

    if total_duration <= 0:
        utils.info("Could not determine stream duration or stream is live/endless.")
        shutil.rmtree(run_temp_dir, ignore_errors=True)
        return

    clips = engine.generate_random_clips(config.url, total_duration, run_temp_dir)
    engine.concatenate_clips(clips, output_file, run_temp_dir)
    notify_done()


def notify_done():
    title = "🤯 hugegull"
    message = "Video Complete"

    try:
        subprocess.run(["notify-send", title, message], check=True)
    except subprocess.CalledProcessError as e:
        utils.print(f"Error sending notification: {e}")


if __name__ == "__main__":
    main()
