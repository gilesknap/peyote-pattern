"""Decorative pattern generators for peyote bead patterns.

All generators return list[list[int]] grids. Patterns are peyote-aware:
double-row minimum thickness, offset-aware diagonals.
"""

import math


def stripe_horizontal(columns: int, rows: int,
                      widths: list[int] | None = None,
                      colors: list[int] | None = None) -> list[list[int]]:
    """Horizontal stripes repeating vertically.

    Args:
        widths: Row count per stripe band (default [3, 3]).
        colors: Color index per band (default [1, 0]).
    """
    if widths is None:
        widths = [3, 3]
    if colors is None:
        colors = [1, 0]
    grid = []
    band_idx = 0
    band_row = 0
    for _ in range(rows):
        grid.append([colors[band_idx % len(colors)]] * columns)
        band_row += 1
        if band_row >= widths[band_idx % len(widths)]:
            band_row = 0
            band_idx += 1
    return grid


def stripe_vertical(columns: int, rows: int,
                    widths: list[int] | None = None,
                    colors: list[int] | None = None) -> list[list[int]]:
    """Vertical stripes running lengthwise."""
    if widths is None:
        widths = [2, 2]
    if colors is None:
        colors = [1, 0]
    # Build a single row template
    template = []
    band_idx = 0
    band_col = 0
    for _ in range(columns):
        template.append(colors[band_idx % len(colors)])
        band_col += 1
        if band_col >= widths[band_idx % len(widths)]:
            band_col = 0
            band_idx += 1
    return [list(template) for _ in range(rows)]


def chevron(columns: int, rows: int, width: int = 2,
            color: int = 1, bg: int = 0) -> list[list[int]]:
    """V-shaped chevron pattern repeating vertically.

    Uses double-row thickness for peyote visibility.
    """
    period = columns  # one full V per period
    grid = []
    for r in range(rows):
        row = [bg] * columns
        for w in range(width):
            pos = (r + w) % period
            # V shape: ascending and descending
            mid = columns // 2
            if pos < mid:
                col = pos
            else:
                col = columns - 1 - pos
            if 0 <= col < columns:
                row[col] = color
            mirror = columns - 1 - col
            if 0 <= mirror < columns:
                row[mirror] = color
        grid.append(row)
    return grid


def diamond(columns: int, rows: int, size: int = 4,
            color: int = 1, bg: int = 0) -> list[list[int]]:
    """Diamond/argyle pattern tiling."""
    grid = []
    for r in range(rows):
        row = [bg] * columns
        for c in range(columns):
            # Diamond distance from center of each tile
            cr = r % (size * 2)
            cc = c % (size * 2)
            dr = abs(cr - size)
            dc = abs(cc - size)
            if dr + dc <= size:
                # On the diamond edge
                if dr + dc >= size - 1:
                    row[c] = color
        grid.append(row)
    return grid


def zigzag(columns: int, rows: int, amplitude: int = 3,
           width: int = 2, color: int = 1, bg: int = 0) -> list[list[int]]:
    """Zigzag lines running down the length."""
    period = amplitude * 2
    grid = []
    for r in range(rows):
        row = [bg] * columns
        phase = r % period
        if phase < amplitude:
            center = phase
        else:
            center = period - phase
        # Scale to column range
        col = int(center * (columns - 1) / amplitude)
        for w in range(width):
            c = col + w
            if 0 <= c < columns:
                row[c] = color
        grid.append(row)
    return grid


def checker(columns: int, rows: int, block_size: int = 2,
            color: int = 1, bg: int = 0) -> list[list[int]]:
    """Checkerboard pattern with configurable block size."""
    grid = []
    for r in range(rows):
        row = []
        for c in range(columns):
            block_r = r // block_size
            block_c = c // block_size
            if (block_r + block_c) % 2 == 0:
                row.append(bg)
            else:
                row.append(color)
        grid.append(row)
    return grid


def border(columns: int, rows: int, thickness: int = 2,
           color: int = 1, bg: int = 0) -> list[list[int]]:
    """Border frame around the edges."""
    grid = []
    for r in range(rows):
        row = []
        for c in range(columns):
            if (r < thickness or r >= rows - thickness or
                    c < thickness or c >= columns - thickness):
                row.append(color)
            else:
                row.append(bg)
        grid.append(row)
    return grid


