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


def _legend_els(palette: ColorPalette, start_x: float) -> str:
    """Generate SVG legend elements."""
    els = []
    x = start_x
    for i in range(palette.num_colors):
        lbl = palette.label(i)
        name = palette.names.get(i, f'Color {i}')
        fill = palette.colors[i]
        stroke = palette.strokes[i]
        els.append(
            f'<rect x="{x}" y="24" width="12" height="12" rx="3" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1"/>'
            f'<text x="{x+16}" y="35" font-size="10" fill="#555" '
            f'font-family="Arial,sans-serif">{lbl}={name}</text>')
        x += 90
    return ''.join(els)


def make_fabric_svg(fabric: list[list[int]], title: str,
                    config: BeadConfig, palette: ColorPalette) -> tuple[str, int, int]:
    """Render finished fabric view (interleaved brick appearance)."""
    PL = 30; PT = 46; PB = 20; PR = 30
    nrows = len(fabric)
    bw, bh = config.bead_width, config.bead_height
    slot = config.slot

    last_y = PT + (nrows - 1) * bh / 2
    SH = int(last_y + bh + PB)
    SW = PL + config.columns * slot + slot + PR

    el = []
    el.append(f'<text x="{SW//2}" y="16" text-anchor="middle" font-size="13" '
              f'font-weight="600" fill="#333" font-family="Arial,sans-serif">'
              f'{title} — finished fabric</text>')
    el.append(_legend_els(palette, PL))

    for ri in range(nrows):
        N = ri + 1
        is_odd = (N % 2 == 1)
        fab_cols = config.cols_for_row(ri)
        x_offset = 0 if is_odd else slot
        y = PT + (N - 1) * bh / 2
        for bi, fc in enumerate(fab_cols):
            val = fabric[ri][fc]
            bx = PL + x_offset + bi * slot * 2
            el.append(_bead_el(bx, y, val, palette, config, label=False))

    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{SW}" height="{SH}" '
           f'viewBox="0 0 {SW} {SH}"><rect width="{SW}" height="{SH}" fill="white"/>'
           + ''.join(el) + '</svg>')
    return svg, SW, SH


def make_pattern_svg(fabric: list[list[int]], title: str,
                     config: BeadConfig, palette: ColorPalette) -> tuple[str, int, int]:
    """Render flat working pattern view with row labels."""
    bw, bh = config.bead_width, config.bead_height
    slot = config.slot
    h = bh / 2.0

    # Scale label area for larger patterns
    LABEL_W = 52; ARROW_W = 22
    PL = LABEL_W + ARROW_W + 8
    PT = 46; PB = 40
    SW = PL + config.columns * slot + 40

    # Show bead labels only if beads are big enough
    show_labels = bw >= 16

    def pattern_y(N):
        fabric_y = (N - 1) * h
        if N == 1:    dy = 0
        elif N == 2:  dy = -h
        elif N == 3:  dy = 0
        else:         dy = h * (N - 3)
        return fabric_y + dy

    nrows = len(fabric)
    SH = int(PT + pattern_y(nrows) + bh + PB)

    el = []
    el.append(f'<text x="{SW//2}" y="16" text-anchor="middle" font-size="13" '
              f'font-weight="600" fill="#333" font-family="Arial,sans-serif">'
              f'{title} — working pattern</text>')
    el.append(_legend_els(palette, PL))

    for ri in range(nrows):
        N = ri + 1
        py = PT + pattern_y(N)
        cy = py + bh / 2 + 4
        is_odd = (N % 2 == 1)
        fab_cols = config.cols_for_row(ri)

        # Row labels
        if N == 1:
            label, arrow = 'R1+2', '\u2192'
        elif N == 2:
            label, arrow = '', ''
        else:
            label = f'R{N}'
            arrow = '\u2190' if is_odd else '\u2192'

        if label:
            el.append(f'<text x="{LABEL_W-4}" y="{cy:.1f}" text-anchor="end" '
                      f'font-size="10" font-weight="500" fill="#666" '
                      f'font-family="Arial,sans-serif">{label}</text>'
                      f'<text x="{LABEL_W+ARROW_W//2+4}" y="{cy:.1f}" '
                      f'text-anchor="middle" font-size="13" fill="#888" '
                      f'font-family="Arial,sans-serif">{arrow}</text>')

        for bi, fc in enumerate(fab_cols):
            val = fabric[ri][fc]
            bx = PL + fc * slot
            el.append(_bead_el(bx, py, val, palette, config, label=show_labels))

    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{SW}" height="{SH}" '
           f'viewBox="0 0 {SW} {SH}"><rect width="{SW}" height="{SH}" fill="white"/>'
           + ''.join(el) + '</svg>')
    return svg, SW, SH
