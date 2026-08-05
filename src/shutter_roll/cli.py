"""shutter-roll CLI: init, plan, apply, sheet.

Exit codes: 0 success, 1 error. plan is the default safety posture:
apply --dry-run and plan are the same code path, and apply without
--overwrite keeps exiftool's _original backups beside the scans.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from shutter_roll import __version__
from shutter_roll.frames import DEFAULT_EXTS, FrameError, discover_frames, plan_frames
from shutter_roll.inject import InjectError, apply_plan
from shutter_roll.roll import ROLL_FILENAME, RollError, load_roll, write_template
from shutter_roll.sheet import render_sheet, sheet_name


def _resolve_folder(raw: str) -> Path:
    folder = Path(raw).expanduser()
    try:
        resolved = folder.resolve(strict=True)
    except FileNotFoundError:
        raise RollError(f"Folder does not exist: {raw}")
    if not resolved.is_dir():
        raise RollError(f"Not a folder: {raw}")
    return resolved


def _overrides(args: argparse.Namespace) -> dict:
    return {
        "stock": args.stock,
        "camera": args.camera,
        "iso": args.iso,
        "shot": args.shot,
        "lens": args.lens,
        "roll": args.roll,
        "notes": args.notes,
    }


def _print_plan(plans, folder: Path) -> None:
    print(f"{len(plans)} frame(s) in {folder}")
    first = plans[0]
    print("\ntags for every frame:")
    for tag, value in first.tags.items():
        if tag in ("DateTimeOriginal", "CreateDate", "UserComment", "Title"):
            continue
        rendered = ", ".join(value) if isinstance(value, list) else value
        print(f"  {tag:<16} {rendered}")
    print("\nper frame:")
    show = plans if len(plans) <= 8 else plans[:4] + plans[-2:]
    for plan in show:
        stamp = plan.tags.get("DateTimeOriginal", "-")
        print(f"  {plan.frame:02d}  {plan.path.name:<34} {stamp}")
        if len(plans) > 8 and plan is show[3]:
            print(f"  ... {len(plans) - 6} more ...")


def _cmd_init(args: argparse.Namespace) -> int:
    folder = _resolve_folder(args.folder)
    target = write_template(folder)
    print(f"wrote {target}. Edit it, then run: shutter-roll plan {folder}")
    return 0


def _cmd_plan(args: argparse.Namespace, *, apply: bool = False) -> int:
    folder = _resolve_folder(args.folder)
    roll = load_roll(folder, _overrides(args))
    paths = discover_frames(folder, tuple(args.ext.split(",")))
    plans = plan_frames(
        roll, paths, start_frame=args.start_frame, title=args.title
    )

    if not apply or args.dry_run:
        _print_plan(plans, folder)
        if not apply:
            print(f"\ndry plan only. Apply it with: shutter-roll apply {folder}")
        else:
            print("\n--dry-run: nothing written.")
        return 0

    written = apply_plan(plans, overwrite=args.overwrite)
    backups = "" if args.overwrite else " (_original backups kept beside them)"
    print(f"wrote metadata into {written} file(s){backups}")
    return 0


def _cmd_apply(args: argparse.Namespace) -> int:
    return _cmd_plan(args, apply=True)


def _cmd_sheet(args: argparse.Namespace) -> int:
    folder = _resolve_folder(args.folder)
    roll = load_roll(folder, _overrides(args))
    paths = discover_frames(folder, tuple(args.ext.split(",")))
    out = folder / sheet_name(roll)
    render_sheet(roll, paths, out, start_frame=args.start_frame)
    print(f"contact sheet: {out}")
    return 0


def _add_roll_flags(sp: argparse.ArgumentParser) -> None:
    sp.add_argument("folder", help="folder holding one roll of scans")
    sp.add_argument("--stock", default=None, help="film stock, e.g. 'Portra 400'")
    sp.add_argument("--camera", default=None, help="e.g. 'Canon Canonet QL17 GIII'")
    sp.add_argument("--iso", default=None, help="box or shot ISO")
    sp.add_argument("--shot", default=None, help="shoot date, 2026-07-15 or 2026-07")
    sp.add_argument("--lens", default=None)
    sp.add_argument("--roll", default=None, help="roll id, e.g. R012")
    sp.add_argument("--notes", default=None)
    sp.add_argument("--start-frame", type=int, default=1)
    sp.add_argument("--title", action="store_true",
                    help="also write an XMP title like 'R012 frame 14'")
    sp.add_argument("--ext", default=",".join(DEFAULT_EXTS),
                    help="comma-separated scan extensions")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shutter-roll",
        description=(
            "Inject film stock, camera, ISO, roll and frame metadata into "
            "scanned negatives, and render contact sheets. Local only."
        ),
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help=f"write a {ROLL_FILENAME} template")
    init.add_argument("folder")
    init.set_defaults(func=_cmd_init)

    plan = sub.add_parser("plan", help="show the tag plan, write nothing")
    _add_roll_flags(plan)
    plan.set_defaults(func=_cmd_plan)

    apply_cmd = sub.add_parser("apply", help="inject metadata via exiftool")
    _add_roll_flags(apply_cmd)
    apply_cmd.add_argument("--dry-run", action="store_true")
    apply_cmd.add_argument(
        "--overwrite", action="store_true",
        help="skip exiftool's _original backups",
    )
    apply_cmd.set_defaults(func=_cmd_apply)

    sheet = sub.add_parser("sheet", help="render the roll's contact sheet JPEG")
    _add_roll_flags(sheet)
    sheet.set_defaults(func=_cmd_sheet)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "dry_run"):
        args.dry_run = False
    try:
        return args.func(args)
    except (RollError, FrameError, InjectError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
