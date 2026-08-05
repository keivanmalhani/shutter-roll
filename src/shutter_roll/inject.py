"""Metadata writes via exiftool, the family's battle-tested writer.

Never hand-roll metadata serialization: exiftool writes JPEG, TIFF,
PNG, and DNG natively and keeps `_original` backups beside the files
unless the caller explicitly opts out with overwrite=True.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from shutter_roll.frames import FramePlan

EXIFTOOL_TIMEOUT_S = 120


class InjectError(Exception):
    """exiftool missing or a write failed."""


def exiftool_available() -> bool:
    return shutil.which("exiftool") is not None


def require_exiftool() -> None:
    if not exiftool_available():
        raise InjectError(
            "exiftool not found. Install it first: 'brew install exiftool' "
            "on macOS, 'sudo apt install libimage-exiftool-perl' on Debian."
        )


def _args_for(plan: FramePlan, overwrite: bool) -> list[str]:
    args = ["exiftool", "-charset", "utf8"]
    if overwrite:
        args.append("-overwrite_original")
    for tag, value in plan.tags.items():
        if tag == "Keywords":
            # One replace-assignment with an explicit separator. The
            # clear-then-append idiom (-Keywords= then -Keywords+=...)
            # stacks duplicates on re-runs: exiftool applies += against
            # the ORIGINAL list, so the clear never wins. Caught by the
            # rerun test with a real exiftool round trip.
            args += ["-sep", ";;", "-Keywords=" + ";;".join(value)]
        else:
            args.append(f"-{tag}={value}")
    args.append(str(plan.path))
    return args


def apply_plan(plans: list[FramePlan], *, overwrite: bool = False) -> int:
    """Write every frame's tags. Returns the number of files written.

    Raises:
        InjectError: exiftool missing, or any file failed to write.
    """
    require_exiftool()
    written = 0
    failures: list[str] = []
    for plan in plans:
        try:
            proc = subprocess.run(
                _args_for(plan, overwrite),
                capture_output=True,
                text=True,
                timeout=EXIFTOOL_TIMEOUT_S,
            )
        except subprocess.TimeoutExpired:
            failures.append(f"{plan.path.name}: exiftool timed out")
            continue
        if proc.returncode != 0 or "1 image files updated" not in proc.stdout:
            detail = (proc.stderr or proc.stdout).strip().splitlines()
            failures.append(
                f"{plan.path.name}: {detail[-1] if detail else 'unknown error'}"
            )
            continue
        written += 1
    if failures:
        raise InjectError(
            f"{written} written, {len(failures)} failed:\n  " + "\n  ".join(failures)
        )
    return written


def read_tags(path: Path, tags: list[str]) -> dict:
    """Read tags back with exiftool. Test and verification helper."""
    require_exiftool()
    args = ["exiftool", "-s", "-s", "-s", "-charset", "utf8"]
    args += [f"-{tag}" for tag in tags]
    args.append(str(path))
    proc = subprocess.run(args, capture_output=True, text=True, timeout=EXIFTOOL_TIMEOUT_S)
    values: dict = {}
    lines = [line for line in proc.stdout.splitlines()]
    # -s -s -s prints bare values in argument order for present tags only;
    # ask one tag at a time instead for unambiguous mapping.
    if len(tags) == 1:
        return {tags[0]: lines[0] if lines else None}
    for tag in tags:
        values[tag] = read_tags(path, [tag])[tag]
    return values
