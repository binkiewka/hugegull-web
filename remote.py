from Log import log

class Remote:
    def is_url(s):
        return s.startswith(("http", "https"))

    def requires_ytdlp(s):
        if is_url(s):
            if "youtube.com" in s or "youtu.be" in s or "twitch.tv" in s:
                return True

        return False

    def resolve_with_ytdlp(url):
        log.add("Resolving URL via yt-dlp...", "class:info")

        command = [
            "yt-dlp",
            "-f",
            "bestvideo[height<=1080]+bestaudio/best",
            "--dump-json",
            url,
        ]

        result = run_cancellable_command(command)

        if abort_event.is_set():
            return url, 0.0

        if result.returncode != 0:
            log.add("Error resolving URL. yt-dlp output:", "class:error")
            log.add(result.stderr, "class:error")
            return url, 0.0

        try:
            metadata = json.loads(result.stdout)
            duration = 0.0

            if "duration" in metadata:
                if metadata["duration"] is not None:
                    duration = float(metadata["duration"])

            if "requested_formats" in metadata:
                if len(metadata["requested_formats"]) >= 2:
                    v_url = metadata["requested_formats"][0]["url"]
                    a_url = metadata["requested_formats"][1]["url"]
                    return {"video": v_url, "audio": a_url}, duration
                else:
                    return {
                        "video": metadata["requested_formats"][0]["url"],
                        "audio": None,
                    }, duration
            else:
                return {"video": metadata.get("url"), "audio": None}, duration

        except Exception as e:
            log.add(f"Error parsing yt-dlp output: {e}", "class:error")
            return url, 0.0