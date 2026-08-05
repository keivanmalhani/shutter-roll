"""roll.txt parsing, overrides, dates, frame planning."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from shutter_roll.frames import discover_frames, plan_frames, tags_for
from shutter_roll.roll import (
    Roll,
    RollError,
    load_roll,
    parse_shot_date,
    write_template,
)
from tests.conftest import write_scan


class TestRollFile:
    def test_load_full_roll(self, roll_folder):
        roll = load_roll(roll_folder)
        assert roll.stock == "Portra 400"
        assert roll.make_model == ("Canon", "Canonet QL17 GIII")
        assert roll.iso == 400
        assert roll.shot == datetime(2026, 7, 15, 12, 0, 0)
        assert roll.roll_id == "R012"

    def test_flags_override_file(self, roll_folder):
        roll = load_roll(roll_folder, {"stock": "HP5 Plus", "iso": "1600"})
        assert roll.stock == "HP5 Plus"
        assert roll.iso == 1600
        assert roll.camera == "Canon Canonet QL17 GIII"  # file value kept

    def test_missing_stock_is_actionable(self, tmp_path):
        with pytest.raises(RollError) as err:
            load_roll(tmp_path)
        assert "--stock" in str(err.value)

    def test_bad_iso_rejected(self, tmp_path):
        with pytest.raises(RollError):
            load_roll(tmp_path, {"stock": "Gold 200", "iso": "box speed"})

    def test_unknown_keys_survive_as_extras(self, tmp_path):
        (tmp_path / "roll.txt").write_text("stock: Gold 200\npush: +1\n")
        roll = load_roll(tmp_path)
        assert roll.extras == {"push": "+1"}

    def test_single_word_camera(self, tmp_path):
        roll = load_roll(tmp_path, {"stock": "X", "camera": "Holga"})
        assert roll.make_model == ("Holga", "Holga")

    def test_template_writes_once(self, tmp_path):
        target = write_template(tmp_path)
        assert target.read_text().startswith("#")
        with pytest.raises(RollError):
            write_template(tmp_path)


class TestShotDate:
    def test_full_date(self):
        assert parse_shot_date("2026-07-15") == datetime(2026, 7, 15, 12, 0, 0)

    def test_month_only_uses_first(self):
        assert parse_shot_date("2026-07") == datetime(2026, 7, 1, 12, 0, 0)

    def test_garbage_rejected(self):
        with pytest.raises(RollError):
            parse_shot_date("last july")

    def test_impossible_date_rejected(self):
        with pytest.raises(RollError):
            parse_shot_date("2026-02-30")


class TestDiscovery:
    def test_ordered_and_filtered(self, roll_folder):
        write_scan(roll_folder / "scan_000.jpg")
        (roll_folder / "._scan_001.jpg").write_bytes(b"\0" * 100)
        (roll_folder / "_reject.jpg").write_bytes(b"\0" * 100)
        (roll_folder / "notes.txt").write_text("x")
        write_scan(roll_folder / "R012-contact.jpg")

        frames = discover_frames(roll_folder)
        assert [p.name for p in frames] == [
            "scan_000.jpg", "scan_001.jpg", "scan_002.jpg",
            "scan_003.jpg", "scan_004.jpg", "scan_005.jpg",
        ]

    def test_empty_folder_raises(self, tmp_path):
        from shutter_roll.frames import FrameError

        with pytest.raises(FrameError):
            discover_frames(tmp_path)

    def test_ext_filter(self, tmp_path):
        write_scan(tmp_path / "a.tif")
        write_scan(tmp_path / "b.jpg")
        frames = discover_frames(tmp_path, ("tif",))
        assert [p.name for p in frames] == ["a.tif"]


class TestTagPlan:
    def _roll(self, **kw):
        base = dict(
            stock="Portra 400",
            camera="Canon Canonet QL17 GIII",
            iso=400,
            shot=datetime(2026, 7, 15, 12, 0, 0),
            lens="40mm f/1.7",
            roll_id="R012",
        )
        base.update(kw)
        return Roll(**base)

    def test_full_mapping(self):
        tags = tags_for(self._roll(), 3, 36)
        assert tags["Make"] == "Canon"
        assert tags["Model"] == "Canonet QL17 GIII"
        assert tags["LensModel"] == "40mm f/1.7"
        assert tags["ISO"] == "400"
        assert tags["DateTimeOriginal"] == "2026:07:15 12:02:00"  # +1 min per frame
        assert tags["CreateDate"] == tags["DateTimeOriginal"]
        assert tags["Keywords"] == ["film", "Portra 400", "R012"]
        assert tags["UserComment"] == "Film: Portra 400, roll R012, frame 3/36"

    def test_dates_preserve_frame_order(self):
        roll = self._roll()
        stamps = [tags_for(roll, n, 5)["DateTimeOriginal"] for n in (1, 2, 5)]
        assert stamps == sorted(stamps)
        assert stamps[0] == "2026:07:15 12:00:00"

    def test_minimal_roll_writes_minimal_tags(self):
        tags = tags_for(Roll(stock="Gold 200"), 1, 1)
        assert "Make" not in tags and "ISO" not in tags
        assert "DateTimeOriginal" not in tags
        assert tags["Keywords"] == ["film", "Gold 200"]
        assert tags["UserComment"] == "Film: Gold 200, frame 1/1"

    def test_title_opt_in(self):
        assert "Title" not in tags_for(self._roll(), 1, 1)
        assert tags_for(self._roll(), 14, 36, title=True)["Title"] == "R012 frame 14"

    def test_start_frame_offset(self, roll_folder):
        roll = load_roll(roll_folder)
        frames = discover_frames(roll_folder)
        plans = plan_frames(roll, frames, start_frame=20)
        assert plans[0].frame == 20
        assert plans[-1].frame == 24
        assert plans[-1].total == 24
        assert "frame 20/24" in plans[0].tags["UserComment"]
