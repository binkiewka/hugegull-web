class Utils:
    def get_clipboard_text():
        try:
            if shutil.which("xclip"):
                result = subprocess.run(
                    ["xclip", "-o", "-selection", "clipboard"],
                    capture_output=True,
                    text=True
                )

                if result.returncode == 0:
                    return result.stdout.strip()

            if shutil.which("wl-paste"):
                result = subprocess.run(
                    ["wl-paste"],
                    capture_output=True,
                    text=True
                )

                if result.returncode == 0:
                    return result.stdout.strip()

        except Exception as e:
            print(f"Clipboard error: {e}", "class:error")

        return ""

    def notify_done():
        if abort_event.is_set():
            return

        title = "🤯 hugegull"
        message = "Video Complete"

        try:
            subprocess.run(["notify-send", title, message], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error sending notification: {e}", "class:error")

    def get_random_name():
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