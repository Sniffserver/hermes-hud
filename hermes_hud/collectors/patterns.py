"""Collect prompt pattern analytics from Hermes state.db."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from ..models import HourlyActivity, PatternsState, RepeatedPrompt, TaskCluster, ToolWorkflow
from .utils import default_hermes_dir, safe_get

# Keyword lists for task cluster classification (checked in order — first match wins)
_CLUSTERS = [
    ("git ops",    ["commit", "push", "pull", "merge", "branch", "rebase", " pr ", "pull request", "release", "tag", "stash"]),
    ("debugging",  ["fix", "bug", "error", "broken", "failing", "crash", "traceback", "exception", "not work", "doesn't work"]),
    ("code gen",   ["create", "implement", "add feature", "build", "write a", "new function", "new class", "generate"]),
    ("refactor",   ["refactor", "rename", "clean up", "simplify", "extract", "reorganize", "restructure", "move"]),
    ("research",   ["explain", "how does", "what is", "what are", "find", "search", "look at", "investigate", "understand"]),
    ("config/ops", ["install", "configure", "setup", "deploy", "env", "systemd", "cron", "docker", "service"]),
    ("docs",       ["readme", "documentation", "comment", "docstring", "document"]),
]


def _classify(text: str) -> str:
    lower = text.lower()
    for label, keywords in _CLUSTERS:
        if any(kw in lower for kw in keywords):
            return label
    return "other"


def _normalize_prompt(text: str) -> str:
    return text.strip().lower()[:80]


def _extract_session_tool_sequences(db_path: str) -> list[list[str]]:
    """Return ordered tool name lists per session."""
    sequences: list[list[str]] = []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT session_id, tool_calls
            FROM messages
            WHERE tool_calls IS NOT NULL AND tool_calls != ''
            ORDER BY session_id, timestamp ASC
        """)
        session_tools: dict[str, list[str]] = defaultdict(list)
        for row in cur.fetchall():
            try:
                sid = safe_get(row, "session_id", "")
                tc_json = safe_get(row, "tool_calls", "")
                calls = json.loads(tc_json)
                if isinstance(calls, list):
                    for call in calls:
                        name = call.get("function", {}).get("name", "")
                        if name:
                            session_tools[sid].append(name)
            except Exception:
                continue
        conn.close()
        sequences = list(session_tools.values())
    except Exception:
        pass
    return sequences


def _top_trigrams(sequences: list[list[str]], n: int = 10) -> list[ToolWorkflow]:
    """Find the most common 3-tool subsequences across all sessions."""
    counts: Counter = Counter()
    for seq in sequences:
        for i in range(len(seq) - 2):
            trigram = (seq[i], seq[i + 1], seq[i + 2])
            counts[trigram] += 1
    return [
        ToolWorkflow(tool_sequence=list(trigram), count=count)
        for trigram, count in counts.most_common(n)
    ]


def collect_patterns(hermes_dir: str | None = None) -> PatternsState:
    """Collect prompt pattern analytics from state.db."""
    if hermes_dir is None:
        hermes_dir = default_hermes_dir()

    db_path = str(Path(hermes_dir) / "state.db")
    if not Path(db_path).exists():
        return PatternsState()

    cluster_buckets: dict[str, dict] = {
        label: {"count": 0, "msg_sum": 0, "tool_sum": 0, "titles": []}
        for label, _ in _CLUSTERS
    }
    cluster_buckets["other"] = {"count": 0, "msg_sum": 0, "tool_sum": 0, "titles": []}

    prompt_counts: Counter = Counter()
    prompt_last_seen: dict[str, datetime] = {}
    total_user_messages = 0

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Task clustering + repeated prompts — one query gets both
        cur.execute("""
            SELECT s.id, s.title, s.message_count, s.tool_call_count, s.started_at,
                   (SELECT m.content FROM messages m
                    WHERE m.session_id = s.id AND m.role = 'user'
                    ORDER BY m.timestamp ASC LIMIT 1) as first_msg
            FROM sessions s
            ORDER BY s.started_at DESC
        """)

        for row in cur.fetchall():
            try:
                first_msg = safe_get(row, "first_msg") or ""
                title = safe_get(row, "title") or ""
                msg_count = safe_get(row, "message_count", 0) or 0
                tool_count = safe_get(row, "tool_call_count", 0) or 0
                started_raw = safe_get(row, "started_at", 0)
                started = datetime.fromtimestamp(started_raw) if started_raw else datetime.now()

                combined = f"{first_msg} {title}"
                label = _classify(combined)
                bucket = cluster_buckets[label]
                bucket["count"] += 1
                bucket["msg_sum"] += msg_count
                bucket["tool_sum"] += tool_count
                if first_msg and len(bucket["titles"]) < 3:
                    bucket["titles"].append(title or first_msg[:50])

                # Repeated prompts
                if first_msg:
                    norm = _normalize_prompt(first_msg)
                    prompt_counts[norm] += 1
                    if norm not in prompt_last_seen or started > prompt_last_seen[norm]:
                        prompt_last_seen[norm] = started
            except Exception:
                continue

        # Total user messages
        cur.execute("SELECT COUNT(*) FROM messages WHERE role = 'user'")
        row = cur.fetchone()
        if row:
            total_user_messages = safe_get(row, 0, 0)

        # Hourly activity
        cur.execute("""
            SELECT CAST(strftime('%H', started_at, 'unixepoch', 'localtime') AS INTEGER) as hour,
                   COUNT(*) as sessions,
                   COALESCE(SUM(message_count), 0) as messages
            FROM sessions
            GROUP BY hour
            ORDER BY hour
        """)
        hour_map: dict[int, HourlyActivity] = {}
        for row in cur.fetchall():
            try:
                h = safe_get(row, "hour", 0) or 0
                hour_map[h] = HourlyActivity(
                    hour=h,
                    sessions=safe_get(row, "sessions", 0) or 0,
                    messages=safe_get(row, "messages", 0) or 0,
                )
            except Exception:
                continue

        conn.close()
    except Exception:
        return PatternsState()

    # Build clusters (skip empty)
    clusters = []
    for label, bucket in cluster_buckets.items():
        if bucket["count"] == 0:
            continue
        clusters.append(TaskCluster(
            label=label,
            count=bucket["count"],
            avg_messages=bucket["msg_sum"] / bucket["count"],
            avg_tool_calls=bucket["tool_sum"] / bucket["count"],
            example_titles=bucket["titles"],
        ))
    clusters.sort(key=lambda c: -c.count)

    # Build repeated prompts (seen more than once)
    repeated = []
    for norm, count in prompt_counts.most_common(15):
        if count < 2:
            break
        repeated.append(RepeatedPrompt(
            pattern=norm,
            count=count,
            last_seen=prompt_last_seen.get(norm, datetime.now()),
            could_be_skill=count >= 3,
        ))

    # Fill all 24 hours
    hourly = [hour_map.get(h, HourlyActivity(hour=h, sessions=0, messages=0)) for h in range(24)]

    # Tool workflows
    sequences = _extract_session_tool_sequences(db_path)
    workflows = _top_trigrams(sequences)

    return PatternsState(
        clusters=clusters,
        repeated_prompts=repeated,
        hourly_activity=hourly,
        tool_workflows=workflows,
        total_user_messages=total_user_messages,
    )
