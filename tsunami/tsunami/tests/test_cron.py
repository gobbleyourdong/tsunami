"""Tests for cron scheduler."""

import json
import os
import tempfile
import time
import pytest

from tsunami.cron import (
    CronTask,
    CronStore,
    generate_task_id,
    parse_cron,
    cron_matches_now,
    add_jitter,
    RECURRING_MAX_AGE_MS,
)


class TestParseCron:
    """5-field cron expression parsing."""

    def test_every_minute(self):
        result = parse_cron("* * * * *")
        assert result == {"minute": "*", "hour": "*", "dom": "*", "month": "*", "dow": "*"}

    def test_specific_time(self):
        result = parse_cron("30 9 * * 1-5")
        assert result["minute"] == "30"
        assert result["hour"] == "9"
        assert result["dow"] == "1-5"

    def test_invalid_fields(self):
        assert parse_cron("* * *") is None
        assert parse_cron("") is None
        assert parse_cron("* * * * * *") is None  # 6 fields


class TestCronMatchesNow:
    """Cron expression time matching."""

    def test_wildcard_always_matches(self):
        assert cron_matches_now("* * * * *") is True

    def test_step_pattern(self):
        import datetime
        now = time.time()
        dt = datetime.datetime.fromtimestamp(now)
        minute = dt.minute
        # */5 matches when minute % 5 == 0
        if minute % 5 == 0:
            assert cron_matches_now("*/5 * * * *", now) is True
        else:
            assert cron_matches_now("*/5 * * * *", now) is False

    def test_exact_match(self):
        import datetime
        now = time.time()
        dt = datetime.datetime.fromtimestamp(now)
        # Match current hour and minute
        expr = f"{dt.minute} {dt.hour} * * *"
        assert cron_matches_now(expr, now) is True

    def test_non_matching_minute(self):
        import datetime
        now = time.time()
        dt = datetime.datetime.fromtimestamp(now)
        wrong_minute = (dt.minute + 30) % 60
        expr = f"{wrong_minute} {dt.hour} * * *"
        assert cron_matches_now(expr, now) is False

    def test_range(self):
        import datetime
        now = time.time()
        dt = datetime.datetime.fromtimestamp(now)
        expr = f"* {dt.hour}-{dt.hour} * * *"
        assert cron_matches_now(expr, now) is True

    def test_list(self):
        import datetime
        now = time.time()
        dt = datetime.datetime.fromtimestamp(now)
        expr = f"{dt.minute},{(dt.minute+1)%60} * * * *"
        assert cron_matches_now(expr, now) is True


class TestCronTask:
    """Task model."""

    def test_not_expired_when_new(self):
        task = CronTask(id="t1", cron="* * * * *", prompt="test", recurring=True)
        assert task.is_expired is False

    def test_expired_after_max_age(self):
        task = CronTask(
            id="t1", cron="* * * * *", prompt="test",
            recurring=True,
            created_at=time.time() * 1000 - RECURRING_MAX_AGE_MS - 1000,
        )
        assert task.is_expired is True

    def test_non_recurring_never_expires(self):
        task = CronTask(
            id="t1", cron="* * * * *", prompt="test",
            recurring=False,
            created_at=0,  # ancient
        )
        assert task.is_expired is False


class TestGenerateTaskId:
    """Task ID generation."""

    def test_length(self):
        tid = generate_task_id()
        assert len(tid) == 8

    def test_unique(self):
        ids = {generate_task_id() for _ in range(100)}
        assert len(ids) == 100  # all unique


class TestAddJitter:
    """Jitter to prevent thundering herd."""

    def test_adds_positive_offset(self):
        base = 1000.0
        jittered = add_jitter(base, interval_ms=60000)
        assert jittered >= base
        assert jittered <= base + 60000 * 0.1  # max 10% of interval

    def test_respects_cap(self):
        base = 1000.0
        jittered = add_jitter(base, interval_ms=1_000_000_000, max_cap_ms=100)
        assert jittered <= base + 100

    def test_variation(self):
        base = 1000.0
        values = {add_jitter(base, interval_ms=60000) for _ in range(20)}
        assert len(values) > 1  # should have variation


class TestCronStore:
    """Session + file-backed task storage."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = CronStore(self.tmpdir)

    def test_add_session_task(self):
        task = CronTask(id="s1", cron="* * * * *", prompt="test")
        self.store.add(task)
        assert len(self.store.get_all()) == 1

    def test_add_durable_task(self):
        task = CronTask(id="d1", cron="* * * * *", prompt="test", durable=True)
        self.store.add(task)
        # Should be written to file
        assert os.path.exists(os.path.join(self.tmpdir, "scheduled_tasks.json"))
        # And readable
        tasks = self.store.get_all()
        assert len(tasks) == 1
        assert tasks[0].id == "d1"

    def test_remove_session_task(self):
        task = CronTask(id="s1", cron="* * * * *", prompt="test")
        self.store.add(task)
        self.store.remove("s1")
        assert len(self.store.get_all()) == 0

    def test_remove_durable_task(self):
        task = CronTask(id="d1", cron="* * * * *", prompt="test", durable=True)
        self.store.add(task)
        self.store.remove("d1")
        assert len(self.store.get_all()) == 0

    def test_mark_fired(self):
        task = CronTask(id="s1", cron="* * * * *", prompt="test")
        self.store.add(task)
        self.store.mark_fired("s1", fired_at=12345.0)
        tasks = self.store.get_all()
        assert tasks[0].last_fired_at == 12345.0

    def test_find_missed(self):
        task = CronTask(
            id="old", cron="0 9 * * *", prompt="missed",
            recurring=False,
            created_at=time.time() * 1000 - 300_000,  # 5 min ago
        )
        self.store.add(task)
        missed = self.store.find_missed()
        assert len(missed) == 1
        assert missed[0].id == "old"

    def test_no_missed_for_recent(self):
        task = CronTask(
            id="recent", cron="0 9 * * *", prompt="test",
            recurring=False,
            created_at=time.time() * 1000,  # just now
        )
        self.store.add(task)
        assert len(self.store.find_missed()) == 0

    def test_no_missed_for_recurring(self):
        task = CronTask(
            id="rec", cron="* * * * *", prompt="test",
            recurring=True,
            created_at=time.time() * 1000 - 600_000,
        )
        self.store.add(task)
        assert len(self.store.find_missed()) == 0

    def test_mixed_session_and_durable(self):
        self.store.add(CronTask(id="s1", cron="* * * * *", prompt="session"))
        self.store.add(CronTask(id="d1", cron="* * * * *", prompt="durable", durable=True))
        assert len(self.store.get_all()) == 2

    def test_empty_store(self):
        assert self.store.get_all() == []
        assert self.store.find_missed() == []
