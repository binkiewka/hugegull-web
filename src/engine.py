from __future__ import annotations

import os
import random
import subprocess
import json
import shutil
import concurrent.futures
import hashlib
from typing import Any
from dataclasses import dataclass, asdict

from config import config
from utils import utils


@dataclass
class ClipSection:
    """Represents a clip section to extract"""
    start: float
    duration: float
    source: dict[str, Any]
    scene_score: float = 0.0
    index: int = 0


class Engine:
    def __init__(self) -> None:
        self.sources: list[dict[str, Any]] = []
        self.clips: list[str] = []
        self.workers = 8
        self.max_width = 0
        self.max_height = 0
        self.video_title: str | None = None
        self.state_file: str | None = None
        self.clip_sections: list[ClipSection] = []
        self.total_clips: int = 0
        self.completed_clips: int = 0

    def prepare(self) -> None:
        os.makedirs(config.project_dir, exist_ok=True)
        os.makedirs(config.output_dir, exist_ok=True)

        # Use video title for naming if available and no custom name
        if not config.name and self.video_title:
            safe_title = "".join(c for c in self.video_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            config.name = safe_title[:50]  # Limit length
        
        if not config.name:
            config.name = utils.get_random_name()

        self.file = os.path.join(config.output_dir, f"{config.name}.{config.output_format}")
        counter = 1

        while os.path.exists(self.file):
            self.file = os.path.join(config.output_dir, f"{config.name}_{counter}.{config.output_format}")
            counter += 1

        # Set up state file for resume capability
        self.state_file = os.path.join(config.project_dir, "state.json")

    def prepare_sources(self) -> None:
        for url in config.urls:
            source: dict[str, Any] = {
                "url": url,
                "v_data": url,
                "a_url": None,
                "duration": 0.0,
                "width": 0,
                "height": 0,
            }

            if os.path.isfile(url):
                info = self.get_stream_info(url)
                source.update(info)
            else:
                if utils.is_site(url):
                    yt_data = self.resolve_with_ytdlp(url)

                    if yt_data is not None:
                        source.update(yt_data)
                        
                        # Store video title for naming
                        if yt_data.get("title"):
                            self.video_title = yt_data.get("title")

                        v_data = source.get("v_data")

                        if v_data is None:
                            v_data = ""

                        info = self.get_stream_info(str(v_data))
                        source["width"] = info["width"]
                        source["height"] = info["height"]

                        if source["duration"] == 0.0:
                            source["duration"] = info["duration"]
                else:
                    info = self.get_stream_info(url)
                    source.update(info)

            raw_duration = source.get("duration")
            duration = 0.0

            if raw_duration is not None:
                try:
                    duration = float(raw_duration)
                except ValueError:
                    duration = 0.0

            raw_width = source.get("width")
            width = 0

            if raw_width is not None:
                width = int(raw_width)

            raw_height = source.get("height")
            height = 0

            if raw_height is not None:
                height = int(raw_height)

            if duration > 0 and width > 0 and height > 0:
                self.sources.append(source)

                if width > self.max_width:
                    self.max_width = width

                if height > self.max_height:
                    self.max_height = height
            else:
                utils.info(f"Could not determine valid data for {url}, skipping.")

    def start(self) -> bool:
        utils.info(f"Starting: {config.name} | {int(config.duration)}s")
        
        # Check for resume state
        if config.resume and os.path.exists(self.state_file):
            if self.load_state():
                utils.info("Resuming from previous session...")
            else:
                self.prepare()
                self.prepare_sources()
        else:
            self.prepare()
            self.prepare_sources()

        if len(self.sources) == 0:
            utils.info(
                "No valid sources found in the pool. Stream is live/endless or invalid."
            )

            shutil.rmtree(config.project_dir, ignore_errors=True)
            return False

        # Generate clip plan
        if not self.clip_sections:
            if config.scene_detection:
                self.clip_sections = self.generate_scene_based_sections()
            else:
                self.clip_sections = self.generate_random_sections()
            
            self.total_clips = len(self.clip_sections)
            self.save_state()

        # Preview mode - just show what would be extracted
        if config.preview or config.dry_run:
            return self.show_preview()

        # Extract clips with progress tracking
        self.completed_clips = sum(1 for section in self.clip_sections 
                                   if os.path.exists(os.path.join(config.project_dir, f"temp_clip_{section.index + 1}.mp4")))
        
        utils.info(f"Extracting {self.total_clips} clips ({self.completed_clips} already done)...")
        self.generate_clips_from_sections()
        
        # Reorder clips if shuffle enabled
        if config.shuffle_clips:
            random.shuffle(self.clips)
        elif config.sort_by == "scene_score" and config.scene_detection:
            # Sort by scene change intensity (most dynamic first)
            self.clips.sort(key=lambda x: self.get_clip_score(x), reverse=True)
        
        return self.concatenate_clips()

    def resolve_with_ytdlp(self, url: str) -> dict[str, Any] | None:
        cookie_args = [
            [],
        ]

        if os.path.isfile("cookies.txt"):
            cookie_args.append(["--cookies", "cookies.txt"])

        cookie_args.extend([
            ["--cookies-from-browser", "firefox"],
            ["--cookies-from-browser", "chrome"]
        ])

        result = None
        errors = []

        for args in cookie_args:
            command = [
                "yt-dlp",
                "--no-playlist",
                "--no-warnings"
            ]

            command.extend(args)

            command.extend([
                "-f",
                "bv*[height<=1080]+ba/b[height<=1080]/bv+ba/b",
                "--dump-json",
                url,
            ])

            result = subprocess.run(command, capture_output=True, text=True)

            if result.returncode == 0:
                break

            method_name = "default"

            if len(args) > 0:
                method_name = " ".join(args)

            errors.append(f"[{method_name}] -> {result.stderr.strip()}")

        if result is None or result.returncode != 0:
            utils.error(f"Error resolving URL {url}. All attempts failed:")

            for err in errors:
                utils.error(err)

            return None

        try:
            metadata = json.loads(result.stdout)
            duration = 0.0

            if "duration" in metadata:
                if metadata["duration"] is not None:
                    duration = float(metadata["duration"])

            title = metadata.get("title", "")

            if "requested_formats" in metadata:
                if len(metadata["requested_formats"]) >= 2:
                    v_data = metadata["requested_formats"][0]["url"]
                    a_url = metadata["requested_formats"][1]["url"]

                    return {"v_data": v_data, "a_url": a_url, "duration": duration, "title": title}
                else:
                    return {"v_data": metadata["requested_formats"][0]["url"], "a_url": None, "duration": duration, "title": title}
            else:
                return {"v_data": metadata.get("url"), "a_url": None, "duration": duration, "title": title}

        except Exception as e:
            utils.error(f"Error parsing yt-dlp output: {e}")
            return None

    def detect_scenes(self, source: dict[str, Any]) -> list[tuple[float, float]]:
        """Detect scene changes using ffmpeg scene filter with sampling for long videos"""
        v_data = source["v_data"]
        duration = source["duration"]
        
        # Skip intros/outros if configured
        start_offset = config.skip_start
        end_offset = config.skip_end
        
        if start_offset + end_offset >= duration:
            return []
        
        analysis_duration = duration - start_offset - end_offset
        
        # For long videos, analyze in chunks to avoid processing entire video
        max_analysis_time = 300  # 5 minutes max analysis time
        max_scenes = 50  # Limit number of scenes
        
        # Calculate how many segments to sample
        if analysis_duration > max_analysis_time:
            # Sample multiple segments throughout the video
            num_segments = 5
            segment_duration = max_analysis_time / num_segments
            segment_starts = [
                start_offset + (analysis_duration - segment_duration * num_segments) * i / (num_segments - 1)
                for i in range(num_segments)
            ]
            utils.info(f"Sampling {num_segments} segments for scene detection (video is {int(duration/60)}min long)...")
        else:
            # Short video - analyze the whole thing
            segment_starts = [start_offset]
            segment_duration = analysis_duration
            utils.info(f"Detecting scenes (this may take a moment)...")
        
        scenes = []
        for seg_start in segment_starts:
            # Use ffmpeg scene detection on segment
            command = [
                "ffmpeg",
                "-ss", str(seg_start),
                "-t", str(segment_duration),
                "-i", v_data,
                "-vf", f"select='gt(scene,{config.scene_threshold})',showinfo",
                "-f", "null",
                "-",
            ]
            
            result = subprocess.run(command, capture_output=True, text=True)
            
            for line in result.stderr.split("\n"):
                if "pts_time:" in line:
                    try:
                        # Extract timestamp from showinfo output
                        time_str = line.split("pts_time:")[1].split()[0]
                        timestamp = float(time_str) + seg_start
                        
                        # Apply skip offsets
                        if timestamp < start_offset or timestamp > duration - end_offset:
                            continue
                        
                        # Avoid duplicates (scenes within 2 seconds)
                        if not any(abs(timestamp - s) < 2.0 for s in scenes):
                            scenes.append(timestamp)
                            
                        if len(scenes) >= max_scenes:
                            break
                    except (IndexError, ValueError):
                        continue
            
            if len(scenes) >= max_scenes:
                break
        
        return sorted(scenes)

    def generate_scene_based_sections(self) -> list[ClipSection]:
        """Generate clip sections based on scene detection"""
        target_duration = config.duration
        sections: list[ClipSection] = []
        current_sum = 0.0
        end_buffer = 2.0
        
        for source in self.sources:
            scenes = self.detect_scenes(source)
            
            if not scenes:
                # Fall back to random if no scenes detected
                utils.info("No scenes detected, falling back to random selection")
                return self.generate_random_sections()
            
            safe_duration = source["duration"] - config.skip_start - config.skip_end - end_buffer
            
            # Sort scenes by position
            scenes.sort()
            
            # Create clips around scene changes
            for i, scene_time in enumerate(scenes):
                if current_sum >= target_duration:
                    break
                
                # Determine clip boundaries around scene
                clip_length = random.triangular(
                    config.min_clip_duration,
                    config.max_clip_duration,
                    config.avg_clip_duration,
                )
                
                if current_sum + clip_length > target_duration:
                    clip_length = target_duration - current_sum
                
                if clip_length < config.min_clip_duration:
                    continue
                
                # Center clip on scene change, but respect boundaries
                half_clip = clip_length / 2
                start = max(config.skip_start, scene_time - half_clip)
                max_start = min(scene_time + half_clip, source["duration"] - config.skip_end - clip_length)
                
                if start > max_start:
                    start = max_start
                
                if start < config.skip_start or start + clip_length > source["duration"] - config.skip_end:
                    continue
                
                # Calculate scene score (distance from previous scene indicates change intensity)
                scene_score = 0.5
                if i > 0:
                    scene_score = min(1.0, (scene_time - scenes[i-1]) / 10.0)
                
                sections.append(ClipSection(
                    start=start,
                    duration=clip_length,
                    source=source,
                    scene_score=scene_score,
                    index=len(sections)
                ))
                current_sum += clip_length
        
        return sections

    def generate_random_sections(self) -> list[ClipSection]:
        """Generate random clip sections (original behavior)"""
        target_duration = config.duration
        sections: list[ClipSection] = []
        current_sum = 0.0
        end_buffer = 2.0

        while current_sum < target_duration:
            source = random.choice(self.sources)
            safe_duration = source["duration"] - config.skip_start - config.skip_end - end_buffer

            if safe_duration <= 0:
                continue

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
                continue

            start = random.uniform(config.skip_start, config.skip_start + max_start)
            
            sections.append(ClipSection(
                start=start,
                duration=clip_length,
                source=source,
                index=len(sections)
            ))
            current_sum += clip_length

        return sections

    def show_preview(self) -> bool:
        """Show what clips would be extracted without actually doing it"""
        utils.info(f"\n📋 PREVIEW MODE - {len(self.clip_sections)} clips planned:\n")
        
        total_duration = 0.0
        for i, section in enumerate(self.clip_sections, 1):
            source_url = section.source.get("url", "unknown")[:50]
            scene_info = f" (scene score: {section.scene_score:.2f})" if config.scene_detection else ""
            
            utils.info(f"Clip {i}/{len(self.clip_sections)}: {section.start:.1f}s - {section.start + section.duration:.1f}s "
                      f"(duration: {section.duration:.1f}s){scene_info}")
            utils.info(f"  Source: {source_url}...")
            total_duration += section.duration
        
        utils.info(f"\n✅ Total planned duration: {total_duration:.1f}s")
        utils.info(f"📝 Use --preview to see this without generating")
        utils.info(f"🚀 Remove --dry-run to actually generate the video\n")
        
        return True

    def save_state(self) -> None:
        """Save current state for resume capability"""
        if not self.state_file:
            return
        
        state = {
            "sources": self.sources,
            "clip_sections": [
                {
                    "start": s.start,
                    "duration": s.duration,
                    "source_index": self.sources.index(s.source) if s.source in self.sources else 0,
                    "scene_score": s.scene_score,
                    "index": s.index,
                }
                for s in self.clip_sections
            ],
            "total_clips": self.total_clips,
            "completed_clips": self.completed_clips,
            "config": {
                "name": config.name,
                "duration": config.duration,
            }
        }
        
        try:
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            utils.error(f"Failed to save state: {e}")

    def load_state(self) -> bool:
        """Load previous state for resume capability"""
        if not self.state_file or not os.path.exists(self.state_file):
            return False
        
        try:
            with open(self.state_file, "r") as f:
                state = json.load(f)
            
            self.sources = state.get("sources", [])
            self.total_clips = state.get("total_clips", 0)
            self.completed_clips = state.get("completed_clips", 0)
            
            # Reconstruct clip sections
            self.clip_sections = []
            for s in state.get("clip_sections", []):
                source_idx = s.get("source_index", 0)
                if source_idx < len(self.sources):
                    self.clip_sections.append(ClipSection(
                        start=s["start"],
                        duration=s["duration"],
                        source=self.sources[source_idx],
                        scene_score=s.get("scene_score", 0.0),
                        index=s["index"]
                    ))
            
            return len(self.clip_sections) > 0
            
        except Exception as e:
            utils.error(f"Failed to load state: {e}")
            return False

    def get_clip_score(self, clip_path: str) -> float:
        """Get scene score for a clip from its filename"""
        try:
            index = int(os.path.basename(clip_path).split("_")[2].split(".")[0]) - 1
            if 0 <= index < len(self.clip_sections):
                return self.clip_sections[index].scene_score
        except (IndexError, ValueError):
            pass
        return 0.0

    def generate_clips_from_sections(self) -> None:
        """Extract clips from planned sections with progress tracking"""
        
        def extract_with_progress(i: int, section: ClipSection) -> str | None:
            # Skip if already exists
            expected_path = os.path.join(config.project_dir, f"temp_clip_{section.index + 1}.mp4")
            if os.path.exists(expected_path):
                self.completed_clips += 1
                utils.info(f"✓ Clip {section.index + 1}/{self.total_clips} already exists")
                return expected_path
            
            result = self.extract_single_clip(section.index, {
                "start": section.start,
                "duration": section.duration,
                "source": section.source
            })
            
            if result:
                self.completed_clips += 1
                self.save_state()  # Save progress after each clip
            
            return result

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {
                executor.submit(extract_with_progress, i, section): i 
                for i, section in enumerate(self.clip_sections)
            }

            for future in concurrent.futures.as_completed(futures):
                clip_path = future.result()

                if clip_path is not None:
                    self.clips.append(clip_path)

        # Sort by original index to maintain order (unless shuffled later)
        self.clips.sort(
            key=lambda x: int(os.path.basename(x).split("_")[2].split(".")[0])
        )

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
        modes_to_try = self.get_encoding_modes()

        for mode in modes_to_try:
            command = ["ffmpeg"]

            if mode == "amd":
                command.extend(["-vaapi_device", "/dev/dri/renderD128"])
            elif mode == "nvidia":
                command.extend(["-hwaccel", "cuda"])
            elif mode == "intel":
                command.extend(["-vaapi_device", "/dev/dri/renderD128"])

            command.extend(["-ss", str(start), "-i", v_data])

            if is_split_stream:
                command.extend(["-ss", str(start), "-i", a_url])

            fade_out_start = duration - config.fade
            
            # Apply aspect ratio transformation if needed
            pad_w, pad_h = self.get_output_dimensions()

            if pad_w % 2 != 0:
                pad_w += 1

            if pad_h % 2 != 0:
                pad_h += 1

            vf_filter = f"scale={pad_w}:{pad_h}:force_original_aspect_ratio=decrease,pad={pad_w}:{pad_h}:(ow-iw)/2:(oh-ih)/2,fps={config.fps},setsar=1"

            if mode == "amd" or mode == "intel":
                vf_filter = f"{vf_filter},format=nv12,hwupload"

            af_filter = f"afade=t=in:st=0:d={config.fade},afade=t=out:st={fade_out_start}:d={config.fade}"

            # Ensure we only take exactly one video and one audio stream
            if is_split_stream:
                command.extend(["-map", "0:v:0", "-map", "1:a:0"])
            else:
                command.extend(["-map", "0:v:0", "-map", "0:a:0?"])

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
            elif mode == "intel":
                command.extend(
                    ["-c:v", "h264_qsv", "-global_quality", str(config.crf)]
                )
            else:
                command.extend(
                    ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(config.crf)]
                )

            # Force uniform audio attributes across all extracted clips
            command.extend(
                [
                    "-c:a",
                    "aac",
                    "-ar",
                    "48000",
                    "-ac",
                    "2",
                    "-video_track_timescale",
                    "90000",
                    "-y",
                    name,
                ]
            )

            utils.action(
                f"Clip {i + 1}/{self.total_clips} starting at {round(start)}s (Duration: {round(duration)}s) ({mode})"
            )

            try:
                result = subprocess.run(command, capture_output=True, text=True)

                if result.returncode == 0:
                    return name

                utils.error(f"Error extracting clip {i + 1} using {mode}:")
                utils.error(result.stderr)

                if mode != modes_to_try[-1]:
                    utils.info(f"Retrying clip {i + 1} with fallback...")

            except Exception as e:
                utils.error(f"Exception extracting clip {i + 1} using {mode}: {e}")

                if mode != modes_to_try[-1]:
                    utils.info(f"Retrying clip {i + 1} with fallback...")

        return None

    def get_encoding_modes(self) -> list[str]:
        """Get list of encoding modes to try based on config"""
        modes = []
        
        if config.gpu == "amd":
            modes = ["amd", "cpu"]
        elif config.gpu == "nvidia":
            modes = ["nvidia", "cpu"]
        elif config.gpu == "intel":
            modes = ["intel", "cpu"]
        else:
            modes = ["cpu"]
        
        return modes

    def get_output_dimensions(self) -> tuple[int, int]:
        """Get output dimensions based on aspect ratio preset"""
        if config.aspect_ratio == "16:9":
            return (1920, 1080)
        elif config.aspect_ratio == "9:16":
            return (1080, 1920)
        elif config.aspect_ratio == "1:1":
            return (1080, 1080)
        elif config.aspect_ratio == "4:5":
            return (1080, 1350)
        else:
            # Original dimensions
            return (self.max_width, self.max_height)

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
            return False
        else:
            # Clean up state file on success
            if self.state_file and os.path.exists(self.state_file):
                os.remove(self.state_file)
            
            shutil.rmtree(config.project_dir, ignore_errors=True)
            utils.info(f"Saved: {self.file}")

        return True

    def get_stream_info(self, url: str) -> dict[str, Any]:
        command = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            url,
        ]

        result = subprocess.run(command, capture_output=True, text=True)
        info = {"duration": 0.0, "width": 0, "height": 0}

        if result.returncode != 0:
            return info

        try:
            metadata = json.loads(result.stdout)

            if "format" in metadata:
                if "duration" in metadata["format"]:
                    info["duration"] = float(metadata["format"]["duration"])

            if "streams" in metadata:
                for stream in metadata["streams"]:
                    if stream.get("codec_type") == "video":
                        info["width"] = int(stream.get("width", 0))
                        info["height"] = int(stream.get("height", 0))
                        break
        except Exception:
            pass

        return info


engine = Engine()