def dots(columns: int, rows: int, spacing: int = 4,
         color: int = 1, bg: int = 0) -> list[list[int]]:
    """Scattered dot pattern.

    The +1 offset on the column conditions lands each dot on an active
    peyote cell (rows alternate between odd/even active cols).
    """
    half = spacing // 2
    grid = []
    for r in range(rows):
        row = []
        for c in range(columns):
            if r % spacing == 0 and c % spacing == 1 % spacing:
                row.append(color)
            elif r % spacing == half and c % spacing == (half + 1) % spacing:
                row.append(color)
            else:
                row.append(bg)
        grid.append(row)
    return grid


def wave(columns: int, rows: int, amplitude: int = 2,
         period: int = 8, width: int = 2,
         color: int = 1, bg: int = 0) -> list[list[int]]:
    """Sine wave pattern."""
    mid = columns // 2
    grid = []
    for r in range(rows):
        row = [bg] * columns
        offset = int(amplitude * math.sin(2 * math.pi * r / period))
        for w in range(width):
            c = mid + offset + w
            if 0 <= c < columns:
                row[c] = color
        grid.append(row)
    return grid


def gradient_dither(columns: int, rows: int, direction: str = 'vertical',
                    color: int = 1, bg: int = 0) -> list[list[int]]:
    """Dithered gradient from dense to sparse."""
    grid = []
    for r in range(rows):
        row = []
        for c in range(columns):
            if direction == 'vertical':
                density = r / max(rows - 1, 1)
            else:
                density = c / max(columns - 1, 1)
            # Ordered dithering (2x2 Bayer matrix)
            threshold_map = [[0.0, 0.5], [0.75, 0.25]]
            t = threshold_map[r % 2][c % 2]
            if density > t:
                row.append(color)
            else:
                row.append(bg)
        grid.append(row)
    return grid


def greek_key(columns: int, rows: int, size: int = 4,
              color: int = 1, bg: int = 0) -> list[list[int]]:
    """Greek key / meander border pattern."""
    # Build one tile of the meander
    tile_h = size * 2
    tile_w = size * 2
    tile = [[bg] * tile_w for _ in range(tile_h)]

    # Draw the key shape
    for i in range(tile_w):
        tile[0][i] = color                    # top bar
    for i in range(tile_h):
        tile[i][tile_w - 1] = color           # right bar
    for i in range(tile_w - 1):
        tile[tile_h - 1][i] = color           # bottom bar (partial)
    for i in range(2, tile_h):
        tile[i][0] = color                    # left bar (partial)
    for i in range(1, tile_w - 1):
        tile[2][i] = color                    # inner top bar

    # Tile it
    grid = []
    for r in range(rows):
        row = []
        for c in range(columns):
            row.append(tile[r % tile_h][c % tile_w])
        grid.append(row)
    return grid


def argyle(columns: int, rows: int, size: int = 5,
           color1: int = 1, color2: int = 2, bg: int = 0) -> list[list[int]]:
    """Classic argyle: alternating filled diamonds with crossing stripes.

    Diamond interiors use *color1*, the crossing X-lines use *color2*.
    """
    grid = []
    period = size * 2
    for r in range(rows):
        row = []
        for c in range(columns):
            cr = r % period
            cc = c % period
            dr = abs(cr - size)
            dc = abs(cc - size)
            tile_r = r // period
            tile_c = c // period
            val = bg
            # Alternating filled diamonds
            if dr + dc < size and (tile_r + tile_c) % 2 == 0:
                val = color1
            # Thin crossing lines every `size` beads — overwrite so they stitch
            # the diamonds together visually
            if (r + c) % size == 0 or (r - c) % size == 0:
                val = color2
            row.append(val)
        grid.append(row)
    return grid


