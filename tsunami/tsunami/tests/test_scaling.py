"""Tests for auto-scaling eddy slots based on memory."""

import pytest
from tsunami.scaling import calculate_bee_slots, MAX_BEES, MIN_BEES


class TestFullMode:
    """Full mode: 9B wave + 2B eddies + SD-Turbo."""

    def test_12gb_full(self):
        config = calculate_bee_slots(total_mem_gb=12, queen_model="9b")
        assert config["mode"] == "full"
        assert config["bee_slots"] >= 1
        assert config["image_gen"] is True

    def test_16gb_good_slots(self):
        config = calculate_bee_slots(total_mem_gb=16, queen_model="9b")
        assert config["mode"] == "full"
        assert config["bee_slots"] >= 4
        assert config["image_gen"] is True

    def test_32gb_27b(self):
        config = calculate_bee_slots(total_mem_gb=32, queen_model="27b")
        assert config["mode"] == "full"
        assert config["bee_slots"] >= 1
        assert config["image_gen"] is True

    def test_64gb_many_eddies(self):
        config = calculate_bee_slots(total_mem_gb=64, queen_model="27b")
        assert config["mode"] == "full"
        assert config["bee_slots"] >= 16

    def test_128gb_max_eddies(self):
        config = calculate_bee_slots(total_mem_gb=128, queen_model="27b")
        assert config["bee_slots"] == MAX_BEES

    def test_never_exceeds_max(self):
        config = calculate_bee_slots(total_mem_gb=1000, queen_model="9b")
        assert config["bee_slots"] <= MAX_BEES

    def test_more_memory_more_eddies(self):
        c12 = calculate_bee_slots(total_mem_gb=12, queen_model="9b")
        c24 = calculate_bee_slots(total_mem_gb=24, queen_model="9b")
        assert c24["bee_slots"] > c12["bee_slots"]


class TestLiteMode:
    """Lite mode: 2B only, no image gen."""

    def test_4gb_lite(self):
        config = calculate_bee_slots(total_mem_gb=4, queen_model="9b")
        assert config["mode"] == "lite"
        assert config["queen_model"] == "2b"
        assert config["image_gen"] is False
        assert config["bee_slots"] == MIN_BEES

    def test_3gb_lite(self):
        config = calculate_bee_slots(total_mem_gb=3, queen_model="9b")
        assert config["mode"] == "lite"
        assert config["image_gen"] is False

    def test_2gb_lite(self):
        config = calculate_bee_slots(total_mem_gb=2, queen_model="9b")
        assert config["mode"] == "lite"
        assert config["bee_slots"] >= MIN_BEES

    def test_never_below_min(self):
        config = calculate_bee_slots(total_mem_gb=1, queen_model="2b")
        assert config["bee_slots"] >= MIN_BEES


class TestConfigFields:
    """All configs have required fields."""

    def test_full_has_all_fields(self):
        config = calculate_bee_slots(total_mem_gb=16, queen_model="9b")
        for key in ("mode", "queen_model", "bee_slots", "queen_mem", "bee_mem", "image_gen", "total_mem"):
            assert key in config

    def test_lite_has_all_fields(self):
        config = calculate_bee_slots(total_mem_gb=4, queen_model="9b")
        for key in ("mode", "queen_model", "bee_slots", "queen_mem", "bee_mem", "image_gen", "total_mem"):
            assert key in config
