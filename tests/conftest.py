"""Fixtures: Pillow-generated scans, no committed binaries."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

exiftool_missing = shutil.which("exiftool") is None
requires_exiftool = pytest.mark.skipif(
    exiftool_missing, reason="exiftool not installed in this environment"
)


def write_scan(path: Path, *, hue: int = 0, size: tuple[int, int] = (240, 160)) -> Path:
    """A film-scan-looking little frame with a distinct color block."""
    image = Image.new("RGB", size, (24 + hue % 60, 22, 20))
    draw = ImageDraw.Draw(image)
    draw.rectangle(
        [20 + hue % 40, 30, 140 + hue % 40, 130],
        fill=((90 + hue * 37) % 255, (140 + hue * 11) % 255, 90),
    )
    fmt = "TIFF" if path.suffix.lower() in (".tif", ".tiff") else \
        "PNG" if path.suffix.lower() == ".png" else "JPEG"
    image.save(path, format=fmt)
    return path


@pytest.fixture
def roll_folder(tmp_path: Path) -> Path:
    """Five ordered scans plus a roll.txt."""
    folder = tmp_path / "R012"
    folder.mkdir()
    for i in range(1, 6):
        write_scan(folder / f"scan_{i:03d}.jpg", hue=i * 17)
    (folder / "roll.txt").write_text(
        "stock: Portra 400\n"
        "camera: Canon Canonet QL17 GIII\n"
        "iso: 400\n"
        "shot: 2026-07-15\n"
        "lens: 40mm f/1.7\n"
        "roll: R012\n",
        encoding="utf-8",
    )
    return folder
