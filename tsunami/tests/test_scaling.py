"""Tests for auto-scaling bee slots based on memory."""

import pytest
from tsunami.scaling import calculate_bee_slots, MAX_BEES, MIN_BEES


class TestCalculateBeeSlots:
    """Memory-based bee slot calculation."""

    def test_4gb_lite_mode(self):
        config = calculate_bee_slots(total_mem_gb=4, queen_model="9b")
        assert config["mode"] == "lite"
        assert config["bee_slots"] == MIN_BEES

    def test_8gb_full_9b(self):
        config = calculate_bee_slots(total_mem_gb=8, queen_model="9b")
        assert config["mode"] == "full"
        assert config["bee_slots"] >= 1

    def test_12gb_full_9b(self):
        config = calculate_bee_slots(total_mem_gb=12, queen_model="9b")
        assert config["mode"] == "full"
        assert config["bee_slots"] >= 2

    def test_16gb_good_slots(self):
        config = calculate_bee_slots(total_mem_gb=16, queen_model="9b")
        assert config["mode"] == "full"
        assert config["bee_slots"] >= 4

    def test_32gb_27b_queen(self):
        config = calculate_bee_slots(total_mem_gb=32, queen_model="27b")
        assert config["mode"] == "full"
        assert config["bee_slots"] >= 1

    def test_64gb_many_bees(self):
        config = calculate_bee_slots(total_mem_gb=64, queen_model="27b")
        assert config["mode"] == "full"
        assert config["bee_slots"] >= 16

    def test_128gb_max_bees(self):
        config = calculate_bee_slots(total_mem_gb=128, queen_model="27b")
        assert config["mode"] == "full"
        assert config["bee_slots"] == MAX_BEES

    def test_never_exceeds_max(self):
        config = calculate_bee_slots(total_mem_gb=1000, queen_model="9b")
        assert config["bee_slots"] <= MAX_BEES

    def test_never_below_min(self):
        config = calculate_bee_slots(total_mem_gb=4, queen_model="2b")
        assert config["bee_slots"] >= MIN_BEES

    def test_2b_queen_low_mem(self):
        config = calculate_bee_slots(total_mem_gb=4, queen_model="2b")
        assert config["queen_model"] == "2b"

    def test_config_has_all_fields(self):
        config = calculate_bee_slots(total_mem_gb=16, queen_model="9b")
        assert "mode" in config
        assert "queen_model" in config
        assert "bee_slots" in config
        assert "queen_mem" in config
        assert "bee_mem" in config
        assert "total_mem" in config


class TestLiteMode:
    """Lite mode for low-memory systems."""

    def test_lite_uses_2b(self):
        config = calculate_bee_slots(total_mem_gb=3, queen_model="9b")
        assert config["mode"] == "lite"
        assert config["queen_model"] == "2b"

    def test_lite_minimal_bees(self):
        config = calculate_bee_slots(total_mem_gb=2, queen_model="9b")
        assert config["bee_slots"] == MIN_BEES
