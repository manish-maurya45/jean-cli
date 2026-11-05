import json
from contextlib import contextmanager

from rich import box
from rich.align import Align
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.padding import Padding
from rich.panel import Panel
from rich.rule import Rule
from rich.segment import Segment, Segments
from rich.style import Style as RichStyle
from rich.table import Table
from rich.text import Text

from prompt_toolkit.application import Application
from prompt_toolkit.input.ansi_escape_sequences import ANSI_SEQUENCES
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout.containers import HSplit, VSplit, Window, WindowAlign
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame, TextArea
from prompt_toolkit.widgets.base import Border

# Rounded corners for prompt_toolkit's Frame (inner input box)
Border.TOP_LEFT = "╭"
Border.TOP_RIGHT = "╮"
Border.BOTTOM_LEFT = "╰"
Border.BOTTOM_RIGHT = "╯"

# Shift+Enter, for terminals that report it. Mapped to Alt+Enter.
for _seq in ("\x1b[13;2u", "\x1b[27;2;13~"):
    ANSI_SEQUENCES[_seq] = (Keys.Escape, Keys.ControlM)


ACCENT = "#7aa2f7"
USER = "#9ece6a"
TOOL = "#e0af68"
MUTED = "#565f89"
BORDER = "#414868"

MAX_TOOL_OUTPUT_LINES = 12
MAX_INPUT_LINES = 10

MENU_ROWS = 8

# Sentinel returned by a prompt that was aborted because the terminal resized.
_RESIZED = object()

INPUT_STYLE = Style.from_dict({
    "outer": BORDER,
    "input frame.border": ACCENT,
    "input frame.label": f"bold {USER}",
    "prompt": f"bold {USER}",
    "text-area": "#c0caf5",
    "hint": MUTED,
    "menu": "bg:#161b2e",
    "menu.border": "bg:#161b2e #414868",
    "menu.name": "bg:#1f2a4a #c0caf5",
    "menu.meta": "bg:#1f2a4a #7f8bb8",
    "menu.current": "bg:#3d59a1 bold #ffffff",
    "menu.current.meta": "bg:#3d59a1 #c0caf5",
})

HINT = "enter  send   ·   /  commands   ·   shift+enter / alt+enter  new line   ·   ctrl-c  exit"
HINT_SHORT = "enter send · / commands · alt+enter newline · ctrl-c exit"
HINT_MIN_WIDTH = 110
APP_TITLE = " jean"

# ---------------------------------------------------------------- banner art

SPIDER = [
    "╲╲    ╲▄█▄╱    ╱╱",
    " ╲╲╲_ ▐███▌ _╱╱╱ ",
    "──═══▐█████▌═══──",
    " ╱╱╱‾ ▐███▌ ‾╲╲╲ ",
    "╱╱   ╱▐███▌╲   ╲╲",
    "╱    ╲ ▀█▀ ╱    ╲",
]

JEAN = [
    "     ██╗ ███████╗  █████╗  ███╗   ██╗",
    "     ██║ ██╔════╝ ██╔══██╗ ████╗  ██║",
    "     ██║ █████╗   ███████║ ██╔██╗ ██║",
    "██   ██║ ██╔══╝   ██╔══██║ ██║╚██╗██║",
    "╚█████╔╝ ███████╗ ██║  ██║ ██║ ╚████║",
    " ╚════╝  ╚══════╝ ╚═╝  ╚═╝ ╚═╝  ╚═══╝",
]

# # top-to-bottom gradient, one color per row
# GRADIENT = ["#ff6b6b", "#f25555", "#e23636", "#cc2b2b", "#b01e1e", "#8f1717"]
GRADIENT = ["#a9c7ff", "#8ab4ff", "#6a9bff", "#4f84f0", "#386ad6", "#2a52b0"]
LOGO_MIN_WIDTH = 66

