"""Dashboard screen for Tribe HUD — unified operator view."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, Grid
from textual.screen import Screen
from textual.widgets import Header, Footer, Static

from hermes_hud.tui.widgets.growth_tracker import GrowthTrackerWidget
from hermes_hud.tui.widgets.cron_monitor import CronMonitorWidget
from hermes_hud.tui.widgets.project_tracker import ProjectTrackerWidget
from hermes_hud.tui.widgets.health_check import HealthCheckWidget
from hermes_hud.tui.widgets.corrections_log import CorrectionsLogWidget


class DashboardScreen(Screen):
    """Main dashboard — all widgets in one view."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("d", "toggle_dark", "Dark mode"),
        Binding("1", "focus_health", "Health"),
        Binding("2", "focus_growth", "Growth"),
        Binding("3", "focus_cron", "Cron"),
        Binding("4", "focus_projects", "Projects"),
        Binding("5", "focus_corrections", "Corrections"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()

        with Container(id="dashboard-grid"):
            yield HealthCheckWidget(id="health-panel")
            yield GrowthTrackerWidget(id="growth-panel")
            yield CronMonitorWidget(id="cron-panel")
            yield ProjectTrackerWidget(id="projects-panel")
            yield CorrectionsLogWidget(id="corrections-panel")

    def action_refresh(self) -> None:
        """Refresh all widgets."""
        for WidgetCls in (HealthCheckWidget, GrowthTrackerWidget,
                          CronMonitorWidget, ProjectTrackerWidget,
                          CorrectionsLogWidget):
            for widget in self.query(WidgetCls):
                if hasattr(widget, "refresh_data"):
                    widget.refresh_data()

    def action_focus_health(self) -> None:
        self.query_one("#health-panel", HealthCheckWidget).focus()

    def action_focus_growth(self) -> None:
        self.query_one("#growth-panel", GrowthTrackerWidget).focus()

    def action_focus_cron(self) -> None:
        self.query_one("#cron-panel", CronMonitorWidget).focus()

    def action_focus_projects(self) -> None:
        self.query_one("#projects-panel", ProjectTrackerWidget).focus()

    def action_focus_corrections(self) -> None:
        self.query_one("#corrections-panel", CorrectionsLogWidget).focus()
