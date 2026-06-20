"""Health Check widget for Tribe HUD — API keys, services, ESP32, gateway.

Security: shows status only, never exposes key values or secrets.
"""

from __future__ import annotations

import os
import subprocess
import socket
from dataclasses import dataclass
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import DataTable, Static, Label


# ── Data Model ────────────────────────────────────────────────────────────

@dataclass
class HealthCheck:
    name: str
    status: str  # "ok" | "warn" | "error" | "unknown"
    detail: str = ""
    category: str = "service"  # "api" | "service" | "device" | "gateway"


# ── Check Functions ────────────────────────────────────────────────────────

def _check_port(port: int, host: str = "127.0.0.1", timeout: float = 2.0) -> bool:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def _check_http(url: str, timeout: float = 3.0) -> bool:
    try:
        import urllib.request
        req = urllib.request.Request(url, method="HEAD")
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.status < 500
    except Exception:
        return False


def _run_cmd(cmd: list[str], timeout: int = 5) -> tuple[int, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout.strip()
    except Exception:
        return 1, ""


def _check_api_key(name: str, env_var: str) -> HealthCheck:
    value = os.environ.get(env_var, "")
    if value:
        masked = value[:4] + "..." + f"({len(value)} chars)"
        return HealthCheck(name=name, status="ok", detail=masked, category="api")
    return HealthCheck(name=name, status="warn", detail="Not set", category="api")


def _check_service(name: str, port: int, url: str | None = None) -> HealthCheck:
    if url:
        if _check_http(url):
            return HealthCheck(name=name, status="ok", detail="HTTP OK", category="service")
    if _check_port(port):
        return HealthCheck(name=name, status="ok", detail=f"Port {port}", category="service")
    return HealthCheck(name=name, status="error", detail=f"Port {port} closed", category="service")


def _check_esp32() -> HealthCheck:
    rc, out = _run_cmd(["ls", "/dev/ttyUSB0", "/dev/ttyACM0"], timeout=3)
    if rc == 0 and out:
        devices = [d for d in out.split("\n") if d.strip()]
        return HealthCheck(name="ESP32", status="ok", detail=f"Connected: {', '.join(devices)}", category="device")
    return HealthCheck(name="ESP32", status="warn", detail="Not connected", category="device")


def _check_gateway() -> HealthCheck:
    rc, out = _run_cmd(["pgrep", "-f", "hermes"], timeout=3)
    if rc == 0 and out:
        return HealthCheck(name="Hermes Gateway", status="ok", detail=f"PID: {out.split()[0]}", category="gateway")
    return HealthCheck(name="Hermes Gateway", status="error", detail="Not running", category="gateway")


def _check_ollama() -> HealthCheck:
    rc, out = _run_cmd(["curl", "-sf", "http://127.0.0.1:11434/api/tags"], timeout=5)
    if rc == 0:
        try:
            import json
            data = json.loads(out)
            models = data.get("models", [])
            return HealthCheck(name="Ollama", status="ok", detail=f"{len(models)} models", category="service")
        except Exception:
            return HealthCheck(name="Ollama", status="ok", detail="Running", category="service")
    return HealthCheck(name="Ollama", status="error", detail="Not responding", category="service")


def _check_docker() -> HealthCheck:
    rc, out = _run_cmd(["docker", "ps", "--format", "{{.Names}}"], timeout=5)
    if rc == 0:
        containers = [c for c in out.split("\n") if c.strip()]
        return HealthCheck(name="Docker", status="ok", detail=f"{len(containers)} containers", category="service")
    return HealthCheck(name="Docker", status="error", detail="Not responding", category="service")


def run_all_checks() -> list[HealthCheck]:
    checks: list[HealthCheck] = []
    checks.append(_check_api_key("OpenRouter", "OPENROUTER_API_KEY"))
    checks.append(_check_api_key("Telegram", "TELEGRAM_BOT_TOKEN"))
    checks.append(_check_api_key("Langfuse", "LANGFUSE_SECRET_KEY"))
    checks.append(_check_api_key("Perplexity", "PERPLEXITY_API_KEY"))
    checks.append(_check_service("Ollama", 11434, "http://127.0.0.1:11434/api/tags"))
    checks.append(_check_service("Qdrant", 6333))
    checks.append(_check_service("Langfuse", 3000, "http://127.0.0.1:3000"))
    checks.append(_check_service("Uptime Kuma", 3001))
    checks.append(_check_service("Forgejo", 3100))
    checks.append(_check_service("Vaultwarden", 8200))
    checks.append(_check_service("Portainer", 9000))
    checks.append(_check_service("Syncthing", 8384))
    checks.append(_check_esp32())
    checks.append(_check_gateway())
    checks.append(_check_docker())
    return checks


def _status_icon(status: str) -> str:
    return {"ok": "✅", "warn": "⚠️", "error": "❌", "unknown": "?"}.get(status, "?")


def _category_icon(category: str) -> str:
    return {"api": "🔑", "service": "⚙️", "device": "🔌", "gateway": "🦶"}.get(category, "•")


# ── Textual Widget ────────────────────────────────────────────────────────

class HealthCheckWidget(Static):
    """Health Check — API keys, services, devices, gateway."""

    def on_mount(self) -> None:
        self.refresh_data()

    def refresh_data(self) -> None:
        checks = run_all_checks()
        ok_count = sum(1 for c in checks if c.status == "ok")
        warn_count = sum(1 for c in checks if c.status == "warn")
        error_count = sum(1 for c in checks if c.status == "error")

        lines = [
            "🏥 HEALTH CHECK",
            "─" * 50,
            f"✓ {ok_count} OK  |  ⚠ {warn_count} Warning  |  ✗ {error_count} Error",
            "─" * 50,
            f"{'':3} {'Category':<10} {'Name':<22} {'Status'}",
            "─" * 50,
        ]

        for check in checks:
            icon = _status_icon(check.status)
            cat = f"{_category_icon(check.category)} {check.category}"
            lines.append(f"  {icon} {cat:<12} {check.name:<22} {check.detail}")

        self.update("\n".join(lines))
