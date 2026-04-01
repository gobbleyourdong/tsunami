"""Tests for pressure — tension monitoring over time."""

import pytest
from tsunami.pressure import Pressure, AlertLevel


class TestPressure:
    """Track tension over time."""

    def test_starts_calm(self):
        p = Pressure()
        assert p.alert_level == AlertLevel.CALM
        assert p.average_tension == 0.0

    def test_low_readings_stay_calm(self):
        p = Pressure()
        for _ in range(10):
            p.record(0.1)
        assert p.alert_level == AlertLevel.CALM

    def test_high_readings_escalate(self):
        p = Pressure()
        for _ in range(10):
            p.record(0.7)
        assert p.alert_level == AlertLevel.CRUSHING

    def test_consecutive_high_tracked(self):
        p = Pressure()
        p.record(0.6)
        p.record(0.7)
        p.record(0.8)
        assert p.consecutive_high == 3

    def test_low_reading_resets_consecutive(self):
        p = Pressure()
        p.record(0.7)
        p.record(0.7)
        p.record(0.1)
        assert p.consecutive_high == 0

    def test_should_force_search(self):
        p = Pressure()
        p.record(0.6)
        p.record(0.7)
        assert p.should_force_search()

    def test_should_refuse_after_4(self):
        p = Pressure()
        for _ in range(4):
            p.record(0.8)
        assert p.should_refuse()

    def test_reset(self):
        p = Pressure()
        p.record(0.8)
        p.record(0.8)
        p.reset()
        assert p.consecutive_high == 0

    def test_format_status(self):
        p = Pressure()
        p.record(0.3)
        status = p.format_status()
        assert "moderate" in status.lower() or "calm" in status.lower()
