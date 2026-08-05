"""The roll description: roll.txt parsing, flag overlay, validation.

A roll is one physical roll of film scanned into one folder. The
description lives in roll.txt beside the scans (plain "key: value"
lines, # comments), and every key can be overridden by a CLI flag.
Only the film stock is required; everything else degrades gracefully.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path

ROLL_FILENAME = "roll.txt"

KNOWN_KEYS = ("stock", "camera", "iso", "shot", "lens", "roll", "notes")

TEMPLATE = """\
# shutter-roll description for this folder of scans.
# Only "stock" is required. Delete any line you do not want written.

stock: Portra 400
camera: Canon Canonet QL17 GIII
iso: 400
# shot supports 2026-07-15 or just 2026-07 (uses the 1st)
shot: 2026-07-15
lens: 40mm f/1.7
roll: R001
notes:
"""


class RollError(Exception):
    """Bad or missing roll description."""


@dataclass(frozen=True)
class Roll:
    stock: str
    camera: str | None = None
    iso: int | None = None
    shot: datetime | None = None
    lens: str | None = None
    roll_id: str | None = None
    notes: str | None = None
    extras: dict = field(default_factory=dict)

    @property
    def make_model(self) -> tuple[str, str] | None:
        """Split 'Canon Canonet QL17 GIII' into Make 'Canon' and the rest
        as Model. A single-word camera becomes both."""
        if not self.camera:
            return None
        parts = self.camera.split(None, 1)
        if len(parts) == 1:
            return parts[0], parts[0]
        return parts[0], parts[1]


def parse_shot_date(raw: str) -> datetime:
    """Accept 2026-07-15 or 2026-07 (day defaults to the 1st).

    Time of day is fixed at 12:00: rolls sort by date without landing at
    midnight boundaries, and per-frame minutes are added downstream.
    """
    raw = raw.strip()
    match = re.fullmatch(r"(\d{4})-(\d{1,2})(?:-(\d{1,2}))?", raw)
    if not match:
        raise RollError(
            f"Cannot read shot date '{raw}'. Use 2026-07-15 or 2026-07."
        )
    year, month = int(match.group(1)), int(match.group(2))
    day = int(match.group(3)) if match.group(3) else 1
    try:
        return datetime(year, month, day, 12, 0, 0)
    except ValueError as exc:
        raise RollError(f"Impossible shot date '{raw}': {exc}") from exc


def parse_roll_text(text: str) -> dict:
    """roll.txt lines into a raw dict. Unknown keys survive as extras."""
    values: dict = {}
    for line_number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            raise RollError(
                f"roll.txt line {line_number} is not 'key: value': {stripped!r}"
            )
        key, _, value = stripped.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if value:
            values[key] = value
    return values


def load_roll(
    folder: Path,
    overrides: dict | None = None,
) -> Roll:
    """Build the Roll from roll.txt plus CLI overrides (overrides win).

    Raises:
        RollError: no stock anywhere, or an unparseable value.
    """
    values: dict = {}
    roll_path = folder / ROLL_FILENAME
    if roll_path.is_file():
        values.update(parse_roll_text(roll_path.read_text(encoding="utf-8")))
    for key, value in (overrides or {}).items():
        if value is not None:
            values[str(key).lower()] = value

    stock = values.pop("stock", None)
    if not stock:
        raise RollError(
            f"No film stock. Add 'stock: ...' to {roll_path.name} (run "
            f"'shutter-roll init' for a template) or pass --stock."
        )

    iso: int | None = None
    if "iso" in values:
        raw_iso = str(values.pop("iso"))
        try:
            iso = int(raw_iso)
        except ValueError as exc:
            raise RollError(f"ISO must be a number, got '{raw_iso}'.") from exc
        if iso <= 0:
            raise RollError(f"ISO must be positive, got {iso}.")

    shot: datetime | None = None
    if "shot" in values:
        shot = parse_shot_date(str(values.pop("shot")))

    known = {
        "camera": values.pop("camera", None),
        "lens": values.pop("lens", None),
        "roll_id": values.pop("roll", None),
        "notes": values.pop("notes", None),
    }
    return Roll(stock=str(stock), iso=iso, shot=shot, extras=values, **known)


def write_template(folder: Path) -> Path:
    """Write the commented roll.txt template. Refuses to clobber."""
    target = folder / ROLL_FILENAME
    if target.exists():
        raise RollError(f"{target} already exists; not overwriting it.")
    target.write_text(TEMPLATE, encoding="utf-8")
    return target


def with_overrides(roll: Roll, **kw) -> Roll:
    return replace(roll, **kw)
