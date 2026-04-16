"""Composition engine — combine text and decorative patterns into a fabric grid."""

from dataclasses import dataclass

from .sizing import BeadConfig
from .grid import blank_grid, overlay
from .font import text_to_fabric
from .patterns import PATTERN_CATALOG


@dataclass
class Segment:
    """A vertical section of the pattern."""
    kind: str           # 'text', 'pattern', 'blank'
    rows: int | None = None   # row count (None = auto for text)
    text: str = ''
    pattern: str = ''
    pattern_kwargs: dict | None = None


def text_extent(fabric: list[list[int]], config: BeadConfig) -> tuple[int, int]:
    """Return (first_row, last_row) of the first/last non-zero rows."""
    first_row = 0
    last_row = config.rows - 1
    for ri, row in enumerate(fabric):
        if any(v != 0 for v in row):
            first_row = ri
            break
    for ri in range(config.rows - 1, -1, -1):
        if any(v != 0 for v in fabric[ri]):
            last_row = ri
            break
    return first_row, last_row


def default_border_rows(text: str, config: BeadConfig,
                        font_mode: str = 'auto', font_path: str | None = None,
                        rotate: bool = True, gap: int = 2) -> int:
    """Calculate border rows that fill from the edges to *gap* rows before text."""
    fabric = text_to_fabric(text or 'HELLO', config,
                            font_mode=font_mode, font_path=font_path, rotate=rotate)
    first_row, last_row = text_extent(fabric, config)
    top_space = first_row - gap
    bottom_space = config.rows - 1 - last_row - gap
    return max(1, min(top_space, bottom_space))


