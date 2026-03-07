from __future__ import annotations

import os
import random
import subprocess
from pathlib import Path


class Utils:
    def __init__(self) -> None:
        self.ansi_colors = {
            "black": "\033[30m",
            "red": "\033[31m",
            "green": "\033[32m",
            "yellow": "\033[33m",
            "blue": "\033[34m",
            "magenta": "\033[35m",
            "cyan": "\033[36m",
            "white": "\033[37m",
            "reset": "\033[0m",
        }

        self.words: list[str] = []

    def load_words(self) -> None:
        path = Path(__file__).parent / "nouns.txt"

        with open(path, "r") as f:
            self.words = [line.strip() for line in f]

    def get_random_name(self, n: int = 2, join_str: str = "_") -> str:
        if not self.words:
            self.load_words()

        selected = random.sample(self.words, n)
        return join_str.join(selected)

    def is_url(self, s: str) -> bool:
        return s.startswith(("http", "https"))

    def is_site(self, s: str) -> bool:
        domains = [
            "youtu.be",
            "youtube.com",
            "twitch.tv",
        ]

        return self.is_url(s) and any(d in s for d in domains)

    def print(self, text: str, color: str = "") -> None:
        if color:
            color_key = color.lower()

            if color_key in self.ansi_colors:
                color_code = self.ansi_colors[color_key]
            else:
                color_code = ""

            print(f"{color_code}{text}{self.ansi_colors['reset']}")
        else:
            print(text)

    def error(self, text: str) -> None:
        self.print(text, "red")

    def action(self, text: str) -> None:
        self.print(text, "yellow")

    def info(self, text: str) -> None:
        self.print(text, "cyan")

    def get_env(self, what: str) -> str:
        return os.environ.get(what, "")

    def notify(self, message: str) -> None:
        title = "🤯 hugegull"

        try:
            subprocess.run(["notify-send", title, message], check=True)
        except subprocess.CalledProcessError as e:
            utils.print(f"Error sending notification: {e}")

    def short_path(self, file_path: str) -> str:
        path = Path(file_path).resolve()
        home = Path.home()

        if path.is_relative_to(home):
            return str(Path("~") / path.relative_to(home))

        return str(path)

    def open_file(self, path: str) -> None:
        if not os.path.exists(path):
            self.error(f"Error: The path '{path}' does not exist.")
            return

        try:
            subprocess.Popen(
                ["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except Exception as e:
            self.error(f"Failed to open file: {e}")


utils = Utils()
