from __future__ import annotations

import os
import random
import subprocess
import json
import shutil
import concurrent.futures
from typing import Any

from config import config
from utils import utils


class Engine:
    def __init__(self) -> None:
        self.sources: list[dict[str, Any]] = []
        self.clips: list[str] = []
        self.workers = 8

    def prepare(self) -> None:
        os.makedirs(config.project_dir, exist_ok=True)
        os.makedirs(config.output_dir, exist_ok=True)

        self.file = os.path.join(config.output_dir, f"{config.name}.mp4")
        counter = 1

        while os.path.exists(self.file):
            self.file = os.path.join(config.output_dir, f"{config.name}_{counter}.mp4")
            counter += 1

    def prepare_sources(self) -> None:
        for url in config.urls:
            source = {"url": url, "v_data": url, "a_url": None, "duration": 0.0}

            if os.path.isfile(url):
                source["duration"] = self.get_stream_duration(url)
            else:
                if utils.is_site(url):
                    yt_data = self.resolve_with_ytdlp(url)

                    if yt_data is not None:
                        source.update(yt_data)
                else:
                    source["duration"] = self.get_stream_duration(url)

            raw_duration = source["duration"]
            duration = 0.0

            if raw_duration is not None:
                try:
                    duration = float(raw_duration)
                except ValueError:
                    duration = 0.0

            if duration > 0:
                self.sources.append(source)
            else:
                utils.info(f"Could not determine duration for {url}, skipping.")

    def start(self) -> bool:
        utils.info(f"Starting: {config.name} | {int(config.duration)}s")
        self.prepare()
        self.prepare_sources()

        if len(self.sources) == 0:
            utils.info(
                "No valid sources found in the pool. Stream is live/endless or invalid."
            )

            shutil.rmtree(config.project_dir, ignore_errors=True)
            return False

        self.generate_random_clips()
        return self.concatenate_clips()

    def resolve_with_ytdlp(self, url: str) -> dict[str, Any] | None:
        command = [
            "yt-dlp",
            "--no-playlist",
            "--no-warnings",
            "-f",
            "bestvideo[height<=1080]+bestaudio/best",
            "--dump-json",
            url,
        ]

        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode != 0:
            utils.error(f"Error resolving URL {url}. yt-dlp output:")
            utils.error(result.stderr)
            return None

        try:
            metadata = json.loads(result.stdout)
            duration = 0.0

            if "duration" in metadata:
                if metadata["duration"] is not None:
                    duration = float(metadata["duration"])

            if "requested_formats" in metadata:
                if len(metadata["requested_formats"]) >= 2:
                    v_data = metadata["requested_formats"][0]["url"]
                    a_url = metadata["requested_formats"][1]["url"]

                    return {"v_data": v_data, "a_url": a_url, "duration": duration}
                else:
                    return {
                        "v_data": metadata["requested_formats"][0]["url"],
                        "a_url": None,
                        "duration": duration,
                    }
            else:
                return {
                    "v_data": metadata.get("url"),
                    "a_url": None,
                    "duration": duration,
                }

        except Exception as e:
            utils.error(f"Error parsing yt-dlp output: {e}")
            return None

    def generate_clip_sections(self) -> list[dict[str, Any]]:
        duration = config.duration
        sections: list[dict[str, Any]] = []
        current_sum = 0.0
        end_buffer = 2.0

        while current_sum < duration:
            source = random.choice(self.sources)
            safe_duration = source["duration"] - end_buffer

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
                continue

            start = random.uniform(0, max_start)
            sections.append({"start": start, "duration": clip_length, "source": source})
            current_sum += clip_length

        return sections

    def extract_single_clip(self, i: int, section: dict[str, Any]) -> str | None:
        source = section["source"]
        start = section["start"]
        duration = section["duration"]
        v_data = source["v_data"]
        a_url = source["a_url"]

        is_split_stream = False

        if a_url is not None:
            is_split_stream = True

        name = os.path.join(config.project_dir, f"temp_clip_{i + 1}.mp4")
        modes_to_try = [config.gpu]

        if config.gpu in ("amd", "nvidia"):
            modes_to_try = [config.gpu, "cpu"]
        else:
            modes_to_try = ["cpu"]

        for mode in modes_to_try:
            command = ["ffmpeg"]

            if mode == "amd":
                command.extend(["-vaapi_device", "/dev/dri/renderD128"])
            elif mode == "nvidia":
                command.extend(["-hwaccel", "cuda"])

            command.extend(["-ss", str(start), "-i", v_data])

            if is_split_stream:
                command.extend(["-ss", str(start), "-i", a_url])

            fade_out_start = duration - config.fade
            vf_filter = f"fps={config.fps}"

            if mode == "amd":
                vf_filter = f"{vf_filter},format=nv12,hwupload"

            af_filter = f"afade=t=in:st=0:d={config.fade},afade=t=out:st={fade_out_start}:d={config.fade}"

            command.extend(
                [
                    "-t",
                    str(duration),
                    "-vf",
                    vf_filter,
                    "-af",
                    af_filter,
                ]
            )

            if mode == "amd":
                command.extend(
                    ["-c:v", "h264_vaapi", "-global_quality", str(config.crf)]
                )
            elif mode == "nvidia":
                command.extend(
                    ["-c:v", "h264_nvenc", "-cq", str(config.crf), "-preset", "p4"]
                )
            else:
                command.extend(
                    ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(config.crf)]
                )

            command.extend(
                [
                    "-c:a",
                    "aac",
                    "-video_track_timescale",
                    "90000",
                    "-y",
                    name,
                ]
            )

            utils.action(
                f"Clip {i + 1} starting at {round(start)}s (Duration: {round(duration)}s) ({mode})"
            )

            try:
                result = subprocess.run(command, capture_output=True, text=True)

                if result.returncode == 0:
                    return name

                utils.error(f"Error extracting clip {i + 1} using {mode}:")
                utils.error(result.stderr)

                if mode != modes_to_try[-1]:
                    utils.info(f"Retrying clip {i + 1} with CPU fallback...")

            except Exception as e:
                utils.error(f"Exception extracting clip {i + 1} using {mode}: {e}")

                if mode != modes_to_try[-1]:
                    utils.info(f"Retrying clip {i + 1} with CPU fallback...")

        return None

    def generate_random_clips(self) -> None:
        sections = self.generate_clip_sections()

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.workers
        ) as executor:
            futures = []

            for i in range(len(sections)):
                future = executor.submit(self.extract_single_clip, i, sections[i])

                futures.append(future)

            for future in concurrent.futures.as_completed(futures):
                clip_path = future.result()

                if clip_path is not None:
                    self.clips.append(clip_path)

        self.clips.sort(
            key=lambda x: int(os.path.basename(x).split("_")[2].split(".")[0])
        )

    def concatenate_clips(self) -> bool:
        if not self.clips:
            utils.error("No clips to concatenate.")
            return False

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

        return True

    def get_stream_duration(self, url: str) -> float:
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
