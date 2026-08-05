"""Contact sheet: one dark JPEG grid per roll, Pillow only."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from shutter_roll.roll import Roll

SHEET_WIDTH = 2000
COLUMNS = 6
GUTTER = 14
HEADER_H = 96
LABEL_H = 26

BG = (16, 17, 20)
CELL_BG = (28, 30, 34)
TEXT = (222, 224, 228)
DIM = (140, 144, 152)


def _font(size: int) -> ImageFont.ImageFont:
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/System/Library/Fonts/Menlo.ttc",
    ):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def sheet_name(roll: Roll) -> str:
    return f"{roll.roll_id or 'roll'}-contact.jpg"


def render_sheet(
    roll: Roll,
    paths: list[Path],
    out_path: Path,
    *,
    start_frame: int = 1,
) -> Path:
    """Render the roll's contact sheet JPEG. Returns out_path."""
    cell_w = (SHEET_WIDTH - GUTTER * (COLUMNS + 1)) // COLUMNS
    thumb_h = round(cell_w * 2 / 3)
    cell_h = thumb_h + LABEL_H
    rows = (len(paths) + COLUMNS - 1) // COLUMNS
    height = HEADER_H + rows * (cell_h + GUTTER) + GUTTER

    image = Image.new("RGB", (SHEET_WIDTH, height), BG)
    draw = ImageDraw.Draw(image)

    title_font = _font(30)
    meta_font = _font(16)
    label_font = _font(15)

    title = roll.roll_id or "contact sheet"
    draw.text((GUTTER + 6, 18), title, font=title_font, fill=TEXT)
    meta_bits = [roll.stock]
    if roll.camera:
        meta_bits.append(roll.camera)
    if roll.iso is not None:
        meta_bits.append(f"ISO {roll.iso}")
    if roll.shot is not None:
        meta_bits.append(roll.shot.strftime("%Y-%m-%d"))
    meta_bits.append(f"{len(paths)} frames")
    draw.text(
        (GUTTER + 8, 60), "  |  ".join(meta_bits), font=meta_font, fill=DIM
    )

    for index, path in enumerate(paths):
        col = index % COLUMNS
        row = index // COLUMNS
        x = GUTTER + col * (cell_w + GUTTER)
        y = HEADER_H + row * (cell_h + GUTTER)

        draw.rectangle([x, y, x + cell_w, y + thumb_h], fill=CELL_BG)
        try:
            with Image.open(path) as source:
                thumb = ImageOps.exif_transpose(source).convert("RGB")
                thumb = ImageOps.fit(thumb, (cell_w, thumb_h))
                image.paste(thumb, (x, y))
        except OSError:
            draw.text(
                (x + 10, y + thumb_h // 2 - 8),
                "unreadable",
                font=label_font,
                fill=DIM,
            )

        frame_no = start_frame + index
        draw.text(
            (x + 2, y + thumb_h + 5),
            f"{frame_no:02d}  {path.name}"[:36],
            font=label_font,
            fill=DIM,
        )

    image.save(out_path, format="JPEG", quality=88)
    return out_path
