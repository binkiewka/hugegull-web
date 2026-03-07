import subprocess
import random
import os
import json
import sys
import time
import re
import shutil

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
DURATION = 45.0
PATH = os.path.dirname(os.path.abspath(__file__))
FPS = 30
CRF = 30

MIN_CLIP_DURATION = 3.0
AVG_CLIP_DURATION = 6.0
MAX_CLIP_DURATION = 9.0

# Read configuration from TOML
with open(CONFIG_PATH, "rb") as f:
    config_data = tomllib.load(f)

if "duration" in config_data:
    DURATION = float(config_data["duration"])

if "fps" in config_data:
    FPS = int(config_data["fps"])

if "crf" in config_data:
    CRF = int(config_data["crf"])

if "path" in config_data:
    PATH = config_data["path"]

# Resolve output and base temp directories based on PATH
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


def resolve_with_ytdlp(url):
    print("Resolving URL via yt-dlp...")

    command = [
        "yt-dlp",
        "-f",
        "bestvideo[height<=1080]+bestaudio/best",
        "--dump-json",
        url,
    ]

    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode != 0:
        print("Error resolving URL. yt-dlp output:")
        print(result.stderr)
        return url, 0.0

    try:
        metadata = json.loads(result.stdout)
        duration = 0.0

        if "duration" in metadata:
            if metadata["duration"] is not None:
                duration = float(metadata["duration"])

        if "requested_formats" in metadata:
            if len(metadata["requested_formats"]) >= 2:
                v_url = metadata["requested_formats"][0]["url"]
                a_url = metadata["requested_formats"][1]["url"]
                return {"video": v_url, "audio": a_url}, duration
            else:
                return {"video": metadata["requested_formats"][0]["url"], "audio": None}, duration
        else:
            return {"video": metadata.get("url"), "audio": None}, duration

    except Exception as e:
        print(f"Error parsing yt-dlp output: {e}")
        return url, 0.0


def generate_clip_sections(target_duration, total_stream_duration):
    sections = []
    current_sum = 0.0

    end_buffer = 2.0
    safe_duration = total_stream_duration - end_buffer

    while current_sum < target_duration:
        # Bias the duration heavily towards 6.0 seconds
        clip_length = random.triangular(
            MIN_CLIP_DURATION, MAX_CLIP_DURATION, AVG_CLIP_DURATION
        )

        if current_sum + clip_length > target_duration:
            clip_length = target_duration - current_sum

            if clip_length < MIN_CLIP_DURATION:
                clip_length = MIN_CLIP_DURATION

        max_start = safe_duration - clip_length

        if max_start <= 0:
            break

        start_time = random.uniform(0, max_start)
        sections.append({"start": start_time, "duration": clip_length})

        current_sum += clip_length

    return sections


def generate_random_clips(stream_data, total_duration, run_temp_dir):
    clip_files = []

    sections = generate_clip_sections(DURATION, total_duration)
    total_sections = len(sections)

    print(f"Targeting {total_sections} random clips for this run...")

    is_split_stream = False

    if isinstance(stream_data, dict):
        if stream_data.get("audio") is not None:
            is_split_stream = True

    v_url = stream_data

    if isinstance(stream_data, dict):
        v_url = stream_data["video"]

    for i in range(total_sections):
        section = sections[i]
        start_time = section["start"]
        current_clip_duration = section["duration"]

        output_name = os.path.join(run_temp_dir, f"temp_clip_{i + 1}.mp4")

        command = ["ffmpeg", "-ss", str(start_time), "-i", v_url]

        if is_split_stream:
            command.extend(["-ss", str(start_time), "-i", stream_data["audio"]])

        command.extend(
            [
                "-t",
                str(current_clip_duration),
                "-vf",
                f"fps={FPS}",
                "-c:v",
                "libx264",
                "-crf",
                str(CRF),
                "-c:a",
                "aac",
                "-video_track_timescale",
                "90000",
                "-y",
                output_name,
            ]
        )

        print(
            f"Extracting clip {i + 1}/{total_sections} starting at {start_time:.2f}s (Duration: {current_clip_duration:.2f}s)..."
        )

        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"Error extracting clip {i}:")
            print(result.stderr)
            continue

        clip_files.append(output_name)

    return clip_files


def concatenate_clips(clip_files, output_file, run_temp_dir):
    if not clip_files:
        print("No clips to concatenate.")
        return

    list_file = os.path.join(run_temp_dir, "concat_list.txt")

    with open(list_file, "w") as f:
        for clip in clip_files:
            abs_clip_path = os.path.abspath(clip)
            f.write(f"file '{abs_clip_path}'\n")

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
        "-video_track_timescale",
        "90000",
        "-y",
        output_file,
    ]

    print("Concatenating clips...")
    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode != 0:
        print("Error concatenating clips:")
        print(result.stderr)
    else:
        print("Cleaning up temporary files...")

        # Remove the unique run directory entirely
        shutil.rmtree(run_temp_dir, ignore_errors=True)
        print(f"Video saved as {output_file}")


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


def is_url(s):
    return s.startswith(("http", "https"))


def requires_ytdlp(s):
    if is_url(s):
        if "youtube.com" in s or "youtu.be" in s or "twitch.tv" in s:
            return True

    return False


def main():
    stream_url = None
    base_name = None

    if len(sys.argv) >= 3:
        stream_url = sys.argv[1]
        base_name = sys.argv[2]
    elif len(sys.argv) == 2:
        arg = sys.argv[1]

        # Check for both http URLs and local files
        if is_url(arg) or os.path.exists(arg):
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

    # Generate a unique temp directory for this specific run
    run_id = str(int(time.time() * 1000))
    run_temp_dir = os.path.join(TEMP_DIR, f"project_{run_id}")

    os.makedirs(run_temp_dir, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    output_file = os.path.join(OUTPUT_DIR, f"{base_name}.mp4")
    counter = 1

    while os.path.exists(output_file):
        output_file = os.path.join(OUTPUT_DIR, f"{base_name}_{counter}.mp4")
        counter += 1

    print("Fetching stream duration...")
    total_duration = 0.0

    if requires_ytdlp(stream_url):
        stream_url, total_duration = resolve_with_ytdlp(stream_url)
    else:
        total_duration = get_stream_duration(stream_url)

    if total_duration <= 0:
        print("Could not determine stream duration or stream is live/endless.")
        # Clean up the unused temp folder before exiting
        shutil.rmtree(run_temp_dir, ignore_errors=True)
        return

    print(f"Stream duration: {total_duration} seconds.")

    # Pass the unique temp directory downward
    clips = generate_random_clips(stream_url, total_duration, run_temp_dir)
    concatenate_clips(clips, output_file, run_temp_dir)
    notify_done()


def notify_done():
    title = "🤯 hugegull"
    message = "Video Complete"

    try:
        subprocess.run(["notify-send", title, message], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error sending notification: {e}")


if __name__ == "__main__":
    main()
