"""TTF-to-bitmap font rendering engine for scalable peyote patterns."""

import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Curated font catalog — friendly name → candidate TTF paths.
# Each entry lists fallbacks in order; the first existing file is used.
# Regular weight preferred — bold produces strokes that are too thick at
# small bead counts; the stroke-width normalisation pass ensures visibility.
FONT_CATALOG: dict[str, list[str]] = {
    'Serif': [
        '/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf',
        '/usr/share/fonts/dejavu-serif-fonts/DejaVuSerif.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf',
        '/usr/share/fonts/liberation-serif/LiberationSerif-Regular.ttf',
    ],
    'Serif Bold': [
        '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf',
        '/usr/share/fonts/dejavu-serif-fonts/DejaVuSerif-Bold.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf',
        '/usr/share/fonts/liberation-serif/LiberationSerif-Bold.ttf',
    ],
    'Sans': [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
        '/usr/share/fonts/liberation-sans/LiberationSans-Regular.ttf',
    ],
    'Sans Bold': [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
        '/usr/share/fonts/liberation-sans/LiberationSans-Bold.ttf',
    ],
    'Mono': [
        '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',
        '/usr/share/fonts/dejavu-sans-mono-fonts/DejaVuSansMono.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf',
        '/usr/share/fonts/liberation-mono/LiberationMono-Regular.ttf',
    ],
    'Ubuntu': [
        '/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf',
    ],
}

DEFAULT_FONT_NAME = 'Serif'


def available_fonts() -> list[str]:
    """Return catalog entries whose first existing candidate resolves."""
    return [name for name, paths in FONT_CATALOG.items()
            if any(os.path.exists(p) for p in paths)]


def resolve_font(name: str | None) -> str:
    """Look up a font by friendly catalog name, returning the first existing path.

    Falls back to any available catalog font if *name* is None or missing.
    """
    if name and name in FONT_CATALOG:
        for path in FONT_CATALOG[name]:
            if os.path.exists(path):
                return path
    # Fallback: first available in catalog order
    for paths in FONT_CATALOG.values():
        for path in paths:
            if os.path.exists(path):
                return path
    raise FileNotFoundError(
        "No suitable TTF font found. Install dejavu or liberation fonts, "
        "or specify a font path with --font-path."
    )


def find_default_font() -> str:
    """Find a suitable font on the system (first available in the catalog)."""
    return resolve_font(DEFAULT_FONT_NAME)


def _ensure_min_stroke_width(grid: list[list[int]], min_width: int = 2) -> list[list[int]]:
    """Widen isolated horizontal pixels so every stroke is at least *min_width* beads.

    In peyote stitch each row only shows half the columns, so single-pixel
    strokes can vanish.  This pass extends any horizontally-isolated ON pixel
    to the right (or left at the edge) to guarantee visibility.
    """
    h = len(grid)
    w = len(grid[0]) if grid else 0
    result = [row[:] for row in grid]
    for y in range(h):
        for x in range(w):
            if grid[y][x] != 1:
                continue
            has_left = x > 0 and grid[y][x - 1] == 1
            has_right = x < w - 1 and grid[y][x + 1] == 1
            if not has_left and not has_right:
                if x < w - 1:
                    result[y][x + 1] = 1
                elif x > 0:
                    result[y][x - 1] = 1
    return result


