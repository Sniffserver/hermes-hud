"""Tribe HUD — Gradient ANSI Boot Screen with hõimkonna identity."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static
from textual.timer import Timer

TRIBE_LOGO = """
  ████████╗██████╗ ██╗██████╗ ███████╗
  ╚══██╔══╝██╔══██╗██║██╔══██╗██╔════╝
     ██║   ██████╔╝██║██████╔╝█████╗  
     ██║   ██╔══██╗██║██╔══██╗██╔══╝  
     ██║   ██║  ██║██║██████╔╝███████╗
     ╚═╝   ╚═╝  ╚═╝╚═╝╚═════╝ ╚══════╝

  ██╗  ██╗██╗   ██╗██████╗ 
  ██║  ██║██║   ██║██╔══██╗
  ███████║██║   ██║██║  ██║
  ██╔══██║██║   ██║██║  ██║
  ██║  ██║╚██████╔╝██████╔╝
  ╚═╝  ╚═╝ ╚═════╝ ╚═════╝ 
"""

SUBTITLE_LINES = [
    "[bold cyan]◆ Teadmised · Vastupidavus · Innovatsioon ◆[/bold cyan]",
    "[dim]~/.hermes/ connected — reading agent state...[/dim]",
    "[bold green]● Systems online[/bold green]   [bold yellow]◐ Memory indexed[/bold yellow]   [bold magenta]⬡ Skills loaded[/bold magenta]",
]

GRADIENT_FRAMES = [
    "[bold blue]",
    "[bold cyan]",
    "[bold green]",
    "[bold magenta]",
    "[bold cyan]",
]


class BootScreen(Screen):
    """Animated tribe boot screen — shown once on startup."""

    DEFAULT_CSS = """
    BootScreen {
        background: $background;
        align: center middle;
    }
    #logo {
        text-align: center;
        padding: 1 4;
    }
    #subtitle {
        text-align: center;
        padding: 0 2;
    }
    #status {
        text-align: center;
        padding: 1 2;
        color: $success;
    }
    #version {
        text-align: center;
        color: $text-muted;
        padding: 0 2;
    }
    """

    _frame: int = 0
    _timer: Timer | None = None

    def compose(self) -> ComposeResult:
        yield Static(id="logo")
        yield Static(id="subtitle")
        yield Static(id="status")
        yield Static("[dim]TRIBE HUD v1.0.0 — 500 Aasta Plaan[/dim]", id="version")

    def on_mount(self) -> None:
        self._render_frame()
        self._timer = self.set_interval(0.15, self._animate)
        # Auto-dismiss after 3.5 seconds
        self.set_timer(3.5, self._finish)

    def _render_frame(self) -> None:
        color = GRADIENT_FRAMES[self._frame % len(GRADIENT_FRAMES)]
        logo_widget = self.query_one("#logo", Static)
        logo_widget.update(f"{color}{TRIBE_LOGO}[/]")

        subtitle_widget = self.query_one("#subtitle", Static)
        subtitle_widget.update("\n".join(SUBTITLE_LINES))

        status_widget = self.query_one("#status", Static)
        dots = "." * ((self._frame % 3) + 1)
        status_widget.update(f"[bold green]Initializing{dots}[/bold green]")

    def _animate(self) -> None:
        self._frame += 1
        self._render_frame()

    def _finish(self) -> None:
        if self._timer:
            self._timer.stop()
        self.app.pop_screen()