def scales(columns: int, rows: int, radius: int = 3,
           color1: int = 1, color2: int = 2, bg: int = 0) -> list[list[int]]:
    """Fish / dragon scales — alternating arc rows in two colors.

    Each scale row is *radius* beads tall. Adjacent scale rows shift by
    *radius* columns so arcs interlock like a real scale mosaic.
    """
    grid = []
    period = radius * 2
    for r in range(rows):
        scale_row = r // radius
        row_in_scale = r % radius
        offset = radius if scale_row % 2 else 0
        color = color1 if scale_row % 2 == 0 else color2
        row = [bg] * columns
        for c in range(columns):
            tile_c = (c + offset) % period
            dx = tile_c - radius
            # Arc edge: points on the circle of given radius
            dist_sq = dx * dx + row_in_scale * row_in_scale
            if (radius - 1) ** 2 < dist_sq <= radius ** 2:
                row[c] = color
            # Fill the arc bottom with the scale color for a solid look
            elif dist_sq <= (radius - 1) ** 2 and row_in_scale >= radius - 1:
                row[c] = color
        grid.append(row)
    return grid


def flames(columns: int, rows: int, size: int = 5,
           color1: int = 1, color2: int = 2, bg: int = 0) -> list[list[int]]:
    """Upward-licking flames — alternating triangular tongues in two colors."""
    period_c = size * 2
    period_r = size * 2
    grid = []
    for r in range(rows):
        row = []
        for c in range(columns):
            tile_r = r % period_r
            tile_c = c % period_c
            # Flame rises from bottom of tile (tile_r=period_r-1) to tip (tile_r=0).
            # Width tapers: at tile_r=k from bottom, flame half-width = k // 2 + 1.
            from_bottom = period_r - 1 - tile_r
            half_w = from_bottom // 2 + 1
            # Two flame columns per period, offset — alternating colors
            center1 = size // 2
            center2 = size + size // 2
            val = bg
            if abs(tile_c - center1) < half_w:
                val = color1
            if abs(tile_c - center2) < half_w:
                # Offset the phase vertically so flames alternate
                alt_from_bottom = (from_bottom + size) % period_r
                alt_half_w = alt_from_bottom // 2 + 1
                if abs(tile_c - center2) < alt_half_w:
                    val = color2
            row.append(val)
        grid.append(row)
    return grid


