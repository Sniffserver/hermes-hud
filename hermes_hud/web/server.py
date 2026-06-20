"""Tribe HUD Web Server — FastAPI + WebSocket for live dashboard.

Serves the same data as the TUI but via HTTP/WebSocket for remote access.
"""

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


async def broadcast(data: dict[str, Any]) -> None:
    """Broadcast data to all connected WebSocket clients."""
    disconnected = []
    for ws in _connections:
        try:
            await ws.send_json(data)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        _connections.remove(ws)


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
        _connections.remove(ws)


# ── Dashboard HTML ────────────────────────────────────────────────────────

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="et">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tribe HUD — Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'JetBrains Mono', monospace; background: #1d2021; color: #ebdbb2; padding: 1rem; }
        h1 { color: #fe8019; margin-bottom: 1rem; }
        h2 { color: #fabd2f; margin: 1rem 0 0.5rem; font-size: 0.9rem; text-transform: uppercase; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem; }
        .panel { background: #282828; border: 1px solid #504945; border-radius: 4px; padding: 1rem; }
        .panel h3 { color: #83a598; margin-bottom: 0.5rem; }
        .status-ok { color: #b8bb26; }
        .status-warn { color: #fabd2f; }
        .status-error { color: #fb4934; }
        table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
        th, td { padding: 0.3rem 0.5rem; text-align: left; border-bottom: 1px solid #3c3836; }
        th { color: #928374; }
        .timestamp { color: #7c6f64; font-size: 0.7rem; }
        #connection-status { position: fixed; top: 0.5rem; right: 0.5rem; padding: 0.3rem 0.6rem; border-radius: 3px; font-size: 0.7rem; }
        .connected { background: #b8bb26; color: #1d2021; }
        .disconnected { background: #fb4934; color: #1d2021; }
    </style>
</head>
<body>
    <div id="connection-status" class="disconnected">● Disconnected</div>
    <h1>⚒ TRIBE HUD</h1>
    <p class="timestamp" id="last-update">Waiting for data...</p>

    <div class="grid">
        <div class="panel">
            <h3>🏥 Health</h3>
            <div id="health-data">Loading...</div>
        </div>
        <div class="panel">
            <h3>📈 Growth</h3>
            <div id="growth-data">Loading...</div>
        </div>
        <div class="panel">
            <h3>⏱ Cron</h3>
            <div id="cron-data">Loading...</div>
        </div>
        <div class="panel">
            <h3>📂 Projects</h3>
            <div id="projects-data">Loading...</div>
        </div>
    </div>

    <script>
        const ws = new WebSocket(`ws://${location.host}/ws/hud`);
        const statusEl = document.getElementById('connection-status');
        const updateEl = document.getElementById('last-update');

        ws.onopen = () => {
            statusEl.textContent = '● Connected';
            statusEl.className = 'connected';
        };

        ws.onclose = () => {
            statusEl.textContent = '● Disconnected';
            statusEl.className = 'disconnected';
        };

        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            if (!msg.ok) return;
            const data = msg.data;
            updateEl.textContent = 'Last update: ' + new Date().toLocaleTimeString();

            // Health
            if (data.health) {
                const h = data.health;
                document.getElementById('health-data').innerHTML =
                    `Services: <span class="status-ok">${h.services_ok || 0} OK</span> | ` +
                    `<span class="status-error">${h.services_failed || 0} Failed</span>`;
            }

            // Growth
            if (data.growth) {
                const g = data.growth;
                document.getElementById('growth-data').innerHTML =
                    `Skills: ${g.skills_count || 0} | Sessions: ${g.sessions_count || 0}`;
            }

            // Cron
            if (data.cron) {
                const c = data.cron;
                document.getElementById('cron-data').innerHTML =
                    `Jobs: ${c.jobs_count || 0} | Last run: ${c.last_run || 'never'}`;
            }

            // Projects
            if (data.projects) {
                const p = data.projects;
                document.getElementById('projects-data').innerHTML =
                    `Repos: ${p.repos_count || 0} | Dirty: ${p.dirty_count || 0}`;
            }
        };
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
