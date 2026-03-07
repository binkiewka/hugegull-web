import os
import sys

from utils import utils

try:
    import tomllib
except ImportError:
    import tomli as tomllib


class Config:
    def __init__(self):
        self.fps = 30
        self.crf = 30
        self.duration = 45.0
        self.min_clip_duration = 3.0
        self.avg_clip_duration = 6.0
        self.max_clip_duration = 9.0
        self.path = os.path.dirname(os.path.abspath(__file__))
        self.env_url = os.environ.get("HUGE_URL", "")


        self.read_args()
        self.make_dirs()
        self.read_file()

        self.temp_dir = os.path.join(self.path, "temp")
        self.output_dir = os.path.join(self.path, "output")

    def make_dirs(self):
        self.config_path = os.path.expanduser("~/.config/hugegull/config.toml")
        self.config_dir = os.path.dirname(self.config_path)

        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir, exist_ok=True)

        if not os.path.exists(self.config_path):
            with open(self.config_path, "w") as f:
                f.write("")

    def read_args(self):
        if len(sys.argv) >= 3:
            self.url = sys.argv[1]
            self.name = sys.argv[2]
        elif len(sys.argv) == 2:
            arg = sys.argv[1]

            if utils.is_url(arg) or os.path.exists(arg):
                self.url = arg
                self.name = get_random_name()
            else:
                self.url = self.env_url
                self.name = arg
        else:
            self.url = self.env_url
            self.name = get_random_name()

    def read_file(self):
        with open(self.config_path, "rb") as f:
            self.config_data = tomllib.load(f)

        if "duration" in self.config_data:
            self.duration = float(self.config_data["duration"])

        if "fps" in self.config_data:
            self.fps = int(self.config_data["fps"])

        if "crf" in self.config_data:
            self.crf = int(self.config_data["crf"])

        if "path" in self.config_data:
            self.path = self.config_data["path"]


config = Config()