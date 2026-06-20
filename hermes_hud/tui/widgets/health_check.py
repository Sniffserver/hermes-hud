"""Health Check widget for Tribe HUD — API keys, services, ESP32, gateway.

Security: shows status only, never exposes key values or secrets.
"""

from __future__ import annotations

import os
import subprocess
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable, Static


# ── Data Model ────────────────────────────────────────────────────────────

@dataclass
class HealthCheck:
    name: str
    status: str  # "ok" | "warn" | "error" | "unknown"
    detail: str = ""
    category: str = "service"  # "api" | "service" | "device" | "gateway"


# ── Check Functions ────────────────────────────────────────────────────────

def _check_port(port: int, host: str = "127.0.0.1", timeout: float = 2.0) -> bool:
    """Check if a TCP port is open."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def _check_http(url: str, timeout: float = 3.0) -> bool:
    """Check if an HTTP endpoint responds."""
    try:
        import urllib.request
        req = urllib.request.Request(url, method="HEAD")
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.status < 500
    except Exception:
        return False


def _run_cmd(cmd: list[str], timeout: int = 5) -> tuple[int, str]:
    """Run a command, return (returncode, stdout)."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout.strip()
    except Exception:
        return 1, ""


def _check_api_key(name: str, env_var: str) -> HealthCheck:
    """Check if an API key is configured — status only, never the value."""
    value = os.environ.get(env_var, "")
    if value:
        # Show only first 4 chars + length indicator, never the full key
        masked = value[:4] + "..." + f"({len(value)} chars)"
        return HealthCheck(name=name, status="ok", detail=masked, category="api")
    return HealthCheck(name=name, status="warn", detail="Not set", category="api")


def _check_service(name: str, port: int, url: str | None = None) -> HealthCheck:
    """Check if a service is responding."""
    if url:
        if _check_http(url):
            return HealthCheck(name=name, status="ok", detail=f"HTTP OK", category="service")
    if _check_port(port):
        return HealthCheck(name=name, status="ok", detail=f"Port {port} open", category="service")
    return HealthCheck(name=name, status="error", detail=f"Port {port} closed", category="service")


def _check_esp32() -> HealthCheck:
    """Check if ESP32 is connected via USB."""
    rc, out = _run_cmd(["ls", "/dev/ttyUSB0", "/dev/ttyACM0"], timeout=3)
    if rc == 0 and out:
        devices = [d for d in out.split("\n") if d.strip()]
        return HealthCheck(name="ESP32", status="ok", detail=f"Connected: {', '.join(devices)}", category="device")
    return HealthCheck(name="ESP32", status="warn", detail="Not connected", category="device")


def _check_gateway() -> HealthCheck:
    """Check if Hermes gateway is running."""
    rc, out = _run_cmd(["pgrep", "-f", "hermes"], timeout=3)
    if rc == 0 and out:
        return HealthCheck(name="Hermes Gateway", status="ok", detail=f"PID: {out.split()[0]}", category="gateway")
    return HealthCheck(name="Hermes Gateway", status="error", detail="Not running", category="gateway")


def _check_ollama() -> HealthCheck:
    """Check Ollama status and loaded models."""
    rc, out = _run_cmd(["curl", "-sf", "http://127.0.0.1:11434/api/tags"], timeout=5)
    if rc == 0:
        try:
            import json
            data = json.loads(out)
            models = data.get("models", [])
            return HealthCheck(name="Ollama", status="ok", detail=f"{len(models)} models loaded", category="service")
        except Exception:
            return HealthCheck(name="Ollama", status="ok", detail="Running", category="service")
    return HealthCheck(name="Ollama", status="error", detail="Not responding", category="service")


def _check_docker() -> HealthCheck:
    """Check Docker daemon and running containers."""
    rc, out = _run_cmd(["docker", "ps", "--format", "{{.Names}}"], timeout=5)
    if rc == 0:
        containers = [c for c in out.split("\n") if c.strip()]
        return HealthCheck(name="Docker", status="ok", detail=f"{len(containers)} containers running", category="service")
    return HealthCheck(name="Docker", status="error", detail="Daemon not responding", category="service")


def run_all_checks() -> list[HealthCheck]:
    """Run all health checks."""
    checks: list[HealthCheck] = []

    # API Keys (status only, never values)
    checks.append(_check_api_key("OpenRouter", "OPENROUTER_API_KEY"))
    checks.append(_check_api_key("Telegram", "TELEGRAM_BOT_TOKEN"))
    checks.append(_check_api_key("Langfuse", "LANGFUSE_SECRET_KEY"))
    checks.append(_check_api_key("Perplexity", "PERPLEXITY_API_KEY"))

    # Core services
    checks.append(_check_service("Ollama", 11434, "http://127.0.0.1:11434/api/tags"))
    checks.append(_check_service("Qdrant", 6333))
    checks.append(_check_service("Langfuse", 3000, "http://127.0.0.1:3000"))
    checks.append(_check_service("Uptime Kuma", 3001))
    checks.append(_check_service("Forgejo", 3100))
    checks.append(_check_service("Vaultwarden", 8200))
    checks.append(_check_service("Portainer", 9000))
    checks.append(_check_service("Syncthing", 8384))

    # Devices
    checks.append(_check_esp32())

    # Gateway
    checks.append(_check_gateway())

    # Docker
    checks.append(_check_docker())

    return checks


# ── Status Markup ──────────────────────────────────────────────────────────

def _status_markup(status: str) -> str:
    icons = {
        "ok": "[bold green]✓[/bold green]",
        "warn": "[bold yellow]⚠[/bold yellow]",
        "error": "[bold red]✗[/bold red]",
        "unknown": "[dim]?[/dim]",
    }
    return icons.get(status, "[dim]?[/dim]")


def _category_icon(category: str) -> str:
    icons = {
        "api": "🔑",
        "service": "⚙️",
        "device": "🔌",
        "gateway": "🦶",
    }
    return icons.get(category, "•")


# ── Textual Widget ────────────────────────────────────────────────────────

class HealthCheckWidget(Widget):
    """Health Check — API keys, services, devices, gateway."""

    DEFAULT_CSS = """
    HealthCheckWidget {
        height: auto;
        border: round $success;
        padding: 0 1;
        margin: 0 1;
    }
    #health-title {
        text-align: center;
        color: $success;
        text-style: bold;
        padding: 0 0 1 0;
    }
    #health-summary {
        color: $text-muted;
        padding: 0 0 1 0;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("🏥 HEALTH CHECK — Systems & Services", id="health-title")
        yield Static(id="health-summary")
        yield DataTable(id="health-table")

    def on_mount(self) -> None:
        table = self.query_one("#health-table", DataTable)
        table.add_columns("Category", "Name", "Status", "Detail")
        table.zebra_stripes = True
        table.cursor_type = "row"
        self.refresh_data()

    def refresh_data(self) -> None:
        table = self.query_one("#health-table", DataTable)
        table.clear()

        checks = run_all_checks()

        ok_count = sum(1 for c in checks if c.status == "ok")
        warn_count = sum(1 for c in checks if c.status == "warn")
        error_count = sum(1 for c in checks if c.status == "error")

        # Summary
        summary = self.query_one("#health-summary", Static)
        summary.update(
            f"✓ {ok_count} OK  |  ⚠ {warn_count} Warning  |  ✗ {error_count} Error  |  Total: {len(checks)}"
        )

        # Table
        for check in checks:
            cat_icon = _category_icon(check.category)
            status = _status_markup(check.status)
            table.add_row(
                f"{cat_icon} {check.category}",
                check.name,
                status,
                check.detail[:50],
            )
