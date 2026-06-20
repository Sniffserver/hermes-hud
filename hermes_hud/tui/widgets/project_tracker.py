"""Project Tracker widget for Tribe HUD — security-safe.

Scans git repositories and displays ONLY metadata:
- Repo name, branch, dirty status
- Uncommitted files count (not filenames)
- Last commit time (not message content)
- Top file extensions (not file paths)
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from textual.widgets import Static


@dataclass
class GitRepo:
    name: str
    path: str
    branch: str = "?"
    dirty: bool = False
    uncommitted_count: int = 0
    last_commit_time: str = "?"
    top_extensions: dict = field(default_factory=dict)
    is_bare: bool = False
    error: Optional[str] = None


def _run_git(repo_path: str, *args, timeout: int = 5) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, *args],
            capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return 1, "", "git not found"
    except subprocess.TimeoutExpired:
        return 1, "", "timeout"
    except Exception as e:
        return 1, "", str(e)


def scan_repo(path: str) -> GitRepo:
    name = Path(path).name
    repo = GitRepo(name=name, path=path)
    rc, _, _ = _run_git(path, "rev-parse", "--git-dir")
    if rc != 0:
        repo.error = "Not a git repo"
        return repo
    rc, out, _ = _run_git(path, "rev-parse", "--is-bare-repository")
    if out == "true":
        repo.is_bare = True
        return repo
    rc, out, _ = _run_git(path, "rev-parse", "--abbrev-ref", "HEAD")
    if rc == 0:
        repo.branch = out
    rc, out, _ = _run_git(path, "status", "--porcelain")
    if rc == 0:
        lines = [l for l in out.splitlines() if l.strip()]
        repo.uncommitted_count = len(lines)
        repo.dirty = repo.uncommitted_count > 0
    rc, out, _ = _run_git(path, "log", "-1", "--format=%ar")
    if rc == 0:
        repo.last_commit_time = out
    try:
        ext_counts: dict[str, int] = {}
        git_dir = Path(path) / ".git"
        for f in Path(path).rglob("*"):
            if f.is_file() and not str(f).startswith(str(git_dir)):
                if f.name.startswith(".env") or f.name.endswith((".key", ".pem", ".secret")):
                    continue
                ext = f.suffix.lower() or "(no ext)"
                ext_counts[ext] = ext_counts.get(ext, 0) + 1
        sorted_exts = sorted(ext_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        repo.top_extensions = dict(sorted_exts)
    except Exception:
        pass
    return repo


def scan_projects(projects_dir: str | None = None) -> list[GitRepo]:
    if not projects_dir:
        projects_dir = os.environ.get("HERMES_HUD_PROJECTS_DIR", str(Path.home() / "projects"))
    base = Path(projects_dir)
    if not base.exists():
        return []
    repos: list[GitRepo] = []
    for entry in sorted(base.iterdir()):
        if entry.is_dir() and (entry / ".git").exists():
            repos.append(scan_repo(str(entry)))
    return repos


class ProjectTrackerWidget(Static):
    """Textual widget displaying git project status — security-safe."""

    def on_mount(self) -> None:
        self.refresh_data()

    def refresh_data(self) -> None:
        repos = scan_projects()

        lines = [
            "📂 PROJECT TRACKER",
            "─" * 55,
            f"{'':3} {'Repo':<20} {'Branch':<12} {'Status':<10} {'Pending':<10} {'Last Commit'}",
            "─" * 55,
        ]

        if not repos:
            lines.append("  No git repositories found.")
        else:
            for repo in repos:
                if repo.error:
                    lines.append(f"  ⚠️  {repo.name}: {repo.error}")
                    continue
                if repo.is_bare:
                    lines.append(f"  📦 {repo.name}: bare repo")
                    continue
                status = "🔴 dirty" if repo.dirty else "🟢 clean"
                pending = str(repo.uncommitted_count) if repo.dirty else "0"
                last = repo.last_commit_time or "?"
                lines.append(f"     {repo.name:<20} {repo.branch:<12} {status:<10} {pending:<10} {last}")
                if repo.top_extensions:
                    ext_str = ", ".join(f"{ext}: {cnt}" for ext, cnt in list(repo.top_extensions.items())[:3])
                    lines.append(f"         └─ {ext_str}")

        lines.append("─" * 55)
        dirty_count = sum(1 for r in repos if r.dirty)
        lines.append(f"  Total: {len(repos)} repos | 🔴 dirty: {dirty_count} | 🟢 clean: {len(repos) - dirty_count}")

        self.update("\n".join(lines))
