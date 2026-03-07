import subprocess
import random
import os
import json
import sys
import time
import re
import shutil
import threading

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, VSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.widgets import Button, TextArea, Frame
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import FormattedText

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


# --- UI Logging System ---
log_lines = []

def ui_log(text, style="class:info"):
    log_lines.append((style, str(text) + "\n"))

    if len(log_lines) > 200:
        log_lines.pop(0)

    app = get_app()
    if app:
        app.invalidate()

def get_log_text():
    return FormattedText(log_lines)


# --- Core Logic ---
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
    ui_log("Resolving URL via yt-dlp...", "class:info")

    command = [
        "yt-dlp",
        "-f",
        "bestvideo[height<=1080]+bestaudio/best",
        "--dump-json",
        url,
    ]

    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode != 0:
        ui_log("Error resolving URL. yt-dlp output:", "class:error")
        ui_log(result.stderr, "class:error")
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
                return {
                    "video": metadata["requested_formats"][0]["url"],
                    "audio": None,
                }, duration
        else:
            return {"video": metadata.get("url"), "audio": None}, duration

    except Exception as e:
        ui_log(f"Error parsing yt-dlp output: {e}", "class:error")
        return url, 0.0


def generate_clip_sections(target_duration, total_stream_duration):
    sections = []
    current_sum = 0.0

    end_buffer = 2.0
    safe_duration = total_stream_duration - end_buffer

    while current_sum < target_duration:
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

    ui_log(f"Targeting {total_sections} random clips for this run...", "class:info")

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
                "-t", str(current_clip_duration),
                "-vf", f"fps={FPS}",
                "-c:v", "libx264",
                "-crf", str(CRF),
                "-c:a", "aac",
                "-video_track_timescale", "90000",
                "-y", output_name,
            ]
        )

        ui_log(f"Extracting clip {i + 1}/{total_sections} starting at {start_time:.2f}s (Duration: {current_clip_duration:.2f}s)...", "class:warning")

        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode != 0:
            ui_log(f"Error extracting clip {i}:", "class:error")
            ui_log(result.stderr, "class:error")
            continue

        clip_files.append(output_name)

    return clip_files


def concatenate_clips(clip_files, output_file, run_temp_dir):
    if not clip_files:
        ui_log("No clips to concatenate.", "class:error")
        return

    list_file = os.path.join(run_temp_dir, "concat_list.txt")

    with open(list_file, "w") as f:
        for clip in clip_files:
            abs_clip_path = os.path.abspath(clip)
            f.write(f"file '{abs_clip_path}'\n")

    command = [
        "ffmpeg", "-f", "concat", "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        "-video_track_timescale", "90000",
        "-y", output_file,
    ]

    ui_log("Concatenating clips...", "class:info")
    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode != 0:
        ui_log("Error concatenating clips:", "class:error")
        ui_log(result.stderr, "class:error")
    else:
        ui_log("Cleaning up temporary files...", "class:info")
        shutil.rmtree(run_temp_dir, ignore_errors=True)
        ui_log(f"Video saved as {output_file}", "class:success")


def get_stream_duration(url):
    command = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", url,
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


def notify_done():
    title = "🤯 hugegull"
    message = "Video Complete"

    try:
        subprocess.run(["notify-send", title, message], check=True)
    except subprocess.CalledProcessError as e:
        ui_log(f"Error sending notification: {e}", "class:error")


def run_pipeline(stream_url):
    base_name = get_random_name()
    run_id = str(int(time.time() * 1000))
    run_temp_dir = os.path.join(TEMP_DIR, f"project_{run_id}")

    os.makedirs(run_temp_dir, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    output_file = os.path.join(OUTPUT_DIR, f"{base_name}.mp4")
    counter = 1

    while os.path.exists(output_file):
        output_file = os.path.join(OUTPUT_DIR, f"{base_name}_{counter}.mp4")
        counter += 1

    ui_log("Fetching stream duration...", "class:info")
    total_duration = 0.0

    if requires_ytdlp(stream_url):
        stream_url, total_duration = resolve_with_ytdlp(stream_url)
    else:
        total_duration = get_stream_duration(stream_url)

    if total_duration <= 0:
        ui_log("Could not determine stream duration or stream is live/endless.", "class:error")
        shutil.rmtree(run_temp_dir, ignore_errors=True)
        return

    ui_log(f"Stream duration: {total_duration} seconds.", "class:success")

    clips = generate_random_clips(stream_url, total_duration, run_temp_dir)
    concatenate_clips(clips, output_file, run_temp_dir)
    notify_done()


# --- TUI Application ---
def main():
    # URL Input
    default_url = os.environ.get("HUGE_URL", "")
    url_input = TextArea(
        text=default_url,
        prompt=" URL: ",
        multiline=False,
    )

    # Output Window
    output_window = Window(content=FormattedTextControl(get_log_text))

    # Button Handlers
    def start_clicked():
        url = url_input.text.strip()

        if not url:
            ui_log("Please enter a URL first.", "class:error")
            return

        ui_log(f"Starting job for: {url}", "class:success")
        threading.Thread(target=run_pipeline, args=(url,), daemon=True).start()

    def clear_clicked():
        log_lines.clear()
        get_app().invalidate()

    def exit_clicked():
        get_app().exit()

    # Buttons Layout
    start_button = Button("Start", handler=start_clicked)
    clear_button = Button("Clear Output", handler=clear_clicked)
    exit_button = Button("Exit", handler=exit_clicked)

    button_container = VSplit(
        [start_button, clear_button, exit_button],
        padding=2
    )

    # Main Layout Assembly
    root_container = HSplit([
        Frame(
            HSplit([url_input, button_container]),
            title="HugeGull"
        ),
        Frame(output_window, title="Output Log"),
    ])

    layout = Layout(root_container)

    # Styles
    style = Style.from_dict({
        "info": "cyan",
        "success": "green bold",
        "error": "red bold",
        "warning": "yellow",
        "frame.label": "bold",
    })

    # Keybindings
    kb = KeyBindings()

    @kb.add("c-c")
    def _(event):
        event.app.exit()

    # Create and run application
    app = Application(
        layout=layout,
        key_bindings=kb,
        style=style,
        mouse_support=True,
        full_screen=True,
    )

    ui_log("Ready. Paste a URL and click Start.", "class:info")
    app.run()


if __name__ == "__main__":
    main()