def braid(columns: int, rows: int, period: int = 8, width: int = 2,
          color1: int = 1, color2: int = 2, bg: int = 0) -> list[list[int]]:
    """Two strands weaving over/under each other down the strip."""
    mid = columns // 2
    amplitude = max(2, mid - 1)
    grid = []
    for r in range(rows):
        row = [bg] * columns
        # Phase 0..1 around the period; two strands are half a period apart
        phase1 = (r % period) / period * 2 * math.pi
        phase2 = phase1 + math.pi
        offset1 = int(round(amplitude * math.sin(phase1)))
        offset2 = int(round(amplitude * math.sin(phase2)))
        # "Depth" — which strand is in front, alternates by half-period
        strand1_front = (r % period) < period // 2
        c1 = mid + offset1
        c2 = mid + offset2
        # Draw the back strand first, then the front, so the front overwrites
        strands = [(c2, color2), (c1, color1)] if strand1_front \
            else [(c1, color1), (c2, color2)]
        for center, color in strands:
            for w in range(-width // 2 + 1, width // 2 + 1):
                cc = center + w
                if 0 <= cc < columns:
                    row[cc] = color
        grid.append(row)
    return grid


# "Kinetic" 10-wide × 72-row peyote design, transcribed from the
# original chart. Values: 0=background (pink), 1=accent1 (red),
# 2=accent2 (black). Rows 0-8 are the lead-in, rows 9-24 form a 16-row
# cycle that repeats three times through row 64, then rows 65-71 are an
# all-background tail. Stored as the verbatim source chart and mirrored
# left-to-right at render time so each bead lands on an active peyote
# cell under the odd-row-odd-col / even-row-even-col parity.
_KINETIC_BASE: list[list[int]] = [
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [0, 0, 0, 0, 0, 0, 0, 0, 1, 0],
    [0, 0, 0, 0, 0, 0, 0, 1, 0, 0],
    [0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
    [0, 0, 0, 0, 0, 1, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 1, 0],
    [0, 1, 0, 0, 0, 0, 0, 1, 0, 0],
    [0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
    [0, 0, 0, 1, 0, 0, 0, 0, 0, 0],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 1, 0, 0, 0, 0, 0, 1, 0, 0],
    [0, 0, 1, 0, 0, 0, 1, 0, 1, 0],
    [0, 0, 0, 1, 0, 0, 0, 2, 0, 0],
    [0, 0, 0, 0, 1, 0, 1, 0, 1, 0],
    [0, 0, 0, 0, 0, 0, 0, 1, 0, 0],
    [0, 0, 1, 0, 0, 0, 0, 0, 0, 0],
    [0, 1, 0, 1, 0, 0, 0, 0, 0, 1],
    [0, 0, 2, 0, 0, 0, 0, 0, 1, 0],
    [0, 1, 0, 1, 0, 0, 0, 1, 0, 0],
    [0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
    [0, 0, 0, 0, 0, 1, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 1, 0],
    [0, 1, 0, 0, 0, 0, 0, 1, 0, 0],
    [0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
    [0, 0, 0, 1, 0, 0, 0, 0, 0, 0],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 1, 0, 0, 0, 0, 0, 1, 0, 0],
    [0, 0, 1, 0, 0, 0, 1, 0, 1, 0],
    [0, 0, 0, 1, 0, 0, 0, 2, 0, 0],
    [0, 0, 0, 0, 1, 0, 1, 0, 1, 0],
    [0, 0, 0, 0, 0, 0, 0, 1, 0, 0],
    [0, 0, 1, 0, 0, 0, 0, 0, 0, 0],
    [0, 1, 0, 1, 0, 0, 0, 0, 0, 1],
    [0, 0, 2, 0, 0, 0, 0, 0, 1, 0],
    [0, 1, 0, 1, 0, 0, 0, 1, 0, 0],
    [0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
    [0, 0, 0, 0, 0, 1, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 1, 0],
    [0, 1, 0, 0, 0, 0, 0, 1, 0, 0],
    [0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
    [0, 0, 0, 1, 0, 0, 0, 0, 0, 0],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 1, 0, 0, 0, 0, 0, 1, 0, 0],
    [0, 0, 1, 0, 0, 0, 1, 0, 1, 0],
    [0, 0, 0, 1, 0, 0, 0, 2, 0, 0],
    [0, 0, 0, 0, 1, 0, 1, 0, 1, 0],
    [0, 0, 0, 0, 0, 0, 0, 1, 0, 0],
    [0, 0, 1, 0, 0, 0, 0, 0, 0, 0],
    [0, 1, 0, 1, 0, 0, 0, 0, 0, 1],
    [0, 0, 2, 0, 0, 0, 0, 0, 1, 0],
    [0, 1, 0, 1, 0, 0, 0, 1, 0, 0],
    [0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
    [0, 0, 0, 0, 0, 1, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 1, 0],
    [0, 1, 0, 0, 0, 0, 0, 1, 0, 0],
    [0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
    [0, 0, 0, 1, 0, 0, 0, 0, 0, 0],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 1, 0, 0, 0, 0, 0, 1, 0, 0],
    [0, 0, 1, 0, 0, 0, 1, 0, 1, 0],
    [0, 0, 0, 1, 0, 0, 0, 2, 0, 0],
    [0, 0, 0, 0, 1, 0, 1, 0, 1, 0],
    [0, 0, 0, 0, 0, 0, 0, 1, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
]


def kinetic(columns: int, rows: int,
            color1: int = 1, color2: int = 2,
            bg: int = 0) -> list[list[int]]:
    """Kinetic peyote design — diagonal streaks over pink.

    The original chart is 10 wide × 72 rows. For any other size the 16-row
    middle cycle (base rows 9-24) tiles vertically — its even length keeps
    the peyote parity correct — and the 10-wide motif wraps horizontally.
    """
    color_map = [bg, color1, color2]
    # Mirror each source row L-R so bead positions land on active peyote
    # cells under the odd-row-odd-col / even-row-even-col parity.
    base = [row[::-1] for row in _KINETIC_BASE]
    cycle_start, cycle_len = 9, 16
    base_rows = len(base)

    grid = []
    for r in range(rows):
        if r < base_rows:
            src = base[r]
        else:
            src = base[cycle_start + (r - cycle_start) % cycle_len]
        grid.append([color_map[src[c % 10]] for c in range(columns)])
    return grid


def honeycomb(columns: int, rows: int, size: int = 3,
              color1: int = 1, color2: int = 2, bg: int = 0) -> list[list[int]]:
    """Hexagonal cells — alternating cell fills with shared walls."""
    # A hex tile in bead coords is approximated as size*2 cols × size*2 rows,
    # with offset rows shifted by size cols (honeycomb offset lattice).
    period_r = size * 2
    grid = []
    for r in range(rows):
        row = []
        hex_row = r // period_r
        row_in_hex = r % period_r
        col_offset = size if hex_row % 2 else 0
        for c in range(columns):
            tile_c = (c + col_offset) % (size * 2)
            # Wall: top/bottom edge of tile
            on_wall = (row_in_hex == 0 or row_in_hex == period_r - 1)
            # Side walls at tile_c == 0 or size*2-1
            if tile_c == 0 or tile_c == size * 2 - 1:
                on_wall = True
            # Cell fill alternates
            hex_col = (c + col_offset) // (size * 2)
            fill = color1 if (hex_row + hex_col) % 2 == 0 else color2
            if on_wall:
                row.append(color2 if fill == color1 else color1)
            else:
                row.append(fill if row_in_hex not in (0, period_r - 1) else bg)
        grid.append(row)
    return grid


PATTERN_CATALOG: dict[str, callable] = {
    'stripe-h': stripe_horizontal,
    'stripe-v': stripe_vertical,
    'chevron': chevron,
    'diamond': diamond,
    'zigzag': zigzag,
    'checker': checker,
    'border': border,
    'dots': dots,
    'wave': wave,
    'gradient': gradient_dither,
    'greek-key': greek_key,
    'argyle': argyle,
    'scales': scales,
    'flames': flames,
    'braid': braid,
    'honeycomb': honeycomb,
    'kinetic': kinetic,
}


# Patterns that emit a single ON color (index 1). They look good with just
# Background + Accent 1 and ignore Accent 2.
SINGLE_COLOR_PATTERNS: list[str] = [
    'stripe-h', 'stripe-v', 'chevron', 'diamond', 'zigzag',
    'checker', 'border', 'dots', 'wave', 'gradient', 'greek-key',
]

# Patterns that emit two ON colors (indices 1 and 2). These use both
# Accent 1 and Accent 2 and are the ones that benefit from the full palette.
TWO_COLOR_PATTERNS: list[str] = [
    'argyle', 'scales', 'flames', 'braid', 'honeycomb', 'kinetic',
]


# "Repeat" maps the GUI's single repeat-in-beads control onto each pattern's
# internal period parameter. Value shape: (kwarg_name, default_beads, convert).
# Patterns missing from this dict don't have a meaningful periodic knob:
# chevron spans the full column width, border is a single frame, gradient
# dithers across the whole grid.
PATTERN_REPEAT_SPEC: dict[str, tuple[str, int, callable]] = {
    'stripe-h':  ('widths',     6, lambda r: [max(1, r // 2)] * 2),
    'stripe-v':  ('widths',     4, lambda r: [max(1, r // 2)] * 2),
    'diamond':   ('size',       8, lambda r: max(1, r // 2)),
    'zigzag':    ('amplitude',  6, lambda r: max(1, r // 2)),
    'checker':   ('block_size', 2, lambda r: max(1, r)),
    'dots':      ('spacing',    4, lambda r: max(2, r)),
    'wave':      ('period',     8, lambda r: max(2, r)),
    'greek-key': ('size',       8, lambda r: max(1, r // 2)),
    'argyle':    ('size',      10, lambda r: max(1, r // 2)),
    'scales':    ('radius',     6, lambda r: max(1, r // 2)),
    'flames':    ('size',      10, lambda r: max(1, r // 2)),
    'braid':     ('period',     8, lambda r: max(2, r)),
    'honeycomb': ('size',       6, lambda r: max(1, r // 2)),
}


def pattern_repeat_default(pattern_name: str) -> int | None:
    """Default repeat (beads between repeats) for a pattern, or None if N/A."""
    spec = PATTERN_REPEAT_SPEC.get(pattern_name)
    return spec[1] if spec else None


def pattern_repeat_kwargs(pattern_name: str, repeat: int | None) -> dict:
    """Translate a repeat-in-beads value into the pattern's own kwargs."""
    spec = PATTERN_REPEAT_SPEC.get(pattern_name)
    if spec is None or repeat is None:
        return {}
    kwarg_name, _default, convert = spec
    return {kwarg_name: convert(int(repeat))}
