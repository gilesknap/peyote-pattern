"""Unified font API — generates bitmaps from TTF fonts at any size."""

from .sizing import BeadConfig
from . import font_ttf


def text_to_fabric(
    text: str,
    config: BeadConfig,
    font_mode: str = 'auto',
    font_path: str | None = None,
    rotate: bool = True,
    char_height: int | None = None,
    border: int = 0,
) -> list[list[int]]:
    """Convert text to a centered peyote fabric grid.

    Args:
        text: Text to render.
        config: Bead configuration (columns, rows).
        font_mode: Ignored (kept for API compat). Always uses TTF.
        font_path: TTF font path. Auto-detected if None.
        rotate: True for sideways-reading (rings), False for straight (bracelets).
        char_height: Override character height in rows.
        border: Background beads to leave on each side, shrinking letter height.

    Returns:
        Fabric grid: config.rows x config.columns of 0/1 values.
    """
    effective_columns = max(4, config.columns - 2 * border)
    pixel_rows = font_ttf.render_text_rows(
        text, columns=effective_columns,
        char_height=char_height,
        font_path=font_path,
        rotate=rotate,
    )

    # Pad each row with border zeros on each side to restore full width
    if border > 0:
        pixel_rows = [[0] * border + row + [0] * (config.columns - effective_columns - border)
                      for row in pixel_rows]

    return _center_in_grid(pixel_rows, config)


def _center_in_grid(pixel_rows: list[list[int]], config: BeadConfig) -> list[list[int]]:
    """Center pixel rows vertically in a fabric grid."""
    n = len(pixel_rows)
    cols = config.columns

    # Ensure all rows are the right width
    normalized = []
    for row in pixel_rows:
        if len(row) < cols:
            # Pad with zeros
            normalized.append(row + [0] * (cols - len(row)))
        elif len(row) > cols:
            normalized.append(row[:cols])
        else:
            normalized.append(row)

    if n > config.rows:
        normalized = normalized[:config.rows]
        n = config.rows

    top_pad = (config.rows - n) // 2
    fabric: list[list[int]] = []
    for ri in range(config.rows):
        idx = ri - top_pad
        if 0 <= idx < n:
            fabric.append(list(normalized[idx]))
        else:
            fabric.append([0] * cols)
    return fabric
