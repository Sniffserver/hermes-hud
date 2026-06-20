"""Project Tracker widget for Tribe HUD — security-safe.

Scans git repositories and displays ONLY metadata:
- Repo name, branch, dirty status
- Uncommitted files count (not filenames)
- Last commit time (not message content)
- Top file extensions (not file paths)

NEVER exposes: file contents, commit messages with secrets,
API keys, credentials, or private data.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from textual.widgets import Static


# ── Data Model ────────────────────────────────────────────────────────────

@dataclass
class GitRepo:
    name: str
    path: str
    branch: str = "?"
    dirty: bool = False
    uncommitted_count: int = 0  # Count only, no filenames
    last_commit_time: str = "?"  # Time only, no message content
    top_extensions: dict = field(default_factory=dict)  # Extension counts only
    is_bare: bool = False
    error: Optional[str] = None


# ── Git Helpers ────────────────────────────────────────────────────────────

def _run_git(repo_path: str, *args, timeout: int = 5) -> tuple[int, str, str]:
    """Run a git command. Returns (returncode, stdout, stderr)."""
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
    """Scan a single git repository — metadata only, no content."""
    name = Path(path).name
    repo = GitRepo(name=name, path=path)

    # Check if it's a git repo
    rc, _, _ = _run_git(path, "rev-parse", "--git-dir")
    if rc != 0:
        repo.error = "Not a git repo"
        return repo

    # Check if bare
    rc, out, _ = _run_git(path, "rev-parse", "--is-bare-repository")
    if out == "true":
        repo.is_bare = True
        return repo

    # Branch name only
    rc, out, _ = _run_git(path, "rev-parse", "--abbrev-ref", "HEAD")
    if rc == 0:
        repo.branch = out

    # Dirty status — count only, NO filenames
    rc, out, _ = _run_git(path, "status", "--porcelain")
    if rc == 0:
        lines = [l for l in out.splitlines() if l.strip()]
        repo.uncommitted_count = len(lines)
        repo.dirty = repo.uncommitted_count > 0

    # Last commit time only — NO message content (could contain secrets)
    rc, out, _ = _run_git(path, "log", "-1", "--format=%ar")
    if rc == 0:
        repo.last_commit_time = out

    # Top file extensions only — NO file paths (could contain sensitive names)
    try:
        ext_counts: dict[str, int] = {}
        git_dir = Path(path) / ".git"
        for f in Path(path).rglob("*"):
            if f.is_file() and not str(f).startswith(str(git_dir)):
                # Skip common sensitive files
                if f.name.startswith(".env") or f.name.endswith((".key", ".pem", ".secret")):
                    continue
                ext = f.suffix.lower() or "(no ext)"
                ext_counts[ext] = ext_counts.get(ext, 0) + 1
        # Top 5 extensions
        sorted_exts = sorted(ext_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        repo.top_extensions = dict(sorted_exts)
    except Exception:
        pass

    return repo


def scan_projects(projects_dir: str | None = None) -> list[GitRepo]:
    """Scan a directory for git repositories."""
    if not projects_dir:
        projects_dir = os.environ.get(
            "HERMES_HUD_PROJECTS_DIR",
            str(Path.home() / "projects")
        )

    base = Path(projects_dir)
    if not base.exists():
        return []

    repos: list[GitRepo] = []
    for entry in sorted(base.iterdir()):
        if entry.is_dir() and (entry / ".git").exists():
            repos.append(scan_repo(str(entry)))

    return repos


# ── Textual Widget ────────────────────────────────────────────────────────

class ProjectTrackerWidget(Static):
    """Textual widget displaying git project status — security-safe."""

    def render(self) -> str:
        repos = scan_projects()

        if not repos:
            return (
                "📂 PROJECT TRACKER\n"
                "─────────────────────────────────────────\n"
                "No git repositories found.\n"
                f"Scan dir: {os.environ.get('HERMES_HUD_PROJECTS_DIR', '~/projects')}"
            )

        lines = [
            "📂 PROJECT TRACKER",
            "─────────────────────────────────────────",
            f"{'Repo':<20} {'Branch':<12} {'Status':<10} {'Pending':<10} {'Last Commit'}",
            "─" * 80,
        ]

        for repo in repos:
            if repo.error:
                lines.append(f"{repo.name:<20} ⚠ {repo.error}")
                continue

            if repo.is_bare:
                lines.append(f"{repo.name:<20} (bare)")
                continue

            status = "🔴 dirty" if repo.dirty else "🟢 clean"
            pending = str(repo.uncommitted_count) if repo.dirty else "0"
            last = repo.last_commit_time or "?"

            lines.append(
                f"{repo.name:<20} {repo.branch:<12} {status:<10} {pending:<10} {last}"
            )

            # Extension stats only — no file paths
            if repo.top_extensions:
                ext_str = ", ".join(f"{ext}: {cnt}" for ext, cnt in repo.top_extensions.items())
                lines.append(f"  └─ {ext_str[:60]}")

        lines.append("─" * 80)
        dirty_count = sum(1 for r in repos if r.dirty)
        lines.append(f"Total: {len(repos)} repos | 🔴 dirty: {dirty_count} | 🟢 clean: {len(repos) - dirty_count}")

        return "\n".join(lines)
