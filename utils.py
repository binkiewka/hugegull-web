import os
import re
import time
import random
import subprocess


class Utils:
    def __init__(self):
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

    def get_random_name(self):
        dict_path = "/usr/share/dict/words"

        if os.path.exists(dict_path):
            with open(dict_path, "r") as f:
                words = f.readlines()

            valid_words = []

            for w in words:
                clean_w = w.strip().lower().replace("'", "")

                if re.match(r"^[a-z]+$", clean_w):
                    valid_words.append(clean_w)

            if len(valid_words) >= 2:
                selected = random.sample(valid_words, 2)
                return f"{selected[0]}_{selected[1]}"

        return str(int(time.time()))

    def is_url(self, s):
        return s.startswith(("http", "https"))

    def is_site(self, s):
        if self.is_url(s):
            if ("youtube.com" in s) or ("youtu.be") in s or ("twitch.tv" in s):
                return True

        return False

    def print(self, text, color=""):
        if color:
            color_key = color.lower()

            if color_key in self.ansi_colors:
                color_code = self.ansi_colors[color_key]
            else:
                color_code = ""

            print(f"{color_code}{text}{self.ansi_colors['reset']}")
        else:
            print(text)

    def error(self, text):
        self.print(text, "red")

    def action(self, text):
        self.print(text, "yellow")

    def info(self, text):
        self.print(text, "cyan")

    def get_env(self, what):
        return os.environ.get(what, "")

    def notify(self, message):
        title = "🤯 HugeGull"

        try:
            subprocess.run(["notify-send", title, message], check=True)
        except subprocess.CalledProcessError as e:
            utils.print(f"Error sending notification: {e}")


utils = Utils()
