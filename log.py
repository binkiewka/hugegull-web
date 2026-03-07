class Log:
    def __init__():
        self.log_lines = []
        self.max_lines = 200


    def add(self, text, style="class:info"):
        self.log_lines.append((style, str(text) + "\n"))

        if len(self.log_lines) > self.max_lines:
            self.log_lines.pop(0)

        app = get_app()
        if app:
            app.invalidate()


    def get_log_text():
        return FormattedText(log_lines)


    log = Log()