from __future__ import annotations

import os
import sys
import time

from utils import utils

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore


class Config:
    def __init__(self) -> None:
        self.url = ""
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

        self.env_url = utils.get_env("HUGE_URL")
        self.env_name = utils.get_env("HUGE_NAME")

        self.read_args()
        self.make_dirs()
        self.read_file()
        self.read_info()

        self.temp_dir = os.path.join(self.path, "temp")
        self.output_dir = os.path.join(self.path, "output")

        run_id = str(int(time.time() * 1000))
        self.project_dir = os.path.join(self.temp_dir, f"project_{run_id}")

    def make_dirs(self) -> None:
        self.config_path = os.path.expanduser("~/.config/hugegull/config.toml")
        self.config_dir = os.path.dirname(self.config_path)

        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir, exist_ok=True)

        if not os.path.exists(self.config_path):
            with open(self.config_path, "w") as f:
                f.write("")

    def read_args(self) -> None:
        if len(sys.argv) >= 3:
            self.url = sys.argv[1]
            self.name = sys.argv[2]
        elif len(sys.argv) == 2:
            arg = sys.argv[1]

            if utils.is_url(arg) or os.path.exists(arg):
                self.url = arg

        if not self.url:
            self.url = self.env_url

        if not self.name:
            self.name = self.env_name or utils.get_random_name()

    def read_file(self) -> None:
        with open(self.config_path, "rb") as f:
            config_data = tomllib.load(f)

        if "duration" in config_data:
            self.duration = float(config_data["duration"])

        if "fps" in config_data:
            self.fps = int(config_data["fps"])

        if "crf" in config_data:
            self.crf = int(config_data["crf"])

        if "path" in config_data:
            self.path = config_data["path"]

    def read_info(self) -> None:
        with open("info.toml", "rb") as f:
            info = tomllib.load(f)

        if "name" in info:
            self.info_name = info["name"]

        if "version" in info:
            self.info_version = info["version"]


config = Config()
