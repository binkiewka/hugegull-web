import tomllib
from pathlib import Path


class Info:
    name: str
    version: str

    def __init__(self) -> None:
        toml_path = Path(__file__).parent / "info.toml"

        with open(toml_path, "rb") as f:
            info_dict = tomllib.load(f)

        for key, value in info_dict.items():
            setattr(self, key, value)


info = Info()
