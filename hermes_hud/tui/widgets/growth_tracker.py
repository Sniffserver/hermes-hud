"""Growth Tracker Widget — snapshot diffs show what changed since yesterday."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import DataTable, Label, Static

from ...snapshot import diff_report, load_snapshots


DELTA_FIELDS = [
    ("sessions", "Sessions"),
    ("messages", "Messages"),
    ("tool_calls", "Tool Calls"),
    ("skills", "Skills"),
    ("custom_skills", "Custom Skills"),
    ("memory_entries", "Memory Entries"),
    ("user_entries", "User Entries"),
    ("tokens", "Tokens"),
]


def _arrow_and_color(delta: int) -> tuple[str, str]:
    if delta > 0:
        return f"↑ +{delta}", "bold green"
    elif delta < 0:
        return f"↓ {delta}", "bold red"
    return "→ 0", "dim"


class GrowthTrackerWidget(Widget):
    """Live snapshot diff widget — compares latest vs previous snapshot."""

    DEFAULT_CSS = """
    GrowthTrackerWidget {
        height: auto;
        border: round $accent;
        padding: 0 1;
        margin: 0 1;
    }
    #growth-title {
        text-align: center;
        color: $accent;
        text-style: bold;
        padding: 0 0 1 0;
    }
    #no-data {
        text-align: center;
        color: $text-muted;
        padding: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("📈  GROWTH TRACKER — Since Yesterday", id="growth-title")
        yield DataTable(id="growth-table")

    def on_mount(self) -> None:
        table = self.query_one("#growth-table", DataTable)
        table.add_columns("Metric", "Yesterday", "Today", "Delta")
        table.zebra_stripes = True
        table.cursor_type = "row"
        self.refresh_data()

    def refresh_data(self) -> None:
        table = self.query_one("#growth-table", DataTable)
        table.clear()

        snapshots = load_snapshots()
        if len(snapshots) < 2:
            table.add_row("—", "—", "—", "No history yet — run: hermes-hud snapshot")
            return

        previous = snapshots[-2]
        current = snapshots[-1]

        for key, label in DELTA_FIELDS:
            prev_val = previous.get(key, 0)
            cur_val = current.get(key, 0)
            delta = cur_val - prev_val
            arrow, color = _arrow_and_color(delta)
            table.add_row(
                label,
                str(prev_val),
                str(cur_val),
                f"[{color}]{arrow}[/{color}]",
            )

        # New skill categories
        cur_cats = set(current.get("categories", []))
        prev_cats = set(previous.get("categories", []))
        new_cats = cur_cats - prev_cats
        if new_cats:
            table.add_row(
                "New Categories",
                "—",
                ", ".join(sorted(new_cats)),
                "[bold magenta]★ NEW[/bold magenta]",
            )

    def get_diff_text(self) -> str:
        """Return plain text diff for embedding in other views."""
        snapshots = load_snapshots()
        if len(snapshots) < 2:
            return "No snapshots yet."
        return diff_report(snapshots[-1], snapshots[-2])
