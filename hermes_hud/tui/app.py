"""Tribe HUD — Main Textual TUI Application with Gruvbox theme."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, TabbedContent, TabPane

from .screens.boot import BootScreen
from .screens.dashboard import DashboardScreen
from .widgets.cron_monitor import CronMonitorWidget
from .widgets.growth_tracker import GrowthTrackerWidget
from .widgets.project_tracker import ProjectTrackerWidget
from .widgets.health_check import HealthCheckWidget
from .widgets.corrections_log import CorrectionsLogWidget


class TribeHUDApp(App):
    """Tribe HUD — 500 Aasta Plaani Agent Dashboard."""

    TITLE = "TRIBE HUD"
    SUB_TITLE = "Teadmised · Vastupidavus · Innovatsioon"

    # Gruvbox dark theme CSS
    CSS = """
    Screen {
        background: #1d2021;
        color: #ebdbb2;
    }

    Header {
        background: #1d2021;
        color: #fe8019;
        text-style: bold;
        height: 3;
        dock: top;
    }

    Footer {
        background: #1d2021;
        color: #928374;
        height: 1;
        dock: bottom;
    }

    TabbedContent {
        height: 1fr;
    }

    TabPane {
        padding: 1 2;
    }

    /* Widget panels */
    .widget-panel {
        height: auto;
        border: round #504945;
        padding: 1 2;
        margin: 0 1 1 1;
    }

    .widget-title {
        text-align: center;
        text-style: bold;
        color: #fe8019;
        padding: 0 0 1 0;
    }

    .widget-subtitle {
        text-align: center;
        color: #928374;
        padding: 0 0 1 0;
    }

    DataTable {
        height: auto;
        max-height: 12;
        border: none;
    }

    DataTable > .datatable--header {
        background: #282828;
        color: #83a598;
        text-style: bold;
    }

    DataTable > .datatable--row {
        color: #ebdbb2;
    }

    DataTable > .datatable--row-highlight {
        background: #3c3836;
    }

    /* Status colors */
    .status-ok { color: #b8bb26; }
    .status-warn { color: #fabd2f; }
    .status-error { color: #fb4934; }
    .status-info { color: #83a598; }

    /* Dashboard layout */
    #dashboard-grid {
        layout: grid;
        grid-size: 2 3;
        grid-gutter: 1 1;
        height: 1fr;
        padding: 0 1;
    }

    #dashboard-grid > * {
        height: auto;
        min-height: 8;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("b", "boot", "Boot Screen", show=False),
        Binding("d", "dark", "Dark mode"),
        Binding("1", "switch_tab('growth')", "Growth"),
        Binding("2", "switch_tab('cron')", "Cron"),
        Binding("3", "switch_tab('projects')", "Projects"),
        Binding("4", "switch_tab('health')", "Health"),
        Binding("5", "switch_tab('corrections')", "Corrections"),
        Binding("0", "switch_tab('dashboard')", "Dashboard"),
    ]

    def on_mount(self) -> None:
        """Show boot screen on startup."""
        self.push_screen(BootScreen())

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(initial="dashboard"):
            with TabPane("📊 Dashboard", id="dashboard"):
                yield DashboardScreen()
            with TabPane("📈 Growth", id="growth"):
                yield GrowthTrackerWidget()
            with TabPane("⏱ Cron", id="cron"):
                yield CronMonitorWidget()
            with TabPane("📂 Projects", id="projects"):
                yield ProjectTrackerWidget()
            with TabPane("🏥 Health", id="health"):
                yield HealthCheckWidget()
            with TabPane("📝 Corrections", id="corrections"):
                yield CorrectionsLogWidget()
        yield Footer()

    def action_refresh(self) -> None:
        for WidgetCls in (HealthCheckWidget, GrowthTrackerWidget,
                          CronMonitorWidget, ProjectTrackerWidget,
                          CorrectionsLogWidget):
            for widget in self.query(WidgetCls):
                if hasattr(widget, "refresh_data"):
                    widget.refresh_data()

    def action_boot(self) -> None:
        self.push_screen(BootScreen())

    def action_switch_tab(self, tab_id: str) -> None:
        self.query_one(TabbedContent).active = tab_id


def main():
    app = TribeHUDApp()
    app.run()


if __name__ == "__main__":
    main()
