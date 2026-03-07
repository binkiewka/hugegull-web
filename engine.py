import subprocess
import random
import os
import json
import time
import shutil
import threading

from utils import utils
from config import config
from app import app


class CommandResult:
    def __init__(self, returncode, stdout, stderr):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class Engine:
    def __init__(self):
        self.abort_event = threading.Event()
        self.active_process = None
        self.process_lock = threading.Lock()
        self.is_running = False
        self.state_lock = threading.Lock()
        self.done_emoji = "🤯"

    def get_stream_duration(self, url):
        command = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            url,
        ]

        result = self.run_cancellable_command(command)

        if self.abort_event.is_set():
            return 0.0

        if result.returncode != 0:
            return 0.0

        metadata = json.loads(result.stdout)

        if "format" in metadata:
            if "duration" in metadata["format"]:
                return float(metadata["format"]["duration"])

        return 0.0

    def generate_clip_sections(self, target_duration, total_stream_duration):
        sections = []
        current_sum = 0.0

        end_buffer = 2.0
        safe_duration = total_stream_duration - end_buffer

        while current_sum < target_duration:
            clip_length = random.triangular(
                config.min_clip_duration,
                config.max_clip_duration,
                config.avg_clip_duration,
            )

            if current_sum + clip_length > target_duration:
                clip_length = target_duration - current_sum

                if clip_length < config.min_clip_duration:
                    clip_length = config.min_clip_duration

            max_start = safe_duration - clip_length

            if max_start <= 0:
                break

            start_time = random.uniform(0, max_start)
            sections.append({"start": start_time, "duration": clip_length})

            current_sum += clip_length

        return sections

    def generate_random_clips(self, stream_data, total_duration, run_temp_dir):
        clip_files = []
        sections = self.generate_clip_sections(config.duration, total_duration)
        total_sections = len(sections)

        app.log(
            f"Targeting {total_sections} random clips for this run...", "class:info"
        )

        is_split_stream = False

        if isinstance(stream_data, dict):
            if stream_data.get("audio") is not None:
                is_split_stream = True

        v_url = stream_data

        if isinstance(stream_data, dict):
            v_url = stream_data["video"]

        for i in range(total_sections):
            if self.abort_event.is_set():
                app.log("Clip generation aborted.", "class:error")
                break

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
                    f"fps={config.fps}",
                    "-c:v",
                    "libx264",
                    "-crf",
                    str(config.crf),
                    "-c:a",
                    "aac",
                    "-video_track_timescale",
                    "90000",
                    "-y",
                    output_name,
                ]
            )

            app.log(
                f"Extracting clip {i + 1}/{total_sections} starting at {start_time:.2f}s (Duration: {current_clip_duration:.2f}s)...",
                "class:warning",
            )

            result = self.run_cancellable_command(command)

            if self.abort_event.is_set():
                break

            if result.returncode != 0:
                app.log(f"Error extracting clip {i}:", "class:error")
                app.log(result.stderr, "class:error")
                continue

            clip_files.append(output_name)

        return clip_files

    def concatenate_clips(self, clip_files, output_file, run_temp_dir):
        if self.abort_event.is_set():
            return

        if not clip_files:
            app.log("No clips to concatenate.", "class:error")
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

        app.log("Concatenating clips...", "class:info")
        result = self.run_cancellable_command(command)

        if self.abort_event.is_set():
            app.log("Concatenation aborted.", "class:error")
            return

        if result.returncode != 0:
            app.log("Error concatenating clips:", "class:error")
            app.log(result.stderr, "class:error")
        else:
            app.log("Cleaning up temporary files...", "class:info")
            shutil.rmtree(run_temp_dir, ignore_errors=True)
            app.log(f"{self.done_emoji} Video saved as {output_file}", "class:success")

    def run_pipeline(self, stream_url):
        self.abort_event.clear()
        base_name = utils.get_random_name()
        run_id = str(int(time.time() * 1000))
        run_temp_dir = os.path.join(config.temp_dir, f"project_{run_id}")

        os.makedirs(run_temp_dir, exist_ok=True)
        os.makedirs(config.output_dir, exist_ok=True)

        output_file = os.path.join(config.output_dir, f"{base_name}.mp4")
        counter = 1

        while os.path.exists(output_file):
            output_file = os.path.join(config.output_dir, f"{base_name}_{counter}.mp4")
            counter += 1

        app.log("Fetching stream duration...", "class:info")
        total_duration = 0.0

        if self.requires_ytdlp(stream_url):
            stream_url, total_duration = self.resolve_with_ytdlp(stream_url)
        else:
            total_duration = self.get_stream_duration(stream_url)

        if self.abort_event.is_set():
            app.log("Process aborted during duration fetch.", "class:error")
            shutil.rmtree(run_temp_dir, ignore_errors=True)
            return

        if total_duration <= 0:
            app.log(
                "Could not determine stream duration or stream is live/endless.",
                "class:error",
            )

            shutil.rmtree(run_temp_dir, ignore_errors=True)
            return

        app.log(f"Stream duration: {total_duration} seconds.", "class:success")

        clips = self.generate_random_clips(stream_url, total_duration, run_temp_dir)
        self.concatenate_clips(clips, output_file, run_temp_dir)
        self.notify_done()

    def requires_ytdlp(self, s):
        if utils.is_url(s):
            if "youtube.com" in s or "youtu.be" in s or "twitch.tv" in s:
                return True

        return False

    def resolve_with_ytdlp(self, url):
        app.log("Resolving URL via yt-dlp...", "class:info")

        command = [
            "yt-dlp",
            "-f",
            "bestvideo[height<=1080]+bestaudio/best",
            "--dump-json",
            url,
        ]

        result = self.run_cancellable_command(command)

        if self.abort_event.is_set():
            return url, 0.0

        if result.returncode != 0:
            app.log("Error resolving URL. yt-dlp output:", "class:error")
            app.log(result.stderr, "class:error")
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
            app.log(f"Error parsing yt-dlp output: {e}", "class:error")
            return url, 0.0

    def run_cancellable_command(self, command):
        if self.abort_event.is_set():
            return CommandResult(-1, "", "Aborted by user.")

        with self.process_lock:
            try:
                self.active_process = subprocess.Popen(
                    command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )

            except Exception as e:
                return CommandResult(-1, "", str(e))

        stdout, stderr = self.active_process.communicate()
        returncode = self.active_process.returncode

        with self.process_lock:
            self.active_process = None

        return CommandResult(returncode, stdout, stderr)

    def start(self, url):
        with self.state_lock:
            if self.is_running:
                app.log("A job is already running.", "class:warning")
                return False

            self.is_running = True

        app.log(f"Starting job for: {url}", "class:success")
        threading.Thread(target=self.run_wrapper, args=(url,), daemon=True).start()
        return True

    def run_wrapper(self, url):
        try:
            self.run_pipeline(url)
        finally:
            with self.state_lock:
                self.is_running = False

    def notify_done(self):
        title = f"{self.done_emoji} hugegull"
        message = "Video Complete"

        try:
            subprocess.run(["notify-send", title, message], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error sending notification: {e}", "class:error")

    def abort(self):
        if not self.abort_event.is_set():
            self.abort_event.set()

            with self.process_lock:
                if self.active_process is not None:
                    self.active_process.terminate()


engine = Engine()
