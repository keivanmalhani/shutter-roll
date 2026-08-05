"""Frame discovery, ordering, and the per-frame tag plan."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from shutter_roll.roll import Roll

DEFAULT_EXTS = ("jpg", "jpeg", "tif", "tiff", "png", "dng")

# One minute per frame keeps intra-roll order without spilling a long
# roll into the next day, and reads sanely in a DAM timeline.
FRAME_STEP = timedelta(minutes=1)

EXIF_DATE_FMT = "%Y:%m:%d %H:%M:%S"


class FrameError(Exception):
    """No usable frames in the folder."""


@dataclass(frozen=True)
class FramePlan:
    """Everything apply/plan needs to know about one scan."""

    path: Path
    frame: int
    total: int
    tags: dict  # exiftool tag name -> value


def discover_frames(folder: Path, exts: tuple[str, ...] = DEFAULT_EXTS) -> list[Path]:
    """Scans in the folder, case-insensitive name sort, skip rules on.

    Skips dotfiles, AppleDouble sidecars, underscore-prefixed files, any
    existing contact sheet, and non-frame files like roll.txt. Non
    recursive on purpose: one folder is one roll.
    """
    wanted = {"." + e.lower().lstrip(".") for e in exts}
    frames = []
    for path in folder.iterdir():
        if not path.is_file():
            continue
        name = path.name
        if name.startswith(".") or name.startswith("._") or name.startswith("_"):
            continue
        if name.lower().endswith("-contact.jpg"):
            continue
        if path.suffix.lower() not in wanted:
            continue
        frames.append(path)
    frames.sort(key=lambda p: p.name.lower())
    if not frames:
        raise FrameError(
            f"No scans found in {folder} (looked for {', '.join(sorted(wanted))})."
        )
    return frames


def tags_for(
    roll: Roll,
    frame: int,
    total: int,
    *,
    title: bool = False,
) -> dict:
    """The exiftool tag dictionary for one frame.

    The mapping is the README's contract:
    camera -> Make/Model, lens -> LensModel, iso -> ISO, shot date plus
    one minute per frame -> DateTimeOriginal and CreateDate, stock and
    roll id -> keywords plus a human-readable UserComment.
    """
    tags: dict = {}

    make_model = roll.make_model
    if make_model:
        tags["Make"], tags["Model"] = make_model
    if roll.lens:
        tags["LensModel"] = roll.lens
    if roll.iso is not None:
        tags["ISO"] = str(roll.iso)

    if roll.shot is not None:
        stamp: datetime = roll.shot + FRAME_STEP * (frame - 1)
        rendered = stamp.strftime(EXIF_DATE_FMT)
        tags["DateTimeOriginal"] = rendered
        tags["CreateDate"] = rendered

    keywords = ["film", roll.stock]
    if roll.roll_id:
        keywords.append(roll.roll_id)
    tags["Keywords"] = keywords

    comment = f"Film: {roll.stock}"
    if roll.roll_id:
        comment += f", roll {roll.roll_id}"
    comment += f", frame {frame}/{total}"
    if roll.notes:
        comment += f". {roll.notes}"
    tags["UserComment"] = comment

    if title and roll.roll_id:
        tags["Title"] = f"{roll.roll_id} frame {frame}"

    return tags


def plan_frames(
    roll: Roll,
    paths: list[Path],
    *,
    start_frame: int = 1,
    title: bool = False,
) -> list[FramePlan]:
    total = start_frame + len(paths) - 1
    plans = []
    for offset, path in enumerate(paths):
        frame = start_frame + offset
        plans.append(
            FramePlan(
                path=path,
                frame=frame,
                total=total,
                tags=tags_for(roll, frame, total, title=title),
            )
        )
    return plans
