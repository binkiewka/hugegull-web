from __future__ import annotations

import os
import random
import shutil
import time
from typing import Any

from engine import engine
from config import config
from utils import utils


class Stream:
    def __init__(self) -> None:
        self.url = config.url
        self.data: dict[str, Any] = {}
        self.duration = 0.0
        self.active_clips: list[dict[str, Any]] = []
        self.sequence = 0
        self.opened = False
        self.stream_file = os.path.join(config.output_dir, "stream.m3u8")
        self.prepare()

    def prepare(self) -> None:
        os.makedirs(config.project_dir, exist_ok=True)
        os.makedirs(config.segment_dir, exist_ok=True)

        for f in os.listdir(config.segment_dir):
            if f.endswith(".ts"):
                os.remove(os.path.join(config.segment_dir, f))

    def start(self) -> None:
        if os.path.isfile(self.url):
            self.duration = engine.get_stream_duration(self.url)
        else:
            if utils.is_site(self.url):
                self.data, self.duration = engine.resolve_with_ytdlp(self.url)
            else:
                self.duration = engine.get_stream_duration(self.url)

        if self.duration <= 0:
            utils.info("Could not determine stream duration or stream is live/endless.")
            shutil.rmtree(config.project_dir, ignore_errors=True)
            return

        self.stream_loop()

    def stream_loop(self) -> None:
        utils.info(f"Stream at: {self.stream_file}")

        while len(self.active_clips) < config.buffer:
            self.generate_and_append_clip()

        self.update_playlist()

        while True:
            start_time = time.time()

            # Get the duration of the newly generated clip
            clip_duration = self.generate_and_append_clip()

            if len(self.active_clips) > config.buffer:
                oldest_clip = self.active_clips.pop(0)
                try:
                    os.remove(oldest_clip["path"])
                except OSError:
                    pass

            self.update_playlist()

            # Pace the loop to match real-time playback
            if clip_duration:
                elapsed_time = time.time() - start_time
                sleep_time = clip_duration - elapsed_time

                # Leave a tiny bit of breathing room so generation stays slightly ahead
                sleep_time = sleep_time - 1.0

                if sleep_time > 0:
                    time.sleep(sleep_time)
            else:
                # If extraction failed, just wait a moment before retrying
                time.sleep(1)

    def generate_and_append_clip(self) -> float | None:
        clip_length = random.triangular(
            config.min_clip_duration,
            config.max_clip_duration,
            config.avg_clip_duration,
        )

        end_buffer = 2.0
        safe_duration = self.duration - end_buffer
        max_start = safe_duration - clip_length

        if max_start <= 0:
            start = 0.0
            clip_length = safe_duration
        else:
            start = random.uniform(0, max_start)

        # Predict the next sequence and filename, but don't save it to self.sequence yet
        next_sequence = self.sequence + 1
        clip_filename = f"segment_{next_sequence}.ts"
        clip_path = os.path.join(config.segment_dir, clip_filename)

        video_url = self.data.get("video", self.url)
        audio_url = self.data.get("audio")

        utils.action(
            f"Extracting segment {next_sequence} at {round(start)}s (Duration: {round(clip_length)}s)"
        )

        success = engine.extract_clip(
            start=start,
            duration=clip_length,
            video_url=video_url,
            audio_url=audio_url,
            output_path=clip_path,
            output_format="mpegts",
        )

        if not success:
            return None

        # Only increment sequence if extraction succeeded
        self.sequence = next_sequence

        self.active_clips.append(
            {"filename": clip_filename, "path": clip_path, "duration": clip_length}
        )

        return clip_length

    def update_playlist(self) -> None:
        if not self.active_clips:
            return

        target_duration = int(max(clip["duration"] for clip in self.active_clips) + 1)
        start_sequence = (self.sequence - len(self.active_clips)) + 1

        with open(self.stream_file, "w") as f:
            f.write("#EXTM3U\n")
            f.write("#EXT-X-VERSION:3\n")
            f.write(f"#EXT-X-TARGETDURATION:{target_duration}\n")
            f.write(f"#EXT-X-MEDIA-SEQUENCE:{start_sequence}\n")

            for clip in self.active_clips:
                f.write(f"#EXTINF:{clip['duration']:.6f},\n")
                f.write(f"{clip['filename']}\n")

            if config.open and (not self.opened):
                utils.open_file(self.stream_file)
                self.opened = True


stream = Stream()