def render_char_bitmap(
    char: str,
    columns: int,
    char_height: int,
    font_path: str | None = None,
    threshold: int = 100,
    dilate: bool = False,
) -> list[list[int]]:
    """Render a single character to a binary bitmap grid.

    Args:
        char: Single character to render.
        columns: Target width in bead columns.
        char_height: Target height in bead rows.
        font_path: Path to TTF font file. Auto-detected if None.
        threshold: Binarization threshold (0-255).
        dilate: Apply morphological dilation for thicker strokes.

    Returns:
        char_height x columns grid of 0/1 values.
    """
    if font_path is None:
        font_path = find_default_font()

    # Render at ~20x target size for quality
    render_size = max(columns, char_height) * 20
    font_size = int(render_size * 0.85)

    try:
        font = ImageFont.truetype(font_path, font_size)
    except (IOError, OSError):
        raise FileNotFoundError(f"Cannot load font: {font_path}")

    # Draw character on grayscale canvas
    canvas_size = render_size * 3
    img = Image.new('L', (canvas_size, canvas_size), color=0)
    draw = ImageDraw.Draw(img)
    draw.text((render_size, render_size // 2), char, font=font, fill=255)

    # Crop to tight bounding box
    bbox = img.getbbox()
    if bbox is None:
        # Blank character (e.g., space)
        return [[0] * columns for _ in range(char_height)]
    img = img.crop(bbox)

    # Resize to target dimensions
    img = img.resize((columns, char_height), Image.Resampling.LANCZOS)

    # Optional dilation for thicker strokes
    if dilate:
        img = img.filter(ImageFilter.MaxFilter(size=3))

    # Threshold to binary
    grid = []
    for y in range(char_height):
        row = []
        for x in range(columns):
            pixel = img.getpixel((x, y))
            row.append(1 if pixel > threshold else 0)
        grid.append(row)

    # Ensure every stroke is at least 2 beads wide (critical for peyote
    # stitch where each row only shows alternate columns).
    grid = _ensure_min_stroke_width(grid)

    return grid


def _measure_char_widths(text: str, font_path: str, glyph_height: int,
                         avg_width: int) -> list[int]:
    """Measure the proportional width of each character.

    Renders each character at high resolution, measures its bounding-box
    width relative to the others, then allocates bead-widths proportionally
    so wider letters like M/W get more beads than narrow ones like I.
    """
    scale = 20
    font_size = int(glyph_height * scale * 0.85)
    font = ImageFont.truetype(font_path, font_size)

    raw_widths: list[int] = []
    for ch in text:
        canvas = glyph_height * scale * 3
        img = Image.new('L', (canvas, canvas), color=0)
        draw = ImageDraw.Draw(img)
        draw.text((canvas // 3, canvas // 6), ch, font=font, fill=255)
        bbox = img.getbbox()
        raw_widths.append((bbox[2] - bbox[0]) if bbox else 1)

    # Blend proportional widths toward the average so narrow letters (I)
    # don't vanish and wide letters (M) don't dominate.
    blend = 1.0  # 0 = monospace, 1 = fully proportional
    mean_raw = sum(raw_widths) / len(raw_widths) if raw_widths else 1
    widths = []
    for w in raw_widths:
        proportional = w / mean_raw * avg_width
        blended = avg_width * (1 - blend) + proportional * blend
        widths.append(max(4, round(blended)))
    return widths


def render_text_rows(
    text: str,
    columns: int,
    char_height: int | None = None,
    char_spacing: int = 3,
    font_path: str | None = None,
    rotate: bool = True,
    dilate: bool = False,
) -> list[list[int]]:
    """Render text to pixel rows using TTF rendering.

    Characters are rendered proportionally — wider letters (M, W) get more
    bead-rows than narrow ones (I, L).

    Args:
        text: Text to render.
        columns: Bead column count of the piece.
        char_height: Average rows per character. Auto-calculated if None.
        char_spacing: Blank rows between characters.
        font_path: Path to TTF font. Auto-detected if None.
        rotate: If True, render upright then rotate 90 CW (for sideways reading).
        dilate: Apply morphological dilation.

    Returns:
        List of rows, each `columns` wide.
    """
    text = text.upper()

    if rotate:
        glyph_height = columns
        if char_height is None:
            char_height = max(5, int(columns * 0.9))
        avg_width = char_height
    else:
        glyph_height = None  # set per-char below
        if char_height is None:
            char_height = max(7, int(columns * 1.4))
        avg_width = columns  # unused for non-rotate

    if font_path is None:
        font_path = find_default_font()

    if rotate:
        char_widths = _measure_char_widths(text, font_path, glyph_height, avg_width)
    else:
        char_widths = [columns] * len(text)

    rows: list[list[int]] = []
    for i, ch in enumerate(text):
        if i > 0:
            for _ in range(char_spacing):
                rows.append([0] * columns)

        if rotate:
            gw = char_widths[i]
            gh = columns
        else:
            gw = columns
            gh = char_height

        glyph = render_char_bitmap(ch, gw, gh,
                                   font_path=font_path, dilate=dilate)

        if rotate:
            h = len(glyph)
            w = len(glyph[0]) if glyph else 0
            rotated = []
            for c in range(w):
                row = []
                for r in range(h - 1, -1, -1):
                    row.append(glyph[r][c])
                rotated.append(row)
            rows.extend(rotated)
        else:
            rows.extend(glyph)

    return rows
