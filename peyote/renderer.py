"""SVG renderer for peyote bead patterns — parameterized for any size."""

from .sizing import BeadConfig
from .colors import ColorPalette


def _bead_el(x: float, y: float, val: int,
             palette: ColorPalette, config: BeadConfig,
             label: bool = True) -> str:
    """Generate SVG for a single bead."""
    fill = palette.colors.get(val, '#cccccc')
    stroke = palette.strokes.get(val, '#999999')
    txt = palette.text_colors.get(val, '#333333')
    bw, bh, rx = config.bead_width, config.bead_height, config.corner_radius

    el = (f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw}" height="{bh}" rx="{rx}" '
          f'fill="{fill}" stroke="{stroke}" stroke-width="1"/>')
    if label:
        lbl = palette.label(val)
        font_size = max(6, min(9, bw // 3))
        el += (f'<text x="{x+bw/2:.1f}" y="{y+bh/2+font_size//3:.1f}" text-anchor="middle" '
               f'font-size="{font_size}" font-weight="600" fill="{txt}" '
               f'font-family="Arial,sans-serif">{lbl}</text>')
    return el


def make_fabric_svg(fabric: list[list[int]], title: str,
                    config: BeadConfig, palette: ColorPalette) -> tuple[str, int, int]:
    """Render finished fabric view (interleaved brick appearance)."""
    PL = 30; PT = 8; PB = 20; PR = 30
    nrows = len(fabric)
    bh = config.bead_height
    slot = config.slot

    last_y = PT + (nrows - 1) * bh / 2
    SH = int(last_y + bh + PB)
    SW = PL + config.columns * slot + slot + PR

    el = []

    # bx = PL + fc * slot drives the brick offset directly off each row's
    # active cols, so even and odd column counts both render correctly.
    for ri in range(nrows):
        N = ri + 1
        fab_cols = config.cols_for_row(ri)
        y = PT + (N - 1) * bh / 2
        for fc in fab_cols:
            val = fabric[ri][fc]
            bx = PL + fc * slot
            el.append(_bead_el(bx, y, val, palette, config, label=False))

    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{SW}" height="{SH}" '
           f'viewBox="0 0 {SW} {SH}"><rect width="{SW}" height="{SH}" fill="white"/>'
           + ''.join(el) + '</svg>')
    return svg, SW, SH


CHECKBOX_SIZE = 14


def _pattern_arrow(N: int) -> str:
    """Arrow glyph for row N in pattern view. Empty for merged row 2."""
    if N == 1:
        return '\u2192'
    if N == 2:
        return ''
    return '\u2190' if (N % 2 == 1) else '\u2192'


def _pattern_layout(config: BeadConfig, nrows: int) -> dict:
    """Geometry shared by render + checkbox hit-testing."""
    bh = config.bead_height
    h = bh / 2.0
    LABEL_W = 52
    ARROW_W = 28
    PL = LABEL_W + ARROW_W + 8
    PR = LABEL_W + ARROW_W + 8
    PT = 8; PB = 40
    GRID_RIGHT = PL + config.columns * config.slot

    def pattern_y(N: int) -> float:
        fabric_y = (N - 1) * h
        if N == 1:    dy = 0
        elif N == 2:  dy = -h
        elif N == 3:  dy = 0
        else:         dy = h * (N - 3)
        return fabric_y + dy

    SW = GRID_RIGHT + PR
    SH = int(PT + pattern_y(nrows) + bh + PB)
    return dict(bh=bh, h=h, LABEL_W=LABEL_W, ARROW_W=ARROW_W,
                PL=PL, PR=PR, PT=PT, PB=PB,
                GRID_RIGHT=GRID_RIGHT, SW=SW, SH=SH, pattern_y=pattern_y)


def pattern_checkbox_bounds(fabric: list[list[int]],
                            config: BeadConfig) -> list[tuple[int, float, float, int]]:
    """Return [(N_click, x, y, size), ...] — one per visible pattern row.

    N_click is the row number marked complete when this box is ticked
    (2 for the merged R1+2, N otherwise). Row 2 is merged and gets no
    standalone checkbox.
    """
    nrows = len(fabric)
    L = _pattern_layout(config, nrows)
    sz = CHECKBOX_SIZE
    out: list[tuple[int, float, float, int]] = []
    for ri in range(nrows):
        N = ri + 1
        if N == 2:
            continue
        arrow = _pattern_arrow(N)
        on_right_arrow = (arrow == '\u2190')
        if on_right_arrow:
            cx = L['LABEL_W'] + L['ARROW_W'] / 2 - sz / 2
        else:
            cx = L['GRID_RIGHT'] + 8 + L['ARROW_W'] / 2 - sz / 2
        cy = L['PT'] + L['pattern_y'](N) + L['bh'] / 2 - sz / 2
        N_click = 2 if N == 1 else N
        out.append((N_click, cx, cy, sz))
    return out


def _checkbox_el(x: float, y: float, size: int, checked: bool) -> str:
    rect = (f'<rect x="{x:.1f}" y="{y:.1f}" width="{size}" height="{size}" '
            f'rx="2" fill="#fff" stroke="#888" stroke-width="1.2"/>')
    if not checked:
        return rect
    tick = (f'<path d="M{x+size*0.22:.1f} {y+size*0.52:.1f} '
            f'L{x+size*0.44:.1f} {y+size*0.74:.1f} '
            f'L{x+size*0.80:.1f} {y+size*0.28:.1f}" '
            f'stroke="#1976d2" stroke-width="2" fill="none" '
            f'stroke-linecap="round" stroke-linejoin="round"/>')
    return rect + tick


def make_pattern_svg(fabric: list[list[int]], title: str,
                     config: BeadConfig, palette: ColorPalette,
                     progress_through: int = 0) -> tuple[str, int, int]:
    """Render flat working pattern view with row labels and tick-off boxes."""
    bw = config.bead_width
    slot = config.slot
    nrows = len(fabric)
    L = _pattern_layout(config, nrows)
    bh = L['bh']; LABEL_W = L['LABEL_W']; ARROW_W = L['ARROW_W']
    PL = L['PL']; PT = L['PT']; GRID_RIGHT = L['GRID_RIGHT']
    SW = L['SW']; SH = L['SH']; pattern_y = L['pattern_y']

    # Show bead labels only if beads are big enough
    show_labels = bw >= 16

    el = []

    for ri in range(nrows):
        N = ri + 1
        py = PT + pattern_y(N)
        cy = py + bh / 2 + 4
        fab_cols = config.cols_for_row(ri)

        # Row labels
        if N == 1:
            label = 'R1+2'
        elif N == 2:
            label = ''
        else:
            label = f'R{N}'
        arrow = _pattern_arrow(N)

        if label:
            # ← rows labelled on right, → rows on left — zig-zag that tracks
            # stitch direction so the eye follows the thread path.
            on_right = arrow == '\u2190'
            if on_right:
                label_x = GRID_RIGHT + 8 + ARROW_W + 4
                arrow_x = GRID_RIGHT + 8 + ARROW_W / 2
                label_anchor = 'start'
            else:
                label_x = LABEL_W - 4
                arrow_x = LABEL_W + ARROW_W // 2 + 4
                label_anchor = 'end'
            el.append(f'<text x="{label_x:.1f}" y="{cy:.1f}" text-anchor="{label_anchor}" '
                      f'font-size="10" font-weight="500" fill="#666" '
                      f'font-family="Arial,sans-serif">{label}</text>'
                      f'<text x="{arrow_x:.1f}" y="{cy:.1f}" '
                      f'text-anchor="middle" font-size="27" font-weight="700" fill="#555" '
                      f'font-family="Arial,sans-serif">{arrow}</text>')

        dimmed = N <= progress_through
        if dimmed:
            el.append('<g opacity="0.3">')
        for bi, fc in enumerate(fab_cols):
            val = fabric[ri][fc]
            bx = PL + fc * slot
            el.append(_bead_el(bx, py, val, palette, config, label=show_labels))
        if dimmed:
            el.append('</g>')

    # Checkboxes last so they sit on top of beads.
    for N_click, cx, cy, sz in pattern_checkbox_bounds(fabric, config):
        el.append(_checkbox_el(cx, cy, sz, checked=progress_through >= N_click))

    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{SW}" height="{SH}" '
           f'viewBox="0 0 {SW} {SH}"><rect width="{SW}" height="{SH}" fill="white"/>'
           + ''.join(el) + '</svg>')
    return svg, SW, SH
