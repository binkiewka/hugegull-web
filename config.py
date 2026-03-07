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

        self.default_url = os.environ.get("huge_url", "")
        self.config_path = os.path.expanduser("~/.config/hugegull/config.toml")
        self.config_dir = os.path.dirname(self.config_path)

        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir, exist_ok=true)

        if not os.path.exists(self.config_path):
            with open(self.config_path, "w") as f:
                f.write("")

        self.read_file()

        self.temp_dir = os.path.join(path, "temp")
        self.output_dir = os.path.join(path, "output")

    def read_file(self):
        with open(self.config_path, "rb") as f:
            self.config_data = tomllib.load(f)

        if "duration" in config_data:
            self.duration = float(config_data["duration"])

        if "fps" in config_data:
            self.fps = int(config_data["fps"])

        if "crf" in config_data:
            self.crf = int(config_data["crf"])

        if "path" in config_data:
            self.path = config_data["path"]


    config = Config()