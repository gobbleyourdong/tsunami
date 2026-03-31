"""Git operation detection — passively instrument git ops in shell output.

Instead of building dedicated git tools, we detect git operations
from shell_exec output using regex patterns. This is lighter and
works with any git workflow the model invents.

Detected operations: commit, push, pull, merge, rebase, checkout,
branch create/delete, PR create/merge (via gh CLI).
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field

log = logging.getLogger("tsunami.git_detect")


@dataclass
class GitOperation:
    """A detected git operation."""
    op: str  # commit, push, pull, merge, rebase, checkout, branch, pr_create, pr_merge
    details: dict = field(default_factory=dict)


# --- Detection patterns ---

# git commit — extract SHA and message
_COMMIT_SHA_RE = re.compile(r'\[[\w/-]+\s+([a-f0-9]{7,40})\]')
_COMMIT_MSG_RE = re.compile(r'\[[\w/-]+\s+[a-f0-9]+\]\s+(.+)')

# git push — extract remote and branch
_PUSH_RE = re.compile(r'(?:To\s+\S+|->)\s+(\S+)')

# git checkout/switch — extract branch
_CHECKOUT_RE = re.compile(r"Switched to (?:a new )?branch '([^']+)'")

# git merge
_MERGE_RE = re.compile(r'Merge made by|Fast-forward|Already up to date')

# git pull
_PULL_RE = re.compile(r'(?:Updating|Already up to date|Fast-forward)')

# gh pr create — extract PR number and URL
_PR_CREATE_RE = re.compile(r'https://github\.com/\S+/pull/(\d+)')
_PR_MERGE_RE = re.compile(r'Merged.*pull request #(\d+)')

# git branch
_BRANCH_CREATE_RE = re.compile(r"Created branch '([^']+)'|Switched to a new branch '([^']+)'")
_BRANCH_DELETE_RE = re.compile(r"Deleted branch (\S+)")


def detect_git_ops(command: str, output: str) -> list[GitOperation]:
    """Detect git operations from a shell command and its output.

    Returns a list of detected operations (usually 0 or 1).
    """
    ops = []
    cmd_lower = command.strip().lower()

    # git commit
    if "git commit" in cmd_lower or "git c " in cmd_lower:
        sha_match = _COMMIT_SHA_RE.search(output)
        msg_match = _COMMIT_MSG_RE.search(output)
        if sha_match:
            ops.append(GitOperation(
                op="commit",
                details={
                    "sha": sha_match.group(1),
                    "message": msg_match.group(1) if msg_match else "",
                },
            ))

    # git push
    elif "git push" in cmd_lower:
        ops.append(GitOperation(op="push", details={"command": command.strip()}))

    # git pull
    elif "git pull" in cmd_lower:
        if _PULL_RE.search(output):
            ops.append(GitOperation(op="pull"))

    # git merge
    elif "git merge" in cmd_lower:
        if _MERGE_RE.search(output):
            ops.append(GitOperation(op="merge", details={"command": command.strip()}))

    # git rebase
    elif "git rebase" in cmd_lower:
        ops.append(GitOperation(op="rebase", details={"command": command.strip()}))

    # git checkout / git switch
    elif "git checkout" in cmd_lower or "git switch" in cmd_lower:
        branch_match = _CHECKOUT_RE.search(output)
        if branch_match:
            ops.append(GitOperation(
                op="checkout",
                details={"branch": branch_match.group(1)},
            ))

    # gh pr create
    elif "gh pr create" in cmd_lower:
        pr_match = _PR_CREATE_RE.search(output)
        if pr_match:
            ops.append(GitOperation(
                op="pr_create",
                details={"pr_number": int(pr_match.group(1)), "url": pr_match.group(0)},
            ))

    # gh pr merge
    elif "gh pr merge" in cmd_lower:
        pr_match = _PR_MERGE_RE.search(output)
        if pr_match:
            ops.append(GitOperation(
                op="pr_merge",
                details={"pr_number": int(pr_match.group(1))},
            ))

    # git branch -d / -D
    elif re.search(r'git branch\s+.*-[dD]', cmd_lower):
        del_match = _BRANCH_DELETE_RE.search(output)
        if del_match:
            ops.append(GitOperation(
                op="branch_delete",
                details={"branch": del_match.group(1)},
            ))

    return ops


class GitTracker:
    """Accumulates git operations across a session."""

    def __init__(self):
        self.operations: list[GitOperation] = []

    def track(self, command: str, output: str):
        """Detect and record git operations from shell output."""
        ops = detect_git_ops(command, output)
        self.operations.extend(ops)
        for op in ops:
            log.info(f"Git: {op.op} {op.details}")

    @property
    def commits(self) -> list[GitOperation]:
        return [op for op in self.operations if op.op == "commit"]

    @property
    def pushes(self) -> list[GitOperation]:
        return [op for op in self.operations if op.op == "push"]

    @property
    def prs(self) -> list[GitOperation]:
        return [op for op in self.operations if op.op.startswith("pr_")]

    def summary(self) -> str:
        """One-line summary of git activity."""
        if not self.operations:
            return "No git operations"
        parts = []
        n_commits = len(self.commits)
        n_pushes = len(self.pushes)
        n_prs = len(self.prs)
        if n_commits:
            parts.append(f"{n_commits} commit{'s' if n_commits > 1 else ''}")
        if n_pushes:
            parts.append(f"{n_pushes} push{'es' if n_pushes > 1 else ''}")
        if n_prs:
            parts.append(f"{n_prs} PR{'s' if n_prs > 1 else ''}")
        other = len(self.operations) - n_commits - n_pushes - n_prs
        if other:
            parts.append(f"{other} other")
        return "Git: " + ", ".join(parts)
