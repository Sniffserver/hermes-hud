"""Dashboard screen for Tribe HUD — unified operator view.

Combines all widgets into a single tmux-style layout:
- Top: Health Check (services status)
- Middle: Growth Tracker (snapshot diffs) + Cron Monitor (jobs)
- Bottom: Project Tracker (git repos) + Corrections Log (learnings)
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
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
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("d", "toggle_dark", "Dark mode"),
        ("1", "focus_health", "Health"),
        ("2", "focus_growth", "Growth"),
        ("3", "focus_cron", "Cron"),
        ("4", "focus_projects", "Projects"),
        ("5", "focus_corrections", "Corrections"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()

        with Container(id="dashboard"):
            # Row 1: Health Check (full width)
            yield HealthCheckWidget(id="health-panel")

            with Horizontal(id="row-2"):
                # Row 2: Growth Tracker + Cron Monitor
                yield GrowthTrackerWidget(id="growth-panel")
                yield CronMonitorWidget(id="cron-panel")

            with Horizontal(id="row-3"):
                # Row 3: Project Tracker + Corrections Log
                yield ProjectTrackerWidget(id="projects-panel")
                yield CorrectionsLogWidget(id="corrections-panel")

    def action_refresh(self) -> None:
        """Refresh all widgets."""
        for widget in self.query(HealthCheckWidget, GrowthTrackerWidget,
                                   CronMonitorWidget, ProjectTrackerWidget,
                                   CorrectionsLogWidget):
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
