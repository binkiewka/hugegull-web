import os
import random
import subprocess
import json
import shutil

from config import config
from utils import utils


class Engine:
    def resolve_with_ytdlp(self, url):
        command = [
            "yt-dlp",
            "-f",
            "bestvideo[height<=1080]+bestaudio/best",
            "--dump-json",
            url,
        ]

        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode != 0:
            utils.error("Error resolving URL. yt-dlp output:")
            utils.error(result.stderr)
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
            utils.error(f"Error parsing yt-dlp output: {e}")
            return url, 0.0

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

            utils.action(
                f"Clip {i + 1}/{total_sections} starting at {start_time:.2f}s (Duration: {current_clip_duration:.2f}s)"
            )

            result = subprocess.run(command, capture_output=True, text=True)

            if result.returncode != 0:
                utils.error(f"Error extracting clip {i}:")
                utils.error(result.stderr)
                continue

            clip_files.append(output_name)

        return clip_files

    def concatenate_clips(self, clip_files, output_file, run_temp_dir):
        if not clip_files:
            utils.error("No clips to concatenate.")
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

        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode != 0:
            utils.error("Error concatenating clips:")
            utils.error(result.stderr)
        else:
            # Remove the unique run directory entirely
            shutil.rmtree(run_temp_dir, ignore_errors=True)
            utils.done(f"Video saved as {output_file}")

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

        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode != 0:
            return 0.0

        metadata = json.loads(result.stdout)

        if "format" in metadata:
            if "duration" in metadata["format"]:
                return float(metadata["format"]["duration"])

        return 0.0


engine = Engine()
