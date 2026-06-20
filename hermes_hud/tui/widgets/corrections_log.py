"""Corrections Log widget for Tribe HUD — mistake history and learnings."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from textual.widgets import Static


# ── Data Model ────────────────────────────────────────────────────────────

@dataclass
class Correction:
    id: str
    timestamp: str
    category: str
    summary: str
    resolution: str
    source: str = ""


# ── Load Corrections ──────────────────────────────────────────────────────

CORRECTIONS_DIR = Path(os.path.expanduser("~/.hermes/corrections"))


def load_corrections() -> list[Correction]:
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


# ── Textual Widget ────────────────────────────────────────────────────────

class CorrectionsLogWidget(Static):
    """Corrections Log — mistake history and learnings."""

    def on_mount(self) -> None:
        self.refresh_data()

    def refresh_data(self) -> None:
        corrections = load_corrections()

        lines = [
            "📝 CORRECTIONS LOG",
            "─" * 50,
        ]

        if not corrections:
            lines.append("  No corrections recorded yet.")
        else:
            lines.append(f"  Total: {len(corrections)} corrections")
            lines.append("─" * 50)
            for c in corrections[:15]:
                ts = c.timestamp[:16].replace("T", " ") if c.timestamp else "?"
                cat_icon = {"tool": "🔧", "command": "⌨️", "config": "⚙️", "security": "🔒"}.get(c.category, "📝")
                lines.append(f"  {ts} {cat_icon} [{c.category}]")
                lines.append(f"    What: {c.summary}")
                lines.append(f"    Fix:  {c.resolution}")
                lines.append("")

        self.update("\n".join(lines))
