"""Corrections Log widget for Tribe HUD — mistake history and learnings.

Reads ~/.hermes/corrections/*.json and displays:
- What was corrected
- When it was corrected
- Category of mistake
- Resolution

Security: shows metadata only, never exposes sensitive data from corrections.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable, Static


# ── Data Model ────────────────────────────────────────────────────────────

@dataclass
class Correction:
    id: str
    timestamp: str
    category: str  # "tool" | "command" | "config" | "security" | "other"
    summary: str  # Brief description, no sensitive details
    resolution: str  # What was done to fix
    source: str = ""  # Optional: which file/command triggered it


# ── Load Corrections ──────────────────────────────────────────────────────

CORRECTIONS_DIR = Path(os.path.expanduser("~/.hermes/corrections"))


def load_corrections() -> list[Correction]:
    """Load corrections from ~/.hermes/corrections/*.json."""
    corrections: list[Correction] = []

    if not CORRECTIONS_DIR.exists():
        return corrections

    for jf in sorted(CORRECTIONS_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(jf.read_text())
            corrections.append(Correction(
                id=data.get("id", jf.stem),
                timestamp=data.get("timestamp", ""),
                category=data.get("category", "other"),
                summary=data.get("summary", "")[:80],
                resolution=data.get("resolution", "")[:80],
                source=data.get("source", "")[:40],
            ))
        except (json.JSONDecodeError, OSError):
            continue

    return corrections


def get_corrections_summary(corrections: list[Correction]) -> dict:
    """Get summary statistics."""
    if not corrections:
        return {"total": 0, "categories": {}, "recent": 0}

    categories: dict[str, int] = {}
    recent = 0
    now = datetime.now()

    for c in corrections:
        categories[c.category] = categories.get(c.category, 0) + 1
        # Count corrections from last 7 days
        try:
            ts = datetime.fromisoformat(c.timestamp.replace("Z", "+00:00"))
            if (now - ts.replace(tzinfo=None)).days <= 7:
                recent += 1
        except Exception:
            pass

    return {
        "total": len(corrections),
        "categories": categories,
        "recent": recent,
    }


# ── Category Icons ────────────────────────────────────────────────────────

def _category_icon(category: str) -> str:
    icons = {
        "tool": "🔧",
        "command": "⌨️",
        "config": "⚙️",
        "security": "🔒",
        "other": "📝",
    }
    return icons.get(category, "•")


# ── Textual Widget ────────────────────────────────────────────────────────

class CorrectionsLogWidget(Widget):
    """Corrections Log — mistake history and learnings."""

    DEFAULT_CSS = """
    CorrectionsLogWidget {
        height: auto;
        border: round $warning;
        padding: 0 1;
        margin: 0 1;
    }
    #corrections-title {
        text-align: center;
        color: $warning;
        text-style: bold;
        padding: 0 0 1 0;
    }
    #corrections-summary {
        color: $text-muted;
        padding: 0 0 1 0;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("📝 CORRECTIONS LOG — Mistakes & Learnings", id="corrections-title")
        yield Static(id="corrections-summary")
        yield DataTable(id="corrections-table")

    def on_mount(self) -> None:
        table = self.query_one("#corrections-table", DataTable)
        table.add_columns("Date", "Category", "Summary", "Resolution")
        table.zebra_stripes = True
        table.cursor_type = "row"
        self.refresh_data()

    def refresh_data(self) -> None:
        table = self.query_one("#corrections-table", DataTable)
        table.clear()

        corrections = load_corrections()
        summary = get_corrections_summary(corrections)

        # Summary
        summary_widget = self.query_one("#corrections-summary", Static)
        cats = ", ".join(f"{_category_icon(cat)} {cat}: {cnt}" for cat, cnt in summary["categories"].items())
        summary_widget.update(
            f"Total: {summary['total']} | Last 7 days: {summary['recent']} | {cats or 'No corrections yet'}"
        )

        # Table
        if not corrections:
            table.add_row("—", "—", "No corrections recorded yet", "—")
            return

        for c in corrections[:50]:  # Show last 50
            ts = c.timestamp[:16].replace("T", " ") if c.timestamp else "?"
            cat = f"{_category_icon(c.category)} {c.category}"
            table.add_row(ts, cat, c.summary, c.resolution)
