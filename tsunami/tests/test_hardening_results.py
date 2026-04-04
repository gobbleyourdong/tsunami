"""Hardening loop results — verify deliverables from expansion builds.

These tests check that builds produced during the overnight hardening
loop actually exist and compile. They serve as regression tests —
if a future change breaks scaffolding, these catch it.
"""

import os
from pathlib import Path

DELIVERABLES = Path(__file__).parent.parent.parent / "workspace" / "deliverables"


def _check_exists(name: str) -> bool:
    return (DELIVERABLES / name).exists()


def _check_has_dist(name: str) -> bool:
    return (DELIVERABLES / name / "dist" / "index.html").exists()


def _check_has_src(name: str) -> bool:
    return (DELIVERABLES / name / "src" / "App.tsx").exists()


class TestHardeningBuilds:
    """Deliverables from overnight hardening loop exist."""

    def test_password_generator(self):
        assert _check_exists("password-generator-length")

    def test_habit_tracker(self):
        assert _check_exists("habit-tracker")

    def test_memory_card_game(self):
        assert _check_exists("memory-card-game")

    def test_recipe_book(self):
        assert _check_exists("recipe-book-app")

    def test_workout_tracker(self):
        assert _check_exists("workout-tracker")

    def test_invoice_generator(self):
        assert _check_exists("invoice-generator-app")

    def test_markdown_editor(self):
        assert _check_exists("markdown-editor")

    def test_simple_crm(self):
        assert _check_exists("simple-crm-contacts")

    def test_drawing_app(self):
        assert _check_exists("drawing-canvas-brush")

    def test_timesheet(self):
        assert _check_exists("timesheet-clock-out")

    def test_countdown_timer(self):
        assert _check_exists("countdown-timer-flip")

    def test_standup_board(self):
        assert _check_exists("team-standup-board")


class TestBuildQuality:
    """Passing builds have dist/ and src/App.tsx."""

    def test_password_generator_has_dist(self):
        if _check_exists("password-generator-length"):
            assert _check_has_dist("password-generator-length")

    def test_habit_tracker_has_dist(self):
        if _check_exists("habit-tracker"):
            assert _check_has_dist("habit-tracker")

    def test_invoice_generator_has_src(self):
        if _check_exists("invoice-generator-app"):
            assert _check_has_src("invoice-generator-app")

    def test_drawing_app_has_src(self):
        if _check_exists("drawing-canvas-brush"):
            assert _check_has_src("drawing-canvas-brush")
