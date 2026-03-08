from __future__ import annotations

import os
import sys
import time
import tomllib

from utils import utils


class Config:
    def __init__(self) -> None:
        self.urls: list[str] = []
        self.name = ""
        self.fps = 30
        self.crf = 30
        self.duration = 45.0
        self.min_clip_duration = 3.0
        self.avg_clip_duration = 6.0
        self.max_clip_duration = 9.0
        self.path = os.path.dirname(os.path.abspath(__file__))
        self.info_name = "hugegull"
        self.info_version = "0.0.0"
        self.open = False
        self.fade = 0.03
        self.gpu = ""
        self.config = ""

        self.env_url = utils.get_env("HUGE_URL")
        self.env_name = utils.get_env("HUGE_NAME")

        self.read_args()

        self.config_file = self.config or "~/.config/hugegull/config.toml"
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

    def read_args(self) -> None:
        if "--open" in sys.argv:
            self.open = True
            sys.argv.remove("--open")

        if "--config" in sys.argv:
            self.get_arg("config", "config")

        if "--url" in sys.argv:
            self.get_multiple_args("url", "urls")

        if "--name" in sys.argv:
            self.get_arg("name", "name")

        if not self.urls:
            self.urls.append(self.env_url)

        if not self.name:
            self.name = self.env_name or utils.get_random_name()

    def read_config_file(self) -> None:
        with open(self.config_path, "rb") as f:
            config_data = tomllib.load(f)

        # How long should the video aim to be
        if "duration" in config_data:
            self.duration = float(config_data["duration"])

        # Frames per second
        if "fps" in config_data:
            self.fps = int(config_data["fps"])

        # A bigger crf means lower quality
        # 28 is considered good enough
        if "crf" in config_data:
            self.crf = int(config_data["crf"])

        # Path where files are saved
        if "path" in config_data:
            self.path = config_data["path"]

        # Little gap between clips like 0.03 (seconds)
        if "fade" in config_data:
            self.fade = config_data["fade"]

        # Either "amd" or "nvidia"
        if "gpu" in config_data:
            self.gpu = config_data["gpu"]

        # How long can clips be
        if "max_clip_duration" in config_data:
            self.max_clip_duration = config_data["max_clip_duration"]

        # Clip duration is often close to this
        if "avg_clip_duration" in config_data:
            self.avg_clip_duration = config_data["avg_clip_duration"]

        # The smallest clip duration
        if "min_clip_duration" in config_data:
            self.min_clip_duration = config_data["min_clip_duration"]


config = Config()
