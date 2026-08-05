"""Real exiftool round trips, backups, dry-run, sheet, CLI wiring."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from shutter_roll.cli import main
from shutter_roll.frames import discover_frames, plan_frames
from shutter_roll.inject import apply_plan, read_tags
from shutter_roll.roll import load_roll
from tests.conftest import requires_exiftool, write_scan


@requires_exiftool
class TestInject:
    def test_round_trip_all_tags(self, roll_folder):
        roll = load_roll(roll_folder)
        plans = plan_frames(roll, discover_frames(roll_folder))
        assert apply_plan(plans) == 5

        third = roll_folder / "scan_003.jpg"
        tags = read_tags(
            third,
            ["Make", "Model", "ISO", "DateTimeOriginal", "UserComment", "Keywords"],
        )
        assert tags["Make"] == "Canon"
        assert tags["Model"] == "Canonet QL17 GIII"
        assert tags["ISO"] == "400"
        assert tags["DateTimeOriginal"] == "2026:07:15 12:02:00"
        assert "roll R012, frame 3/5" in tags["UserComment"]
        assert "Portra 400" in tags["Keywords"]

    def test_backups_by_default_overwrite_optin(self, roll_folder):
        roll = load_roll(roll_folder)
        plans = plan_frames(roll, discover_frames(roll_folder))
        apply_plan(plans)
        backups = list(roll_folder.glob("*_original"))
        assert len(backups) == 5

        # a second run with overwrite leaves no NEW backups behind
        for backup in backups:
            backup.unlink()
        plans = plan_frames(roll, discover_frames(roll_folder))
        apply_plan(plans, overwrite=True)
        assert list(roll_folder.glob("*_original")) == []

    def test_rerun_does_not_stack_keywords(self, roll_folder):
        roll = load_roll(roll_folder)
        for _ in range(2):
            plans = plan_frames(roll, discover_frames(roll_folder))
            apply_plan(plans, overwrite=True)
        keywords = read_tags(roll_folder / "scan_001.jpg", ["Keywords"])["Keywords"]
        assert keywords.count("Portra 400") == 1

    def test_pixels_untouched(self, roll_folder):
        target = roll_folder / "scan_001.jpg"
        before = Image.open(target).convert("RGB").tobytes()
        roll = load_roll(roll_folder)
        apply_plan(plan_frames(roll, discover_frames(roll_folder)), overwrite=True)
        after = Image.open(target).convert("RGB").tobytes()
        assert before == after


class TestCli:
    def test_plan_writes_nothing(self, roll_folder, capsys):
        before = {p.name: p.stat().st_mtime_ns for p in roll_folder.iterdir()}
        assert main(["plan", str(roll_folder)]) == 0
        out = capsys.readouterr().out
        assert "5 frame(s)" in out
        assert "Portra 400" in out
        after = {p.name: p.stat().st_mtime_ns for p in roll_folder.iterdir()}
        assert before == after

    @requires_exiftool
    def test_apply_dry_run_writes_nothing(self, roll_folder, capsys):
        assert main(["apply", str(roll_folder), "--dry-run"]) == 0
        assert "nothing written" in capsys.readouterr().out
        assert list(roll_folder.glob("*_original")) == []

    @requires_exiftool
    def test_apply_end_to_end(self, roll_folder, capsys):
        assert main(["apply", str(roll_folder)]) == 0
        assert "wrote metadata into 5 file(s)" in capsys.readouterr().out

    def test_missing_stock_exit_1(self, tmp_path, capsys):
        write_scan(tmp_path / "a.jpg")
        assert main(["plan", str(tmp_path)]) == 1
        assert "stock" in capsys.readouterr().err

    def test_init_then_plan(self, tmp_path, capsys):
        write_scan(tmp_path / "a.jpg")
        assert main(["init", str(tmp_path)]) == 0
        assert main(["plan", str(tmp_path)]) == 0

    def test_missing_folder_exit_1(self, tmp_path, capsys):
        assert main(["plan", str(tmp_path / "nope")]) == 1
        assert "error:" in capsys.readouterr().err


class TestSheet:
    def test_sheet_renders(self, roll_folder, capsys):
        assert main(["sheet", str(roll_folder)]) == 0
        sheet = roll_folder / "R012-contact.jpg"
        assert sheet.exists()
        with Image.open(sheet) as img:
            assert img.width == 2000
            assert img.height > 300

    def test_sheet_excluded_from_rescan(self, roll_folder):
        main(["sheet", str(roll_folder)])
        frames = discover_frames(roll_folder)
        assert all(not p.name.endswith("-contact.jpg") for p in frames)
        assert len(frames) == 5