def compose_text_with_border(
    text: str,
    config: BeadConfig,
    border_pattern: str = 'chevron',
    border_rows: int | None = None,
    font_mode: str = 'auto',
    font_path: str | None = None,
    rotate: bool = True,
    border_color: int = 2,
    margin: int = 0,
    gap: int = 2,
    wrap_border: bool = False,
    **pattern_kwargs,
) -> list[list[int]]:
    """Text centered with decorative borders at the strip ends.

    Borders fill from the top/bottom edges inward, stopping *gap* rows before
    the rendered text. If ``border_rows`` is None (default) this is computed
    automatically; otherwise it overrides the auto-size.

    If ``wrap_border`` is True, the border pattern also paints the outer
    portion of the left and right margin columns between the top and bottom
    bands, producing a full frame around the text. The side strips leave a
    ``gap``-bead background buffer next to the text, mirroring the vertical
    gap above/below. Side-strip width is ``margin - gap`` (per side); if
    ``margin <= gap`` the side strips vanish. The frame is carved from one
    full-grid pattern so all four sides align seamlessly.

    Border ON-beads use *border_color* (default 2) so they can be coloured
    independently from the text foreground.
    """
    text_fabric = text_to_fabric(
        text, config, font_mode=font_mode, font_path=font_path, rotate=rotate,
        margin=margin,
    )

    # Auto-size borders to land *gap* rows before text, if not specified
    if border_rows is None:
        first_row, last_row = text_extent(text_fabric, config)
        top_space = first_row - gap
        bottom_space = config.rows - 1 - last_row - gap
        border_rows = max(1, min(top_space, bottom_space))

    pat_fn = PATTERN_CATALOG.get(border_pattern)
    if pat_fn is None:
        raise ValueError(f"Unknown pattern '{border_pattern}'. "
                         f"Available: {list(PATTERN_CATALOG.keys())}")

    result = [row[:] for row in text_fabric]

    if wrap_border:
        # Generate the pattern at full grid size so the frame lines up on all
        # four sides. Paint top/bottom bands + left/right margin strips.
        full_kwargs = {'columns': config.columns, 'rows': config.rows}
        full_kwargs.update(pattern_kwargs or {})
        full_pat = _shift_pattern_to_accents(pat_fn(**full_kwargs))

        def _stamp(ri: int, ci: int) -> None:
            v = full_pat[ri][ci]
            if v:
                result[ri][ci] = v

        # Top band
        for ri in range(min(border_rows, config.rows)):
            for ci in range(config.columns):
                _stamp(ri, ci)
        # Bottom band
        for ri in range(max(0, config.rows - border_rows), config.rows):
            for ci in range(config.columns):
                _stamp(ri, ci)
        # Side strips: outer (margin - gap) columns on each side so the
        # border stays `gap` beads clear of the text horizontally, matching
        # the vertical gap above/below. Vanishes when margin <= gap.
        # Clamp to half-width so the two sides never overlap or exceed
        # the grid (possible on narrow presets where margin >= columns/2).
        side_width = max(0, min(margin - gap, config.columns // 2))
        if side_width > 0:
            side_cols = list(range(side_width)) + \
                list(range(config.columns - side_width, config.columns))
            for ri in range(border_rows, config.rows - border_rows):
                for ci in side_cols:
                    _stamp(ri, ci)
    else:
        # Original behavior: separate border pattern sized to the band height,
        # painted at top and bottom only.
        kwargs = {'columns': config.columns, 'rows': border_rows}
        kwargs.update(pattern_kwargs or {})
        border_grid = _shift_pattern_to_accents(pat_fn(**kwargs))

        # Top border — starts at row 0
        for i, brow in enumerate(border_grid):
            if i >= config.rows:
                break
            result[i] = list(brow)

        # Bottom border — ends at last row
        for i, brow in enumerate(border_grid):
            ri = config.rows - border_rows + i
            if 0 <= ri < config.rows:
                result[ri] = list(brow)

    return result


def _shift_pattern_to_accents(grid: list[list[int]]) -> list[list[int]]:
    """Remap pattern ON-beads from slots {1,2} into accent slots {2,3}.

    Patterns emit color indices 1 (single-color) or 1 and 2 (two-color).
    Slot 1 is reserved for text, so we shift every non-zero index up by one
    to land on Accent 1 (slot 2) and Accent 2 (slot 3).
    """
    return [[0 if v == 0 else v + 1 for v in row] for row in grid]


def compose_text_with_background(
    text: str,
    config: BeadConfig,
    background_pattern: str = 'checker',
    font_mode: str = 'auto',
    font_path: str | None = None,
    rotate: bool = True,
    margin: int = 0,
    **pattern_kwargs,
) -> list[list[int]]:
    """Text overlaid on a decorative background.

    Pattern indices are shifted into the accent slots (2/3) so they stay
    independent from the text color (slot 1). Text pixels overwrite the
    background where they collide.
    """
    pat_fn = PATTERN_CATALOG.get(background_pattern)
    if pat_fn is None:
        raise ValueError(f"Unknown pattern '{background_pattern}'")

    kwargs = {'columns': config.columns, 'rows': config.rows}
    kwargs.update(pattern_kwargs or {})
    bg = _shift_pattern_to_accents(pat_fn(**kwargs))

    text_grid = text_to_fabric(
        text, config, font_mode=font_mode, font_path=font_path, rotate=rotate,
        margin=margin,
    )

    return overlay(bg, text_grid)


def compose_pattern_only(
    pattern_name: str,
    config: BeadConfig,
    **pattern_kwargs,
) -> list[list[int]]:
    """Full-grid decorative pattern with no text.

    Keeps native pattern indices (0/1 for single-color, 0/1/2 for two-color)
    so the paired palette should place accents on slots 1 and 2.
    """
    pat_fn = PATTERN_CATALOG.get(pattern_name)
    if pat_fn is None:
        raise ValueError(f"Unknown pattern '{pattern_name}'")

    kwargs = {'columns': config.columns, 'rows': config.rows}
    kwargs.update(pattern_kwargs or {})
    return pat_fn(**kwargs)


def compose_segmented(
    segments: list[Segment],
    config: BeadConfig,
    font_mode: str = 'auto',
    font_path: str | None = None,
    rotate: bool = True,
) -> list[list[int]]:
    """Stack segments vertically: pattern, text, pattern, etc."""
    all_rows: list[list[int]] = []

    for seg in segments:
        if seg.kind == 'blank':
            seg_rows = seg.rows or 4
            for _ in range(seg_rows):
                all_rows.append([0] * config.columns)

        elif seg.kind == 'pattern':
            pat_fn = PATTERN_CATALOG.get(seg.pattern)
            if pat_fn is None:
                raise ValueError(f"Unknown pattern '{seg.pattern}'")
            seg_rows = seg.rows or 10
            kwargs = {'columns': config.columns, 'rows': seg_rows}
            if seg.pattern_kwargs:
                kwargs.update(seg.pattern_kwargs)
            grid = pat_fn(**kwargs)
            all_rows.extend(grid)

        elif seg.kind == 'text':
            # Render text into a temporary config sized to fit
            from .font import text_to_fabric as _ttf
            if seg.rows:
                temp_rows = seg.rows
            else:
                # Auto-calculate: each char is ~0.7*columns wide (after
                # rotation) + 3 spacing rows between chars.
                n_chars = len(seg.text)
                char_w = max(5, int(config.columns * 0.9))
                char_spacing = 3
                rows_per_char = char_w + char_spacing
                temp_rows = n_chars * rows_per_char - char_spacing + 4
                temp_rows = max(temp_rows, 16)

            temp_config = BeadConfig(columns=config.columns, rows=temp_rows)
            grid = _ttf(seg.text, temp_config, font_mode=font_mode,
                        font_path=font_path, rotate=rotate)
            all_rows.extend(grid)

    # Trim or pad to config.rows
    if len(all_rows) > config.rows:
        all_rows = all_rows[:config.rows]
    while len(all_rows) < config.rows:
        all_rows.append([0] * config.columns)

    return all_rows
