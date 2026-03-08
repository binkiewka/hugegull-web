from __future__ import annotations

import os
import random
import subprocess
import json
import shutil
from typing import Any

from config import config
from utils import utils


class Engine:
    @staticmethod
    def resolve_with_ytdlp(url: str) -> tuple[dict[str, Any], float]:
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
            return {}, 0.0

        try:
            metadata = json.loads(result.stdout)
            duration = 0.0

            if "duration" in metadata:
                if metadata["duration"] is not None:
                    duration = float(metadata["duration"])

            data = {}

            if "requested_formats" in metadata:
                if len(metadata["requested_formats"]) >= 2:
                    v_data = metadata["requested_formats"][0]["url"]
                    a_url = metadata["requested_formats"][1]["url"]
                    data = {"video": v_data, "audio": a_url}
                else:
                    data = {
                        "video": metadata["requested_formats"][0]["url"],
                        "audio": None,
                    }
            else:
                data = {"video": metadata.get("url"), "audio": None}

            return data, duration

        except Exception as e:
            utils.error(f"Error parsing yt-dlp output: {e}")
            return {}, 0.0

    @staticmethod
    def extract_clip(
        start: float,
        duration: float,
        video_url: str,
        audio_url: str | None,
        output_path: str,
        output_format: str = "mpegts"
    ) -> bool:
        command = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel", "error"
        ]

        command.extend(["-ss", str(start), "-i", video_url])

        if audio_url:
            if audio_url != video_url:
                command.extend(["-ss", str(start), "-i", audio_url])

        command.extend(["-t", str(duration)])

        if audio_url:
            if audio_url != video_url:
                command.extend(["-map", "0:v:0", "-map", "1:a:0"])
            else:
                command.extend(["-map", "0:v:0", "-map", "0:a:0?"])
        else:
            command.extend(["-map", "0:v:0", "-map", "0:a:0?"])

        # strictly force framerate, regenerate timestamps, and sync audio clock
        command.extend([
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-fps_mode", "cfr",
            "-c:a", "aac",
            "-af", "aresample=async=1",
            "-fflags", "+genpts",
            "-avoid_negative_ts", "make_zero",
            "-muxdelay", "0",
            "-f", output_format,
            output_path
        ])

        try:
            subprocess.run(command, check=True)
            return True
        except subprocess.CalledProcessError as e:
            utils.info(f"FFmpeg extraction failed: {e}")
            return False

    @staticmethod
    def get_stream_duration(url: str) -> float:
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

        try:
            metadata = json.loads(result.stdout)

            if "format" in metadata:
                if "duration" in metadata["format"]:
                    return float(metadata["format"]["duration"])

        except Exception as e:
            utils.error(f"Error parsing ffprobe output: {e}")

        return 0.0

    def __init__(self) -> None:
        self.url = config.url
        self.data: dict[str, Any] = {}
        self.clips: list[str] = []
        self.duration = 0.0
        self.prepare()

    def prepare(self) -> None:
        os.makedirs(config.project_dir, exist_ok=True)
        os.makedirs(config.output_dir, exist_ok=True)

        self.file = os.path.join(config.output_dir, f"{config.name}.mp4")
        counter = 1

        while os.path.exists(self.file):
            self.file = os.path.join(config.output_dir, f"{config.name}_{counter}.mp4")
            counter += 1

    def start(self) -> None:
        if os.path.isfile(self.url):
            self.get_stream_duration(self.url)
        else:
            if utils.is_site(self.url):
                self.data, self.duration = self.resolve_with_ytdlp(self.url)
            else:
                self.get_stream_duration(self.url)

        if self.duration <= 0:
            utils.info("Could not determine stream duration or stream is live/endless.")
            shutil.rmtree(config.project_dir, ignore_errors=True)
            return

        self.generate_random_clips()
        self.concatenate_clips()

    def generate_clip_sections(self) -> list[dict[str, Any]]:
        duration = config.duration
        sections: list[dict[str, Any]] = []
        current_sum = 0.0

        end_buffer = 2.0
        safe_duration = self.duration - end_buffer

        while current_sum < duration:
            clip_length = random.triangular(
                config.min_clip_duration,
                config.max_clip_duration,
                config.avg_clip_duration,
            )

            if current_sum + clip_length > duration:
                clip_length = duration - current_sum

            if clip_length < config.min_clip_duration:
                clip_length = config.min_clip_duration

            max_start = safe_duration - clip_length

            if max_start <= 0:
                break

            start = random.uniform(0, max_start)
            sections.append({"start": start, "duration": clip_length})
            current_sum += clip_length

        return sections

    def generate_random_clips(self) -> None:
        sections = self.generate_clip_sections()
        total_sections = len(sections)
        video_url = self.data.get("video", self.url)
        audio_url = self.data.get("audio")

        for i in range(total_sections):
            section = sections[i]
            start = section["start"]
            duration = section["duration"]
            name = os.path.join(config.project_dir, f"temp_clip_{i + 1}.mp4")

            utils.action(
                f"Clip {i + 1}/{total_sections} starting at {round(start)}s (Duration: {round(duration)}s)"
            )

            success = self.extract_clip(
                start=start,
                duration=duration,
                video_url=video_url,
                audio_url=audio_url,
                output_path=name,
            )

            if success:
                self.clips.append(name)

    def concatenate_clips(self) -> None:
        if not self.clips:
            utils.error("No clips to concatenate.")
            return

        list_file = os.path.join(config.project_dir, "concat_list.txt")

        with open(list_file, "w") as f:
            for clip in self.clips:
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
            self.file,
        ]

        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode != 0:
            utils.error("Error concatenating clips:")
            utils.error(result.stderr)
        else:
            shutil.rmtree(config.project_dir, ignore_errors=True)
            utils.info(f"Saved: {self.file}")


engine = Engine()
