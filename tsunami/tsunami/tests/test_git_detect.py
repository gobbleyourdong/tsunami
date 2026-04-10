"""Tests for git operation detection."""

import pytest

from tsunami.git_detect import detect_git_ops, GitTracker, GitOperation


class TestDetectGitOps:
    """Regex-based detection of git operations from shell output."""

    def test_detect_commit(self):
        cmd = "git commit -m 'Fix the bug'"
        output = "[main abc1234] Fix the bug\n 1 file changed, 2 insertions(+)"
        ops = detect_git_ops(cmd, output)
        assert len(ops) == 1
        assert ops[0].op == "commit"
        assert ops[0].details["sha"] == "abc1234"
        assert "Fix the bug" in ops[0].details["message"]

    def test_detect_commit_long_sha(self):
        cmd = "git commit -m 'test'"
        output = "[feature/x abc1234567890] test commit"
        ops = detect_git_ops(cmd, output)
        assert len(ops) == 1
        assert ops[0].details["sha"] == "abc1234567890"

    def test_detect_push(self):
        cmd = "git push origin main"
        output = "To github.com:user/repo.git\n   abc1234..def5678  main -> main"
        ops = detect_git_ops(cmd, output)
        assert len(ops) == 1
        assert ops[0].op == "push"

    def test_detect_pull(self):
        cmd = "git pull"
        output = "Updating abc1234..def5678\nFast-forward\n file.py | 2 +-"
        ops = detect_git_ops(cmd, output)
        assert len(ops) == 1
        assert ops[0].op == "pull"

    def test_detect_checkout(self):
        cmd = "git checkout -b feature/new"
        output = "Switched to a new branch 'feature/new'"
        ops = detect_git_ops(cmd, output)
        assert len(ops) == 1
        assert ops[0].op == "checkout"
        assert ops[0].details["branch"] == "feature/new"

    def test_detect_merge(self):
        cmd = "git merge feature/x"
        output = "Merge made by the 'ort' strategy."
        ops = detect_git_ops(cmd, output)
        assert len(ops) == 1
        assert ops[0].op == "merge"

    def test_detect_rebase(self):
        cmd = "git rebase main"
        output = "Successfully rebased and updated refs/heads/feature."
        ops = detect_git_ops(cmd, output)
        assert len(ops) == 1
        assert ops[0].op == "rebase"

    def test_detect_pr_create(self):
        cmd = "gh pr create --title 'Fix bug' --body 'Details'"
        output = "https://github.com/user/repo/pull/42\n"
        ops = detect_git_ops(cmd, output)
        assert len(ops) == 1
        assert ops[0].op == "pr_create"
        assert ops[0].details["pr_number"] == 42

    def test_detect_pr_merge(self):
        cmd = "gh pr merge 42"
        output = "Merged pull request #42"
        ops = detect_git_ops(cmd, output)
        assert len(ops) == 1
        assert ops[0].op == "pr_merge"
        assert ops[0].details["pr_number"] == 42

    def test_detect_branch_delete(self):
        cmd = "git branch -D feature/old"
        output = "Deleted branch feature/old (was abc1234)."
        ops = detect_git_ops(cmd, output)
        assert len(ops) == 1
        assert ops[0].op == "branch_delete"
        assert ops[0].details["branch"] == "feature/old"

    def test_no_detection_on_non_git(self):
        cmd = "ls -la"
        output = "total 42\ndrwxr-xr-x  5 user user 4096 ..."
        ops = detect_git_ops(cmd, output)
        assert len(ops) == 0

    def test_no_detection_on_failed_commit(self):
        cmd = "git commit -m 'test'"
        output = "nothing to commit, working tree clean"
        ops = detect_git_ops(cmd, output)
        assert len(ops) == 0  # no SHA in output


class TestGitTracker:
    """Session-level git operation accumulation."""

    def test_tracks_multiple_ops(self):
        tracker = GitTracker()
        tracker.track("git commit -m 'a'", "[main abc1234] a")
        tracker.track("git commit -m 'b'", "[main def5678] b")
        tracker.track("git push", "To github.com:user/repo.git")
        assert len(tracker.commits) == 2
        assert len(tracker.pushes) == 1

    def test_summary_empty(self):
        tracker = GitTracker()
        assert tracker.summary() == "No git operations"

    def test_summary_with_ops(self):
        tracker = GitTracker()
        tracker.track("git commit -m 'a'", "[main abc1234] a")
        tracker.track("git push", "To github.com:user/repo.git")
        summary = tracker.summary()
        assert "1 commit" in summary
        assert "1 push" in summary

    def test_summary_plurals(self):
        tracker = GitTracker()
        tracker.track("git commit -m 'a'", "[main abc1234] a")
        tracker.track("git commit -m 'b'", "[main def5678] b")
        summary = tracker.summary()
        assert "2 commits" in summary

    def test_prs_property(self):
        tracker = GitTracker()
        tracker.track("gh pr create --title 'x'", "https://github.com/u/r/pull/1")
        assert len(tracker.prs) == 1

    def test_ignores_non_git(self):
        tracker = GitTracker()
        tracker.track("python test.py", "All 5 tests passed")
        assert len(tracker.operations) == 0
