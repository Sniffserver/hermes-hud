"""Prompt Patterns panel — task clustering, repeated requests, peak hours, tool workflows."""

from __future__ import annotations

from rich.markup import escape
from textual.app import ComposeResult
from textual.widgets import Static

from ..models import PatternsState


class PatternsPanel(Static):
    """Panel showing prompt pattern analytics."""

    DEFAULT_CSS = """
    PatternsPanel {
        height: auto;
        padding: 1 2;
        border: solid $warning;
    }
    """

    def __init__(self, patterns: PatternsState, **kwargs):
        super().__init__(**kwargs)
        self.patterns = patterns

    def compose(self) -> ComposeResult:
        p = self.patterns
        total_sessions = sum(c.count for c in p.clusters)

        yield Static("[bold]◈ PROMPT PATTERNS[/bold]")
        yield Static(
            f"  Analyzed: [bold]{p.total_user_messages:,}[/bold] user messages "
            f"across [bold]{total_sessions}[/bold] sessions"
        )
        yield Static("")

        # ── Task Clusters ──
        yield Static("  [bold underline]What You Use The Agent For[/bold underline]")
        if p.clusters:
            max_count = p.clusters[0].count
            for c in p.clusters:
                bar_len = int(c.count / max(max_count, 1) * 28)
                bar = "█" * bar_len + "░" * (28 - bar_len)
                pct = int(c.count / max(total_sessions, 1) * 100)
                yield Static(
                    f"  [bold]{c.label:<12}[/bold] [cyan]{bar}[/cyan] "
                    f"{c.count} sessions ({pct}%)  "
                    f"[dim]avg {c.avg_messages:.0f} msgs, {c.avg_tool_calls:.0f} tools[/dim]"
                )
        else:
            yield Static("  [dim]No session data[/dim]")
        yield Static("")

        # ── Peak Hours ──
        yield Static("  [bold underline]When You Work[/bold underline]")
        if p.hourly_activity:
            max_sessions = max(h.sessions for h in p.hourly_activity) or 1
            # Sparkline using block chars
            _blocks = " ▁▂▃▄▅▆▇█"
            parts = []
            for h in p.hourly_activity:
                idx = int(h.sessions / max_sessions * (len(_blocks) - 1))
                char = _blocks[idx]
                if h.sessions == max_sessions and max_sessions > 0:
                    parts.append(f"[green]{h.hour:02d}[bold]{char}[/bold][/green]")
                elif h.sessions > max_sessions * 0.5:
                    parts.append(f"[yellow]{h.hour:02d}{char}[/yellow]")
                else:
                    parts.append(f"[dim]{h.hour:02d}{char}[/dim]")
            yield Static("  " + "  ".join(parts[:12]))
            yield Static("  " + "  ".join(parts[12:]))
            if p.peak_hour is not None:
                peak = p.hourly_activity[p.peak_hour]
                yield Static(
                    f"  Peak: [bold green]{p.peak_hour:02d}:00[/bold green] "
                    f"[dim]({peak.sessions} sessions)[/dim]"
                )
        yield Static("")

        # ── Repeated Requests ──
        yield Static("  [bold underline]Repeated Requests[/bold underline]")
        if p.repeated_prompts:
            for r in p.repeated_prompts:
                text = escape(r.pattern[:70])
                if r.could_be_skill:
                    yield Static(
                        f"  [bold yellow]⚡[/bold yellow] [italic]\"{text}\"[/italic] "
                        f"— [bold]{r.count}[/bold] times  "
                        f"[yellow dim](make this a skill?)[/yellow dim]"
                    )
                else:
                    yield Static(
                        f"     [dim]\"{text}\"[/dim] "
                        f"— {r.count} times"
                    )
        else:
            yield Static("  [dim]No repeated requests detected[/dim]")
        yield Static("")

        # ── Tool Workflows ──
        yield Static("  [bold underline]Common Tool Chains[/bold underline]")
        if p.tool_workflows:
            max_wf = p.tool_workflows[0].count if p.tool_workflows else 1
            for wf in p.tool_workflows:
                seq = " [dim]→[/dim] ".join(
                    f"[cyan]{escape(t)}[/cyan]" for t in wf.tool_sequence
                )
                bar_len = int(wf.count / max(max_wf, 1) * 16)
                bar = "▓" * bar_len
                yield Static(f"  {seq}   [magenta]{bar}[/magenta] {wf.count}")
        else:
            yield Static("  [dim]No tool sequences found[/dim]")