def banner_logo():
    spider = Text("\n".join(SPIDER), style=f"bold {GRADIENT[2]}")

    name = Text()
    for i, line in enumerate(JEAN):
        name.append(line, style=f"bold {GRADIENT[i]}")
        if i != len(JEAN) - 1:
            name.append("\n")

    grid = Table.grid(padding=(0, 3))
    grid.add_column(vertical="middle")
    grid.add_column(vertical="middle")
    grid.add_row(spider, name)
    return Align.center(grid)


class Logo:
    """Width-aware logo: full art when it fits, plain text otherwise.

    Because this is a lazy renderable, it re-picks the right variant every
    time it is rendered (including when the transcript is replayed after a
    terminal resize).
    """

    def __rich_console__(self, console, options):
        if options.max_width >= LOGO_MIN_WIDTH:
            yield banner_logo()
        else:
            yield Align.center(Text("KARAN", style=f"bold {GRADIENT[2]}"))


class UI:
    def __init__(self):
        self.console = Console()
        self._totals = {}
        self._history = []              # renderables, replayable at any width
        self._size = self.console.size  # size the transcript was last drawn at
        self._pending = ""              # text typed when a resize interrupted the prompt

    # ------------------------------------------------- outer frame (manual)

    def _top(self):
        width = max(self.console.width - 2, 0)
        self.console.print(
            Text("╭" + "─" * width + "╮", style=BORDER)
        )

    def _bottom(self):
        width = max(self.console.width - 2, 0)
        self.console.print(
            Text("╰" + "─" * width + "╯", style=BORDER)
        )

    def _emit(self, renderable, record=True):
        """Print a renderable inside the outer frame (│ … │ on every line).

        Renderables are recorded so the transcript can be replayed at a new
        width after the terminal is resized.
        """
        if record:
            self._history.append(renderable)
        self._size = self.console.size

        inner = max(self.console.width - 4, 20)
        options = self.console.options.update_width(inner)
        edge = RichStyle(color=BORDER)
        left, right = Segment("│ ", edge), Segment(" │", edge)

        for line in self.console.render_lines(renderable, options, pad=True):
            self.console.print(Segments([left, *line, right]))

    def _redraw(self):
        """Clear screen + scrollback, then replay the transcript at the new width."""
        self.console.file.write("\x1b[2J\x1b[3J\x1b[H")
        self.console.file.flush()
        self._size = self.console.size
        self._top()
        for r in self._history:
            self._emit(r, record=False)

    def banner(self):
        """Clear the screen and draw the top of the frame with the welcome text."""
        self.console.clear()
        self._history.clear()
        self.console.file.write("\x1b[2J\x1b[3J\x1b[H")
        self.console.file.flush()
        self._history.clear()

        self._top()
        self._emit(
            Padding(
                Group(
                    Logo(),
                    Text(""),
                    Text("Your AI-powered terminal assistant", style=f"{GRADIENT[2]}", justify="center"),
                    Text(""),
                    Text(""),
                ),
                (1, 0),
            )
        )

    # --------------------------------------------------------------- input

    def _hint(self):
        return Window(
            FormattedTextControl(
                lambda: [(
                    "class:hint",
                    HINT if self.console.width >= HINT_MIN_WIDTH else HINT_SHORT,
                )]
            ),
            height=1,
            align=WindowAlign.CENTER,
        )

    def _menu_window(self, area):
        """Slash-command list drawn above the input box (keeps a 3-row gap when closed)."""
        GAP = 3

        def state():
            return area.buffer.complete_state

        def rows():
            s = state()
            return min(len(s.completions), MENU_ROWS) if s else 0

        def render():
            s = state()
            if not s:
                return []
            comps = s.completions
            idx = s.complete_index                      # None until you press up/down
            start = max(idx - MENU_ROWS + 1, 0) if idx is not None else 0
            visible = comps[start:start + MENU_ROWS]
            name_w = max(len(c.text) for c in comps) + 2

            frags = [("", "\n")] * max(GAP - len(visible), 0)   # keep menu hugging the box
            for i, c in enumerate(visible, start):
                cur = i == idx
                frags.append(("class:menu.current" if cur else "class:menu.name",
                              f" {c.text:<{name_w}}"))
                frags.append(("class:menu.current.meta" if cur else "class:menu.meta",
                              f"{c.display_meta_text} "))
                if i != start + len(visible) - 1:
                    frags.append(("", "\n"))
            return frags

        return Window(
            FormattedTextControl(render),
            height=lambda: Dimension.exact(max(rows(), GAP)),
        )

    def _prompt_layout(self, area):
        bar = lambda: Window(width=1, char="│", style="class:outer")
        gap = lambda: Window(width=1)

        middle = HSplit([
            Window(height=1),
            self._menu_window(area),          # menu lives above the input box
            Frame(area, style="class:input"),
            Window(height=1),
            self._hint(),
        ])

        bottom = VSplit(
            [
                Window(width=1, char="╰", style="class:outer"),
                Window(char="─", style="class:outer"),
                Window(width=1, char="╯", style="class:outer"),
            ],
            height=1,
        )

        return HSplit([VSplit([bar(), gap(), middle, gap(), bar()]), bottom])

    def ask(self, completer=None):
        """Prompt inside the outer frame. Returns None on ctrl-d / ctrl-c.

        If the terminal is resized (before or during the prompt), the
        transcript is redrawn at the new width and the prompt is restarted
        with whatever the user had already typed.
        """
        initial = ""
        while True:
            if self.console.size != self._size:      # resized while the agent was busy
                self._redraw()
            result = self._ask_once(completer, initial)
            if result is _RESIZED:
                initial = self._pending
                self._redraw()
                continue
            break

        if result is None:
            return None
        text = result.strip()

        if text:
            self._emit(
                Panel(
                    Text.assemble(("❯ ", f"bold {USER}"), (text, "#c0caf5")),
                    border_style=ACCENT,
                    box=box.ROUNDED,
                    padding=(0, 1),
                    expand=True,
                )
            )
        return text

    def _ask_once(self, completer=None, initial=""):
        no_arg = getattr(completer, "no_arg", set())

        def input_height():
            width = max(self.console.width - 8, 10)
            text = area.text or ""
            rows = sum(
                max(1, -(-len(line) // width))
                for line in text.split("\n")
            )
            return Dimension.exact(min(max(rows, 1), MAX_INPUT_LINES))

        area = TextArea(
            text=initial,
            prompt=[("class:prompt", "❯ ")],
            multiline=True,
            wrap_lines=True,
            height=input_height,
            completer=completer,
            complete_while_typing=True,   # menu opens as soon as "/" is typed
        )
        area.buffer.cursor_position = len(initial)

        kb = KeyBindings()

        @kb.add("enter")
        def _submit(event):
            buf = event.current_buffer
            state = buf.complete_state
            if state and state.completions:
                comp = state.current_completion or state.completions[0]
                typed = buf.text.strip()
                buf.apply_completion(comp)
                if typed == comp.text or comp.text in no_arg:
                    event.app.exit(result=buf.text)   # /exit, /help, exact match
                else:
                    buf.insert_text(" ")              # skill: wait for arguments
                return
            event.app.exit(result=buf.text)

        @kb.add("escape", "enter")
        @kb.add("c-j")
        def _newline(event):
            event.current_buffer.insert_text("\n")

        @kb.add("c-d")
        @kb.add("c-c")
        def _exit(event):
            event.app.exit(result=None)

        app = Application(
            layout=Layout(self._prompt_layout(area), focused_element=area),
            key_bindings=kb,
            style=INPUT_STYLE,
            full_screen=False,
            erase_when_done=True,
        )

        def _check_resize(app):
            if self.console.size != self._size and not app.is_done:
                self._size = self.console.size      # guard against exiting twice
                self._pending = area.text
                app.exit(result=_RESIZED)

        app.before_render += _check_resize
        return app.run()

    # -------------------------------------------------------------- output

    def user(self, text):
        """No-op: ask() already echoes the question into the transcript."""
        return

    def agent(self, text):
        self._emit(
            Padding(
                Panel(
                    Markdown(text.strip()),
                    border_style=ACCENT,
                    box=box.ROUNDED,
                    padding=(1, 2),
                    expand=True,
                ),
                (1, 0, 0, 0),
            )
        )

    def help(self, commands):
        table = Table.grid(padding=(0, 3))
        table.add_column(style=f"bold {ACCENT}")
        table.add_column(style=MUTED)
        for name, desc in commands.items():
            table.add_row(name, desc)
        self._emit(Padding(table, (1, 0, 0, 0)))

    def notice(self, text, style=MUTED):
        self._emit(Padding(Text(text, style=style), (1, 0, 0, 0)))

    def tool(self, name, args, result):
        header = Text.assemble(
            (f" {name} ", f"bold {TOOL}"),
            (self._format_args(args), MUTED),
        )

        self._emit(
            Padding(
                Panel(
                    Group(
                        header,
                        Rule(style=BORDER),
                        self._format_result(result),
                    ),
                    title=Text(" TOOL EXECUTION ", style=f"bold {TOOL}"),
                    title_align="left",
                    border_style=TOOL,
                    box=box.ROUNDED,
                    padding=(1, 2),
                    expand=True,
                ),
                (1, 0, 0, 0),
            )
        )

    @contextmanager
    def working(self, label="Thinking..."):
        with self.console.status(
            Text(label, style=MUTED),
            spinner="dots",
            spinner_style=ACCENT,
        ):
            yield

    # --------------------------------------------------------------- usage

    def usage(self, stats):
        for key, value in stats.items():
            self._totals[key] = self._totals.get(key, 0) + (value or 0)

        parts = "  ·  ".join(
            f"{value:,} {key.replace('_tokens', '')}"
            for key, value in stats.items()
            if value
        )

        if parts:
            self._emit(Padding(Text(f"◈  {parts}", style=MUTED), (1, 0, 0, 0)))

    def summary(self):
        """Print session totals and close the outer frame. Call at exit."""
        if self._totals:
            table = Table.grid(padding=(0, 2))
            table.add_column(style=MUTED)
            table.add_column(style=f"bold {ACCENT}", justify="right")

            for key, value in self._totals.items():
                table.add_row(key.replace("_", " ").title(), f"{value:,}")

            self._emit(
                Padding(
                    Panel(
                        table,
                        title=Text(" SESSION USAGE ", style=f"bold {ACCENT}"),
                        border_style=BORDER,
                        box=box.ROUNDED,
                        padding=(1, 2),
                        expand=True,
                    ),
                    (1, 0, 1, 0),
                )
            )

        self._bottom()

    # ------------------------------------------------------------- helpers

    def _format_args(self, args):
        if len(args) == 1:
            return str(next(iter(args.values())))
        return json.dumps(args)

    def _format_result(self, result):
        lines = result.strip().splitlines() or ["(no output)"]
        shown = lines[:MAX_TOOL_OUTPUT_LINES]

        body = Text("\n".join(shown), style=MUTED)

        hidden = len(lines) - len(shown)
        if hidden > 0:
            body.append(f"\n… {hidden} more lines", style=f"italic {TOOL}")

        return body


ui = UI()

if __name__ == "__main__":
    import time

    ui.banner()

    try:
        while True:
            text = ui.ask()

            # Empty input means ctrl-c / ctrl-d (or just pressing enter on nothing)
            if not text:
                break

            if text.lower() in {"/exit", "/quit"}:
                break

            # Simulate the agent "thinking"
            with ui.working("Thinking..."):
                time.sleep(0.6)

            # Demo a tool call for a slash command: /tool <anything>
            if text.startswith("/tool"):
                ui.tool(
                    "echo",
                    {"text": text[5:].strip()},
                    "line 1\nline 2\n" + "\n".join(f"line {i}" for i in range(3, 20)),
                )

            # Echo the user's text back as the agent response
            ui.agent(f"You said:\n\n> {text}")

            # Fake token usage
            ui.usage({
                "input_tokens": len(text.split()),
                "output_tokens": len(text.split()) + 3,
            })
    finally:
        ui.summary()