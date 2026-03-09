from __future__ import annotations

import os
import sys
import time
import tomllib

from utils import utils


class Config:
    def __init__(self) -> None:
        # Core settings
        self.urls: list[str] = []
        self.name = ""
        self.fps = 30
        self.crf = 28
        self.duration = 45.0
        self.min_clip_duration = 3.0
        self.avg_clip_duration = 6.0
        self.max_clip_duration = 9.0
        self.path = os.path.dirname(os.path.abspath(__file__))
        self.info_name = "hugegull-web"
        self.info_version = "0.0.0"
        self.open = False
        self.fade = 0.03
        self.gpu = ""
        self.config = ""
        
        # New feature flags
        self.preview = False
        self.dry_run = False
        self.skip_start = 0.0
        self.skip_end = 0.0
        self.resume = False
        self.shuffle_clips = False
        self.sort_by = "index"  # "index", "random"
        self.aspect_ratio = ""  # "16:9", "9:16", "1:1", "4:5", or "" for original
        self.output_format = "mp4"  # "mp4", "webm", "mov"

        self.env_url = utils.get_env("HUGE_URL")
        self.env_name = utils.get_env("HUGE_NAME")

        self.read_args()

        self.config_file = self.config or "~/.config/hugegull-web/config.toml"
        self.config_path = os.path.expanduser(self.config_file)
        self.config_dir = os.path.dirname(self.config_path)

        self.make_dirs()
        self.read_config_file()

        self.temp_dir = os.path.join(self.path, "temp")
        self.output_dir = os.path.join(self.path, "output")

        run_id = str(int(time.time() * 1000))
        self.project_dir = os.path.join(self.temp_dir, f"project_{run_id}")

    def make_dirs(self) -> None:
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir, exist_ok=True)

        if not os.path.exists(self.config_path):
            with open(self.config_path, "w") as f:
                f.write("")

    def get_multiple_args(self, c: str, k: str) -> None:
        values = []

        while f"--{c}" in sys.argv:
            arg_idx = sys.argv.index(f"--{c}")

            if arg_idx + 1 < len(sys.argv):
                values.append(sys.argv[arg_idx + 1])
                sys.argv.pop(arg_idx + 1)
                sys.argv.pop(arg_idx)
            else:
                print(f"Error: Missing argument value for --{c}")
                sys.exit(1)

        setattr(self, k, values)

    def get_arg(self, c: str, k: str) -> None:
        arg_idx = sys.argv.index(f"--{c}")

        if arg_idx + 1 < len(sys.argv):
            setattr(self, k, sys.argv[arg_idx + 1])
            sys.argv.pop(arg_idx + 1)
            sys.argv.pop(arg_idx)
        else:
            print(f"Error: Missing argument value for --{c}")
            sys.exit(1)

    def has_arg(self, c: str) -> bool:
        """Check if argument exists without consuming it"""
        return f"--{c}" in sys.argv

    def read_flag(self, c: str, k: str) -> None:
        """Read a boolean flag"""
        if f"--{c}" in sys.argv:
            setattr(self, k, True)
            sys.argv.remove(f"--{c}")

    def read_args(self) -> None:
        # Boolean flags
        self.read_flag("open", "open")
        self.read_flag("preview", "preview")
        self.read_flag("dry-run", "dry_run")
        self.read_flag("resume", "resume")
        self.read_flag("shuffle", "shuffle_clips")
        
        # String arguments
        if "--config" in sys.argv:
            self.get_arg("config", "config")

        if "--url" in sys.argv:
            self.get_multiple_args("url", "urls")

        if "--name" in sys.argv:
            self.get_arg("name", "name")
            
        if "--gpu" in sys.argv:
            self.get_arg("gpu", "gpu")
            
        if "--aspect-ratio" in sys.argv:
            self.get_arg("aspect-ratio", "aspect_ratio")
            
        if "--format" in sys.argv:
            self.get_arg("format", "output_format")
            
        if "--sort-by" in sys.argv:
            self.get_arg("sort-by", "sort_by")

        if "--skip-start" in sys.argv:
            arg_idx = sys.argv.index("--skip-start")
            if arg_idx + 1 < len(sys.argv):
                self.skip_start = float(sys.argv[arg_idx + 1])
                sys.argv.pop(arg_idx + 1)
                sys.argv.pop(arg_idx)
                
        if "--skip-end" in sys.argv:
            arg_idx = sys.argv.index("--skip-end")
            if arg_idx + 1 < len(sys.argv):
                self.skip_end = float(sys.argv[arg_idx + 1])
                sys.argv.pop(arg_idx + 1)
                sys.argv.pop(arg_idx)

        if not self.urls:
            self.urls.append(self.env_url)

        if not self.name:
            self.name = self.env_name or ""

    def read_config_file(self) -> None:
        try:
            with open(self.config_path, "rb") as f:
                config_data = tomllib.load(f)
        except Exception:
            return

        # Core settings
        if "duration" in config_data:
            self.duration = float(config_data["duration"])
        if "fps" in config_data:
            self.fps = int(config_data["fps"])
        if "crf" in config_data:
            self.crf = int(config_data["crf"])
        if "path" in config_data:
            self.path = config_data["path"]
        if "fade" in config_data:
            self.fade = config_data["fade"]
        if "gpu" in config_data:
            self.gpu = config_data["gpu"]
        if "max_clip_duration" in config_data:
            self.max_clip_duration = float(config_data["max_clip_duration"])
        if "avg_clip_duration" in config_data:
            self.avg_clip_duration = float(config_data["avg_clip_duration"])
        if "min_clip_duration" in config_data:
            self.min_clip_duration = float(config_data["min_clip_duration"])
            
        # New feature settings
        if "skip_start" in config_data:
            self.skip_start = float(config_data["skip_start"])
        if "skip_end" in config_data:
            self.skip_end = float(config_data["skip_end"])
        if "aspect_ratio" in config_data:
            self.aspect_ratio = config_data["aspect_ratio"]
        if "output_format" in config_data:
            self.output_format = config_data["output_format"]


config = Config()
