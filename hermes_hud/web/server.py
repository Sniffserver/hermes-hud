"""Tribe HUD Web Server — FastAPI + WebSocket for live dashboard."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from hermes_hud.collect import collect_all
from hermes_hud.models import HUDState


def _to_json(obj: Any) -> Any:
    """Recursively convert dataclasses to dicts for JSON serialization."""
    if is_dataclass(obj):
        return {k: _to_json(v) for k, v in asdict(obj).items()}
    elif isinstance(obj, list):
        return [_to_json(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: _to_json(v) for k, v in obj.items()}
    elif isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    else:
        return str(obj)


# ── App ────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Tribe HUD",
    version="1.0.0",
    description="HõimkondOS Agent Dashboard — live system state",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── WebSocket Connections ─────────────────────────────────────────────────

_connections: list[WebSocket] = []


# ── REST Endpoints ─────────────────────────────────────────────────────────

@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "tribe-hud"}


@app.get("/api/state")
async def get_state() -> dict[str, Any]:
    """Get current HUD state as JSON."""
    try:
        state: HUDState = collect_all()
        return {"ok": True, "data": _to_json(state)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/snapshot")
async def take_snapshot() -> dict[str, Any]:
    """Take a snapshot and return it."""
    try:
        from hermes_hud.snapshot import save_snapshot
        snapshot = save_snapshot()
        return {"ok": True, "snapshot": _to_json(snapshot)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── WebSocket ──────────────────────────────────────────────────────────────

@app.websocket("/ws/hud")
async def hud_stream(ws: WebSocket) -> None:
    """Stream HUD state updates every 2 seconds."""
    await ws.accept()
    _connections.append(ws)
    try:
        while True:
            try:
                state: HUDState = collect_all()
                await ws.send_json({"ok": True, "data": _to_json(state)})
            except Exception as e:
                await ws.send_json({"ok": False, "error": str(e)})
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        if ws in _connections:
            _connections.remove(ws)


# ── Dashboard HTML ────────────────────────────────────────────────────────

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="et">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tribe HUD — Dashboard</title>
    <style>
        /* Gruvbox Dark Theme */
        :root {
            --bg: #1d2021;
            --bg-alt: #282828;
            --bg-border: #504945;
            --fg: #ebdbb2;
            --fg-dim: #928374;
            --accent: #fe8019;
            --accent-alt: #fabd2f;
            --green: #b8bb26;
            --red: #fb4934;
            --blue: #83a598;
            --purple: #d3869b;
            --cyan: #8ec07c;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: 'JetBrains Mono', 'Fira Code', monospace;
            background: var(--bg);
            color: var(--fg);
            padding: 1rem;
            line-height: 1.4;
        }

        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.5rem 0 1rem;
            border-bottom: 1px solid var(--bg-border);
            margin-bottom: 1rem;
        }

        .header h1 {
            color: var(--accent);
            font-size: 1.2rem;
        }

        .header .status {
            font-size: 0.7rem;
            padding: 0.2rem 0.5rem;
            border-radius: 3px;
        }

        .status.connected { background: var(--green); color: var(--bg); }
        .status.disconnected { background: var(--red); color: var(--bg); }

        .timestamp {
            color: var(--fg-dim);
            font-size: 0.7rem;
            margin-bottom: 1rem;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 1rem;
        }

        .panel {
            background: var(--bg-alt);
            border: 1px solid var(--bg-border);
            border-radius: 4px;
            padding: 1rem;
        }

        .panel h3 {
            color: var(--blue);
            margin-bottom: 0.5rem;
            font-size: 0.85rem;
        }

        .panel .summary {
            font-size: 0.75rem;
            color: var(--fg-dim);
            margin-bottom: 0.5rem;
        }

        .panel table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.75rem;
        }

        .panel th, .panel td {
            padding: 0.25rem 0.4rem;
            text-align: left;
            border-bottom: 1px solid var(--bg-border);
        }

        .panel th {
            color: var(--fg-dim);
            font-weight: normal;
        }

        .ok { color: var(--green); }
        .warn { color: var(--accent-alt); }
        .error { color: var(--red); }
        .dim { color: var(--fg-dim); }

        .refresh-btn {
            background: var(--bg-alt);
            border: 1px solid var(--bg-border);
            color: var(--fg);
            padding: 0.3rem 0.8rem;
            border-radius: 3px;
            cursor: pointer;
            font-family: inherit;
            font-size: 0.75rem;
        }

        .refresh-btn:hover {
            background: var(--bg-border);
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>⚒ TRIBE HUD</h1>
        <div>
            <span id="connection-status" class="status disconnected">● Disconnected</span>
            <button class="refresh-btn" onclick="location.reload()">↻ Refresh</button>
        </div>
    </div>

    <p class="timestamp" id="last-update">Waiting for data...</p>

    <div class="grid">
        <div class="panel" id="health-panel">
            <h3>🏥 Health</h3>
            <div class="summary" id="health-summary">Loading...</div>
            <table id="health-table">
                <thead><tr><th></th><th>Service</th><th>Status</th></tr></thead>
                <tbody></tbody>
            </table>
        </div>

        <div class="panel" id="growth-panel">
            <h3>📈 Growth</h3>
            <div class="summary" id="growth-summary">Loading...</div>
            <table id="growth-table">
                <thead><tr><th>Metric</th><th>Value</th></tr></thead>
                <tbody></tbody>
            </table>
        </div>

        <div class="panel" id="cron-panel">
            <h3>⏱ Cron</h3>
            <div class="summary" id="cron-summary">Loading...</div>
            <table id="cron-table">
                <thead><tr><th>Job</th><th>Schedule</th><th>Status</th></tr></thead>
                <tbody></tbody>
            </table>
        </div>

        <div class="panel" id="projects-panel">
            <h3>📂 Projects</h3>
            <div class="summary" id="projects-summary">Loading...</div>
            <table id="projects-table">
                <thead><tr><th>Repo</th><th>Branch</th><th>Status</th></tr></thead>
                <tbody></tbody>
            </table>
        </div>
    </div>

    <script>
        const ws = new WebSocket(`ws://${location.host}/ws/hud`);
        const statusEl = document.getElementById('connection-status');
        const updateEl = document.getElementById('last-update');

        ws.onopen = () => {
            statusEl.textContent = '● Connected';
            statusEl.className = 'status connected';
        };

        ws.onclose = () => {
            statusEl.textContent = '● Disconnected';
            statusEl.className = 'status disconnected';
        };

        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            if (!msg.ok) return;
            const d = msg.data;
            updateEl.textContent = 'Last update: ' + new Date().toLocaleTimeString();

            // Health
            if (d.config) {
                const model = d.config.model || 'unknown';
                document.getElementById('health-summary').innerHTML =
                    `Model: <span class="ok">${model}</span>`;
            }

            // Growth (from snapshot data)
            if (d.skills) {
                const total = d.skills.total || 0;
                const custom = d.skills.custom_count || 0;
                document.getElementById('growth-summary').innerHTML =
                    `Skills: <span class="ok">${total}</span> total, <span class="warn">${custom}</span> custom`;
            }

            // Sessions
            if (d.sessions) {
                const total = d.sessions.total_sessions || 0;
                const msgs = d.sessions.total_messages || 0;
                document.getElementById('cron-summary').innerHTML =
                    `Sessions: <span class="ok">${total}</span>, Messages: <span class="ok">${msgs}</span>`;
            }

            // Memory
            if (d.memory) {
                const entries = d.memory.entry_count || 0;
                const chars = d.memory.total_chars || 0;
                const max = d.memory.max_chars || 2200;
                const pct = max > 0 ? Math.round(chars / max * 100) : 0;
                document.getElementById('projects-summary').innerHTML =
                    `Memory: <span class="ok">${entries}</span> entries, <span class="${pct > 80 ? 'warn' : 'ok'}">${pct}%</span> full`;
            }
        };

        // Fallback: fetch state via REST if WebSocket fails
        fetch('/api/state')
            .then(r => r.json())
            .then(msg => {
                if (msg.ok) ws.onmessage({ data: JSON.stringify(msg) });
            })
            .catch(() => {});
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> str:
    return DASHBOARD_HTML


# ── Entry Point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("TRIBE_HUD_PORT", 9191))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
