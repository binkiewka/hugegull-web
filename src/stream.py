from __future__ import annotations

import os
import random
import subprocess
import json
import shutil
import time
from typing import Any

from config import config
from utils import utils


class StreamEngine:
    def __init__(self) -> None:
        self.url = config.url
        self.data: dict[str, Any] = {}
        self.duration = 0.0
        self.active_clips: list[dict[str, Any]] = []
        self.sequence = 0
        self.stream_file = os.path.join(config.output_dir, "stream.m3u8")
        self.prepare()

    def prepare(self) -> None:
        os.makedirs(config.project_dir, exist_ok=True)
        os.makedirs(config.output_dir, exist_ok=True)

        for f in os.listdir(config.output_dir):
            if f.endswith(".ts") or f.endswith(".m3u8"):
                os.remove(os.path.join(config.output_dir, f))

    def start(self) -> None:
        if os.path.isfile(self.url):
            self.duration = Engine.get_stream_duration(self.url)
        else:
            if utils.is_site(self.url):
                self.data, self.duration = Engine.resolve_with_ytdlp(self.url)
            else:
                self.duration = Engine.get_stream_duration(self.url)

        if self.duration <= 0:
            utils.info("Could not determine stream duration or stream is live/endless.")
            shutil.rmtree(config.project_dir, ignore_errors=True)
            return

        self.stream_loop()

    def stream_loop(self) -> None:
        utils.info(f"Starting continuous generation. Playlist at: {self.stream_file}")

        while len(self.active_clips) < config.buffer:
            self.generate_and_append_clip()

        self.update_playlist()

        while True:
            self.generate_and_append_clip()

            if len(self.active_clips) > config.buffer:
                oldest_clip = self.active_clips.pop(0)
                try:
                    os.remove(oldest_clip["path"])
                except OSError:
                    pass

            self.update_playlist()

            time.sleep(1)

    def generate_and_append_clip(self) -> None:
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

        self.sequence += 1
        clip_filename = f"segment_{self.sequence}.ts"
        clip_path = os.path.join(config.output_dir, clip_filename)

        video_url = self.data.get("video", self.url)
        audio_url = self.data.get("audio")

        utils.action(f"Extracting segment {self.sequence} at {round(start)}s (Duration: {round(clip_length)}s)")

        success = Engine.extract_clip(
            start=start,
            duration=clip_length,
            video_url=video_url,
            audio_url=audio_url,
            output_path=clip_path,
            output_format="mpegts",
        )

        if not success:
            return

        self.active_clips.append(
            {
                "filename": clip_filename,
                "path": clip_path,
                "duration": clip_length
            }
        )

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

if __name__ == "__main__":
    engine = StreamEngine()
    engine.start()