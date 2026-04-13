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
    border_rows: int = 10,
    font_mode: str = 'auto',
    font_path: str | None = None,
    rotate: bool = True,
    border_color: int = 2,
    border: int = 0,
    **pattern_kwargs,
) -> list[list[int]]:
    """Text centered with decorative borders at the strip ends.

    Borders start at the top/bottom edges and grow *inward* toward the text.
    ``border_rows`` controls how many rows of pattern from each edge.
    Border ON-beads use *border_color* (default 2) so they can be coloured
    independently from the text foreground.
    """
    text_fabric = text_to_fabric(
        text, config, font_mode=font_mode, font_path=font_path, rotate=rotate,
        border=border,
    )

    # Generate border pattern
    pat_fn = PATTERN_CATALOG.get(border_pattern)
    if pat_fn is None:
        raise ValueError(f"Unknown pattern '{border_pattern}'. "
                         f"Available: {list(PATTERN_CATALOG.keys())}")

    kwargs = {'columns': config.columns, 'rows': border_rows}
    kwargs.update(pattern_kwargs or {})
    border_grid = pat_fn(**kwargs)

    result = [row[:] for row in text_fabric]

    # Top border — starts at row 0
    for i, brow in enumerate(border_grid):
        if i >= config.rows:
            break
        result[i] = [border_color if v else 0 for v in brow]

    # Bottom border — ends at last row
    for i, brow in enumerate(border_grid):
        ri = config.rows - border_rows + i
        if 0 <= ri < config.rows:
            result[ri] = [border_color if v else 0 for v in brow]

    return result


def compose_text_with_background(
    text: str,
    config: BeadConfig,
    background_pattern: str = 'checker',
    font_mode: str = 'auto',
    font_path: str | None = None,
    rotate: bool = True,
    border: int = 0,
    **pattern_kwargs,
) -> list[list[int]]:
    """Text overlaid on a decorative background. Text pixels override background."""
    pat_fn = PATTERN_CATALOG.get(background_pattern)
    if pat_fn is None:
        raise ValueError(f"Unknown pattern '{background_pattern}'")

    kwargs = {'columns': config.columns, 'rows': config.rows}
    kwargs.update(pattern_kwargs or {})
    bg = pat_fn(**kwargs)

    text_grid = text_to_fabric(
        text, config, font_mode=font_mode, font_path=font_path, rotate=rotate,
        border=border,
    )

    return overlay(bg, text_grid)


def compose_pattern_only(
    pattern_name: str,
    config: BeadConfig,
    **pattern_kwargs,
) -> list[list[int]]:
    """Full-grid decorative pattern with no text."""
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
