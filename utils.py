class Utils:
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
        if is_url(s):
            if ("youtube.com" in s) or ("youtu.be") in s or ("twitch.tv" in s):
                return True

        return False


utils = Utils()