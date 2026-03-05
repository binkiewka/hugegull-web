# HUGEGULL
# video maker

# Notes:
# You can use the HUGE_URL env var.
# The output name can be ommitted to use a random name.

# Installation:

# git clone this somewhere.
# Make a shell alias to python /path/to/hugegull/hugegull.py
# alias hgg="python ~/code/hugegull/hugegull.py"

# Edit ~/.config/hugegull/hugegull.conf
# It is empty but you can make it look like this:

# clip_duration = 6
# num_clips = 10
# path = "/home/memphis/toilet"

# Usage:

# export HUGE_URL="https://something.m3u8"
# hgg

# Or:

# hgg "https://something.m3u8"

import subprocess
import random
import os
import json
import sys
import time
import re

try:
    import tomllib
except ImportError:
    import tomli as tomllib

# Configuration path setup
CONFIG_PATH = os.path.expanduser("~/.config/hugegull/config.toml")
CONFIG_DIR = os.path.dirname(CONFIG_PATH)

if not os.path.exists(CONFIG_DIR):
    os.makedirs(CONFIG_DIR, exist_ok=True)

if not os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, "w") as f:
        f.write("")

# Default configuration values
CLIP_DURATION = 6
NUM_CLIPS = 10
PATH = os.path.dirname(os.path.abspath(__file__))

# Read configuration from TOML
with open(CONFIG_PATH, "rb") as f:
    config_data = tomllib.load(f)

if "clip_duration" in config_data:
    CLIP_DURATION = int(config_data["clip_duration"])

if "num_clips" in config_data:
    NUM_CLIPS = int(config_data["num_clips"])

if "path" in config_data:
    PATH = config_data["path"]

# Resolve output and temp directories based on PATH
TEMP_DIR = os.path.join(PATH, "temp")
OUTPUT_DIR = os.path.join(PATH, "output")


def get_random_name():
    dict_path = "/usr/share/dict/words"

    if os.path.exists(dict_path):
        with open(dict_path, "r") as f:
            words = f.readlines()

        valid_words = []

        for w in words:
            clean_w = w.strip().lower().replace("'", "")

            if re.match(r"^[a-z]+$", clean_w):
                valid_words.append(clean_w)

        if len(valid_words) >= 2:
            selected = random.sample(valid_words, 2)
            return f"{selected[0]}_{selected[1]}"

    return str(int(time.time()))


def get_stream_duration(url):
    command = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        url,
    ]

    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode != 0:
        return 0.0

    metadata = json.loads(result.stdout)

    if "format" in metadata:
        if "duration" in metadata["format"]:
            return float(metadata["format"]["duration"])

    return 0.0


def generate_random_clips(url, total_duration, num_clips, clip_duration):
    clip_files = []
    max_start = total_duration - clip_duration

    if max_start <= 0:
        print("Stream is too short.")
        return []

    for i in range(num_clips):
        start_time = random.uniform(0, max_start)
        output_name = os.path.join(TEMP_DIR, f"temp_clip_{i}.mp4")

        command = [
            "ffmpeg",
            "-ss",
            str(start_time),
            "-i",
            url,
            "-t",
            str(clip_duration),
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-y",
            output_name,
        ]

        print(f"Extracting clip {i + 1}/{num_clips} starting at {start_time:.2f}s...")
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        clip_files.append(output_name)

    return clip_files


def concatenate_clips(clip_files, output_file):
    if not clip_files:
        print("No clips to concatenate.")
        return

    list_file = os.path.join(TEMP_DIR, "concat_list.txt")

    with open(list_file, "w") as f:
        for clip in clip_files:
            clip_basename = os.path.basename(clip)
            f.write(f"file '{clip_basename}'\n")

    command = [
        "ffmpeg",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        list_file,
        "-c",
        "copy",
        "-y",
        output_file,
    ]

    print("Concatenating clips...")
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("Cleaning up temporary files...")

    for clip in clip_files:
        os.remove(clip)

    os.remove(list_file)
    print(f"Video saved as {output_file}")


def main():
    stream_url = None
    base_name = None

    if len(sys.argv) >= 3:
        stream_url = sys.argv[1]
        base_name = sys.argv[2]
    elif len(sys.argv) == 2:
        arg = sys.argv[1]

        if arg.startswith("http"):
            stream_url = arg
            base_name = get_random_name()
        else:
            stream_url = os.environ.get("HUGE_URL")
            base_name = arg
    else:
        stream_url = os.environ.get("HUGE_URL")
        base_name = get_random_name()

    if not stream_url:
        print("Usage: python script.py [<m3u8_url>] [<output_name>]")
        print("Or set HUGE_URL environment variable.")
        sys.exit(1)

    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    output_file = os.path.join(OUTPUT_DIR, f"{base_name}.mp4")
    counter = 1

    while os.path.exists(output_file):
        output_file = os.path.join(OUTPUT_DIR, f"{base_name}_{counter}.mp4")
        counter += 1

    print("Fetching stream duration...")
    total_duration = get_stream_duration(stream_url)

    if total_duration <= 0:
        print("Could not determine stream duration or stream is live/endless.")
        return

    print(f"Stream duration: {total_duration} seconds.")
    clips = generate_random_clips(stream_url, total_duration, NUM_CLIPS, CLIP_DURATION)
    concatenate_clips(clips, output_file)


if __name__ == "__main__":
    main()
