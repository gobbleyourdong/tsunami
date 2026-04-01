"""Tests for circulation — tension-aware routing."""

import pytest
from tsunami.circulation import Circulation, FlowType, ValidationStatus


class TestRouting:
    """Route based on tension score."""

    def setup_method(self):
        self.circ = Circulation()

    def test_low_tension_delivers(self):
        route = self.circ.route("What is 2+2?", tension=0.1)
        assert route.action == "deliver"
        assert route.flow_type == FlowType.NONE

    def test_high_tension_with_capability_marker_searches(self):
        route = self.circ.route("What is the current stock price of NVIDIA?", tension=0.5)
        assert route.action == "search"
        assert "search_web" in route.tools

    def test_critical_tension_refuses(self):
        route = self.circ.route("Tell me about quantum gravity", tension=0.75)
        assert route.action == "refuse"

    def test_truth_gap_detected(self):
        route = self.circ.route("Is it true that the earth is flat?", tension=0.4)
        assert route.flow_type == FlowType.TRUTH_GAP

    def test_moderate_tension_suggests_search(self):
        route = self.circ.route("How does photosynthesis work?", tension=0.55)
        assert "search_web" in route.tools or route.action == "caveat"


class TestValidation:
    """Validate tool results by comparing tension before/after."""

    def setup_method(self):
        self.circ = Circulation()

    def test_tension_dropped_verified(self):
        v = self.circ.validate_result("q", "result", pre_tension=0.5, post_tension=0.1)
        assert v.status == ValidationStatus.VERIFIED
        assert v.action == "use"

    def test_tension_increased_rejected(self):
        v = self.circ.validate_result("q", "result", pre_tension=0.3, post_tension=0.6)
        assert v.status == ValidationStatus.REJECTED
        assert v.action in ("retry", "reject")

    def test_tension_unchanged_unverified(self):
        v = self.circ.validate_result("q", "result", pre_tension=0.25, post_tension=0.25)
        assert v.status == ValidationStatus.UNVERIFIED
        assert v.caveat is not None
