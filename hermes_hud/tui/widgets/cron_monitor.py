"""Cron Monitor Widget — scheduled jobs and their execution history."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable, Static

HERMES_JOBS_DIR = Path(os.path.expanduser("~/.hermes/jobs"))
SYSTEM_CRON_LOG = Path("/var/log/cron")
SYSLOG_CRON_LOG = Path("/var/log/syslog")  # fallback on Debian/Ubuntu


@dataclass
class CronJob:
    name: str
    schedule: str
    last_run: Optional[str] = None
    last_status: str = "unknown"
    run_count: int = 0
    last_output: str = ""
    source: str = "hermes"  # "hermes" | "system"


def _load_hermes_jobs() -> list[CronJob]:
    """Load job history from ~/.hermes/jobs/*.json"""
    jobs: list[CronJob] = []
    if not HERMES_JOBS_DIR.exists():
        return jobs

    for jf in sorted(HERMES_JOBS_DIR.glob("*.json")):
        try:
            data = json.loads(jf.read_text())
            jobs.append(CronJob(
                name=data.get("name", jf.stem),
                schedule=data.get("schedule", "?"),
                last_run=data.get("last_run"),
                last_status=data.get("last_status", "unknown"),
                run_count=data.get("run_count", 0),
                last_output=data.get("last_output", "")[:120],
                source="hermes",
            ))
        except (json.JSONDecodeError, OSError):
            continue
    return jobs


def _parse_system_cron() -> list[CronJob]:
    """Read user crontab and parse entries."""
    jobs: list[CronJob] = []
    try:
        result = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True, timeout=3
        )
        if result.returncode != 0:
            return jobs
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 5)
            if len(parts) >= 6:
                schedule = " ".join(parts[:5])
                command = parts[5][:60]
                jobs.append(CronJob(
                    name=command,
                    schedule=schedule,
                    last_status="scheduled",
                    source="system",
                ))
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return jobs


def _read_cron_log(max_lines: int = 200) -> list[str]:
    """Read last N lines from system cron log."""
    for log_path in [SYSTEM_CRON_LOG, SYSLOG_CRON_LOG]:
        if log_path.exists():
            try:
                result = subprocess.run(
                    ["tail", "-n", str(max_lines), str(log_path)],
                    capture_output=True, text=True, timeout=3
                )
                if result.returncode == 0:
                    return [l for l in result.stdout.splitlines() if "CRON" in l or "cron" in l]
            except (subprocess.TimeoutExpired, PermissionError):
                pass
    return []


def _status_markup(status: str) -> str:
    colors = {
        "success": "[bold green]✓ success[/bold green]",
        "ok": "[bold green]✓ ok[/bold green]",
        "failed": "[bold red]✗ failed[/bold red]",
        "error": "[bold red]✗ error[/bold red]",
        "running": "[bold yellow]⟳ running[/bold yellow]",
        "scheduled": "[dim]◷ scheduled[/dim]",
        "unknown": "[dim]? unknown[/dim]",
    }
    return colors.get(status.lower(), f"[dim]{status}[/dim]")


class CronMonitorWidget(Widget):
    """Cron Monitor — shows scheduled jobs from ~/.hermes/jobs/ and crontab."""

    DEFAULT_CSS = """
    CronMonitorWidget {
        height: auto;
        border: round $warning;
        padding: 0 1;
        margin: 0 1;
    }
    #cron-title {
        text-align: center;
        color: $warning;
        text-style: bold;
        padding: 0 0 1 0;
    }
    #cron-log-title {
        color: $text-muted;
        text-style: italic;
        padding: 1 0 0 0;
    }
    #cron-log {
        color: $text-muted;
        height: 5;
        overflow-y: scroll;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("⏱  CRON MONITOR — Jobs & History", id="cron-title")
        yield DataTable(id="cron-table")
        yield Static("Recent system cron log:", id="cron-log-title")
        yield Static(id="cron-log")

    def on_mount(self) -> None:
        table = self.query_one("#cron-table", DataTable)
        table.add_columns("Source", "Job / Command", "Schedule", "Last Run", "Status", "Runs")
        table.zebra_stripes = True
        table.cursor_type = "row"
        self.refresh_data()

    def refresh_data(self) -> None:
        table = self.query_one("#cron-table", DataTable)
        table.clear()

        all_jobs = _load_hermes_jobs() + _parse_system_cron()

        if not all_jobs:
            table.add_row("—", "No jobs found", "—", "—", "—", "—")
        else:
            for job in all_jobs:
                source_tag = (
                    "[bold cyan]⬡ hermes[/bold cyan]"
                    if job.source == "hermes"
                    else "[dim]⚙ system[/dim]"
                )
                last_run = job.last_run or "never"
                # Truncate long ISO timestamps
                if "T" in last_run:
                    last_run = last_run[:16].replace("T", " ")
                table.add_row(
                    source_tag,
                    job.name[:45],
                    job.schedule,
                    last_run,
                    _status_markup(job.last_status),
                    str(job.run_count),
                )

        # System cron log tail
        log_widget = self.query_one("#cron-log", Static)
        log_lines = _read_cron_log(50)
        if log_lines:
            log_widget.update("\n".join(log_lines[-8:]))
        else:
            log_widget.update("[dim]No cron log accessible (try: sudo chmod 644 /var/log/cron)[/dim]")
