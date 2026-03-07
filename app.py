from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, VSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.widgets import Button, TextArea, Frame
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.utils import get_cwidth
from prompt_toolkit.keys import Keys

from config import config
from utils import utils


class App:
    def __init__(self):
        self.version = "1.2"
        self.log_lines = []
        self.max_lines = 200

        self.url_input = TextArea(
            text=config.default_url,
            prompt=" URL: ",
            multiline=False,
            accept_handler=self.accept_url,
        )

        self.output_window = Window(
            content=FormattedTextControl(
                self.get_log_text,
                focusable=True
            ),
            right_margins=[ScrollbarMargin(display_arrows=True)],
            always_hide_cursor=True,
            wrap_lines=True,
        )

        self.paste_button = self.make_button("Paste", self.paste_clicked)
        self.start_button = self.make_button("Start", self.start_clicked)
        self.abort_button = self.make_button("Abort", self.abort_clicked)
        self.clear_button = self.make_button("Clear", self.clear_clicked)
        self.open_button = self.make_button("Open", self.open_clicked)
        self.exit_button = self.make_button("Exit", self.exit_clicked)

        # Adding a dummy Window() at the end acts as a spacer to consume the rest of the empty space
        self.button_container = VSplit(
            [
                self.paste_button,
                self.start_button,
                self.abort_button,
                self.clear_button,
                self.open_button,
                self.exit_button,
                Window(),
            ],
            padding=2,
        )

        self.root_container = HSplit(
            [
                Frame(
                    HSplit([self.url_input, self.button_container]),
                    title=f"HugeGull v{self.version}",
                ),
                Frame(self.output_window),
            ]
        )

        self.layout = Layout(self.root_container)

        self.style = Style.from_dict(
            {
                "info": "cyan",
                "success": "green bold",
                "error": "red bold",
                "warning": "yellow",
                "frame.label": "bold",
                "button": "fg: white",
            }
        )

        self.kb = KeyBindings()

        @self.kb.add("c-c")
        def _(event):
            self.abort_clicked()
            event.app.exit()

        @self.kb.add(Keys.ScrollUp)
        def _(event):
            self.output_window.vertical_scroll -= 3

            if self.output_window.vertical_scroll < 0:
                self.output_window.vertical_scroll = 0

        @self.kb.add(Keys.ScrollDown)
        def _(event):
            info = self.output_window.render_info

            if info:
                max_scroll = max(0, info.content_height - info.window_height)
                self.output_window.vertical_scroll += 3

                if self.output_window.vertical_scroll > max_scroll:
                    self.output_window.vertical_scroll = max_scroll

        @self.kb.add(Keys.PageUp)
        def _(event):
            info = self.output_window.render_info

            if info:
                self.output_window.vertical_scroll -= info.window_height

                if self.output_window.vertical_scroll < 0:
                    self.output_window.vertical_scroll = 0

        @self.kb.add(Keys.PageDown)
        def _(event):
            info = self.output_window.render_info

            if info:
                max_scroll = max(0, info.content_height - info.window_height)
                self.output_window.vertical_scroll += info.window_height

                if self.output_window.vertical_scroll > max_scroll:
                    self.output_window.vertical_scroll = max_scroll

        self.app = Application(
            layout=self.layout,
            key_bindings=self.kb,
            style=self.style,
            mouse_support=True,
            full_screen=True,
        )

        self.log("Ready. Paste a URL and press Enter or click Start.", "class:info")

    def start_clicked(self):
        from engine import engine

        url = self.url_input.text.strip()

        if not url:
            self.log("Please enter a URL first.", "class:error")
            return

        engine.start(url)

    def abort_clicked(self):
        from engine import engine

        self.log("Aborting process...", "class:warning")
        engine.abort()

    def clear_clicked(self):
        self.log_lines.clear()
        self.output_window.vertical_scroll = 0
        get_app().invalidate()

    def open_clicked(self):
        utils.open_file_manager(config.output_dir)

    def paste_clicked(self):
        clip_text = utils.get_clipboard_text()

        if utils.is_url(clip_text):
            self.url_input.text = clip_text
        else:
            self.log("Clipboard does not contain a valid URL.", "class:error")

    def exit_clicked(self):
        self.abort_clicked()
        get_app().exit()

    def accept_url(self, buff):
        self.start_clicked()
        return True

    def start(self):
        return self.app.run()

    def log(self, text, style="class:info"):
        info = self.output_window.render_info
        do_scroll = True

        if info:
            max_scroll = max(0, info.content_height - info.window_height)
            if max_scroll - info.vertical_scroll > 10:
                do_scroll = False

        self.log_lines.append((style, str(text) + "\n"))

        if len(self.log_lines) > self.max_lines:
            self.log_lines.pop(0)

        if do_scroll:
            # Setting it to a massive integer forces the Window to clamp
            # it perfectly to the maximum possible bottom scroll position.
            self.output_window.vertical_scroll = 9999999

        app = get_app()

        if app:
            app.invalidate()

    def get_log_text(self):
        return FormattedText(self.log_lines)

    def make_button(self, text, handler):
        return Button(
            text=text,
            handler=handler,
            left_symbol="",
            right_symbol="",
            width=get_cwidth(text) + 2,
        )


app = App()
