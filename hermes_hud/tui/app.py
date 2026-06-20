"""Tribe HUD — Main Textual TUI Application."""

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
    CSS_PATH = None

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("b", "boot", "Boot Screen", show=False),
        Binding("1", "switch_tab('growth')", "Growth"),
        Binding("2", "switch_tab('cron')", "Cron"),
        Binding("3", "switch_tab('projects')", "Projects"),
        Binding("4", "switch_tab('health')", "Health"),
        Binding("5", "switch_tab('corrections')", "Corrections"),
        Binding("0", "switch_tab('dashboard')", "Dashboard"),
        Binding("d", "dark", "Dark mode"),
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
