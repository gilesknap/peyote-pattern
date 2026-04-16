"""Manual pixel editor — pure logic, no NiceGUI imports."""

import json
from dataclasses import dataclass, field

from .colors import ColorPalette, darken, text_color_for
from .export import _dict_to_state, _state_to_dict
from .sizing import BeadConfig


# SVG layout constants — must match peyote.renderer.make_fabric_svg
PL = 30
PT = 8

HISTORY_CAP = 50
RECENT_COLORS_CAP = 10


@dataclass
class DragState:
    tool: str
    start_cell: tuple[int, int] | None
    last_cell: tuple[int, int] | None
    color: int


@dataclass
class EditorState:
    fabric: list[list[int]]
    config: BeadConfig
    palette: ColorPalette
    title: str
    snapshot: list[list[int]]
    snapshot_palette: ColorPalette
    active_color: int = 1
    tool: str = "pencil"
    history: list[list[list[int]]] = field(default_factory=list)
    redo_stack: list[list[list[int]]] = field(default_factory=list)
    clipboard: list[list[int | None]] | None = None
    clipboard_origin: tuple[int, int] | None = None
    selection: tuple[int, int, int, int] | None = None
    recent_colors: list[int] = field(default_factory=list)
    drag: DragState | None = None
    # Floating buffer — active during paste-positioning or drag-move.
    # `floating_anchor` is the (dr, dc) inside the buffer that tracks the cursor.
    # `floating_lifted` is True when the buffer was cut from the fabric (drag-move),
    # so cancel must restore the source. False for plain paste.
    floating: list[list[int | None]] | None = None
    floating_origin: tuple[int, int] | None = None
    floating_anchor: tuple[int, int] = (0, 0)
    floating_lifted: bool = False


# ─── Coordinate helpers ────────────────────────────────────────────────

def bead_center(ri: int, fc: int, config: BeadConfig) -> tuple[float, float]:
    """Center of bead at fabric (ri, fc) in SVG viewBox coords."""
    slot = config.slot
    bw, bh = config.bead_width, config.bead_height
    return PL + fc * slot + bw / 2, PT + ri * bh / 2 + bh / 2


def _fc_to_bi(ri: int, fc: int, config: BeadConfig) -> int | None:
    cols = config.cols_for_row(ri)
    try:
        return cols.index(fc)
    except ValueError:
        return None


def _bi_to_fc(ri: int, bi: int, config: BeadConfig) -> int | None:
    cols = config.cols_for_row(ri)
    if 0 <= bi < len(cols):
        return cols[bi]
    return None


def hit_test(cx: float, cy: float, fabric: list[list[int]],
             config: BeadConfig) -> tuple[int, int] | None:
    """Map a click in SVG coords to (row_index, fabric_col).

    Returns None for clicks in gutters between beads or on inactive locations.
    Rows overlap by bh/2, so two candidate rows are checked and the nearest
    bead whose bounds contain the click wins.
    """
    bw, bh = config.bead_width, config.bead_height
    slot = config.slot
    nrows = len(fabric)
    if bh <= 0 or nrows == 0:
        return None

    base = (cy - PT) / (bh / 2)
    for ri in (int(base), int(base) - 1):
        if not (0 <= ri < nrows):
            continue
        cols = config.cols_for_row(ri)
        if not cols:
            continue
        x_offset = 0 if (ri + 1) % 2 == 1 else slot
        bi = round((cx - PL - x_offset - bw / 2) / (2 * slot))
        bi = max(0, min(len(cols) - 1, bi))
        fc = cols[bi]
        bcx, bcy = bead_center(ri, fc, config)
        if abs(cx - bcx) <= bw / 2 and abs(cy - bcy) <= bh / 2:
            return ri, fc
    return None


# ─── Mutations ─────────────────────────────────────────────────────────

def paint_pencil(state: EditorState, ri: int, fc: int) -> bool:
    """Paint a single bead; returns True if the cell changed."""
    if not (0 <= ri < len(state.fabric)):
        return False
    if fc not in state.config.cols_for_row(ri):
        return False
    if state.fabric[ri][fc] == state.active_color:
        return False
    state.fabric[ri][fc] = state.active_color
    return True


def paint_line(fabric: list[list[int]], config: BeadConfig,
               a: tuple[int, int], b: tuple[int, int], color: int) -> None:
    """Bresenham line between (ri, fc) endpoints, in (ri, bi) space.

    Running Bresenham in bead-index space (rather than fabric-col) keeps the
    line visually straight in the brick-interleaved fabric view.
    """
    bi_a = _fc_to_bi(a[0], a[1], config)
    bi_b = _fc_to_bi(b[0], b[1], config)
    if bi_a is None or bi_b is None:
        return
    ri0, bi0 = a[0], bi_a
    ri1, bi1 = b[0], bi_b
    nrows = len(fabric)

    dri = abs(ri1 - ri0)
    dbi = abs(bi1 - bi0)
    sri = 1 if ri0 < ri1 else -1
    sbi = 1 if bi0 < bi1 else -1
    err = dri - dbi
    ri, bi = ri0, bi0
    while True:
        if 0 <= ri < nrows:
            fc = _bi_to_fc(ri, bi, config)
            if fc is not None:
                fabric[ri][fc] = color
        if ri == ri1 and bi == bi1:
            break
        e2 = 2 * err
        if e2 > -dbi:
            err -= dbi
            ri += sri
        if e2 < dri:
            err += dri
            bi += sbi


def paint_rect(fabric: list[list[int]], config: BeadConfig,
               a: tuple[int, int], b: tuple[int, int], color: int,
               fill: bool) -> None:
    """Rectangle outline or fill in (ri, bi) space."""
    bi_a = _fc_to_bi(a[0], a[1], config)
    bi_b = _fc_to_bi(b[0], b[1], config)
    if bi_a is None or bi_b is None:
        return
    r0, r1 = sorted((a[0], b[0]))
    c0, c1 = sorted((bi_a, bi_b))
    nrows = len(fabric)
    for ri in range(r0, r1 + 1):
        if not (0 <= ri < nrows):
            continue
        for bi in range(c0, c1 + 1):
            on_edge = (ri == r0 or ri == r1 or bi == c0 or bi == c1)
            if not fill and not on_edge:
                continue
            fc = _bi_to_fc(ri, bi, config)
            if fc is not None:
                fabric[ri][fc] = color


def paint_circle(fabric: list[list[int]], config: BeadConfig,
                 center: tuple[int, int], edge: tuple[int, int],
                 color: int) -> None:
    """Midpoint circle outline in (ri, bi) space."""
    bi_c = _fc_to_bi(center[0], center[1], config)
    bi_e = _fc_to_bi(edge[0], edge[1], config)
    if bi_c is None or bi_e is None:
        return
    rc = center[0]
    dri = edge[0] - rc
    dbi = bi_e - bi_c
    radius = int(round((dri * dri + dbi * dbi) ** 0.5))
    if radius <= 0:
        fc = _bi_to_fc(rc, bi_c, config)
        if fc is not None and 0 <= rc < len(fabric):
            fabric[rc][fc] = color
        return

    def plot(ri: int, bi: int) -> None:
        if 0 <= ri < len(fabric):
            fc = _bi_to_fc(ri, bi, config)
            if fc is not None:
                fabric[ri][fc] = color

    x, y = radius, 0
    err = 1 - radius
    while x >= y:
        for dx, dy in ((x, y), (y, x), (-x, y), (-y, x),
                       (-x, -y), (-y, -x), (x, -y), (y, -x)):
            plot(rc + dy, bi_c + dx)
        y += 1
        if err < 0:
            err += 2 * y + 1
        else:
            x -= 1
            err += 2 * (y - x) + 1


def flood_fill(fabric: list[list[int]], config: BeadConfig,
               ri: int, fc: int, color: int) -> None:
    """6-neighbour peyote flood fill from (ri, fc)."""
    if not (0 <= ri < len(fabric)):
        return
    if fc not in config.cols_for_row(ri):
        return
    orig = fabric[ri][fc]
    if orig == color:
        return
    ncols = config.columns
    nrows = len(fabric)
    stack = [(ri, fc)]
    while stack:
        r, c = stack.pop()
        if not (0 <= r < nrows and 0 <= c < ncols):
            continue
        if c not in config.cols_for_row(r):
            continue
        if fabric[r][c] != orig:
            continue
        fabric[r][c] = color
        for dr, dc in ((0, -2), (0, 2), (-1, -1), (-1, 1), (1, -1), (1, 1)):
            stack.append((r + dr, c + dc))


def clear_fabric(fabric: list[list[int]], color: int) -> None:
    for row in fabric:
        for i in range(len(row)):
            row[i] = color


# ─── Selection & clipboard ─────────────────────────────────────────────

def get_selection(fabric: list[list[int]], config: BeadConfig,
                  sel: tuple[int, int, int, int]) -> list[list[int | None]]:
    """Extract a rectangular region (inclusive bounds in fabric cols).

    Inactive cells within the rectangle are stored as None so paste can
    skip them.
    """
    r0, c0, r1, c1 = sel
    r0, r1 = sorted((r0, r1))
    c0, c1 = sorted((c0, c1))
    out: list[list[int | None]] = []
    for ri in range(r0, r1 + 1):
        row: list[int | None] = []
        active = set(config.cols_for_row(ri)) if 0 <= ri < len(fabric) else set()
        for fc in range(c0, c1 + 1):
            if ri < 0 or ri >= len(fabric) or fc not in active:
                row.append(None)
            else:
                row.append(fabric[ri][fc])
        out.append(row)
    return out


def paste_at(fabric: list[list[int]], config: BeadConfig,
             clipboard: list[list[int | None]], r0: int, c0: int) -> None:
    """Write clipboard into fabric at (r0, c0); skips None and inactive cells."""
    nrows = len(fabric)
    ncols = config.columns
    for dr, row in enumerate(clipboard):
        tr = r0 + dr
        if not (0 <= tr < nrows):
            continue
        active = set(config.cols_for_row(tr))
        for dc, val in enumerate(row):
            if val is None:
                continue
            tc = c0 + dc
            if 0 <= tc < ncols and tc in active:
                fabric[tr][tc] = val


def click_in_selection(sel: tuple[int, int, int, int],
                       hit: tuple[int, int]) -> bool:
    r0, r1 = sorted((sel[0], sel[2]))
    c0, c1 = sorted((sel[1], sel[3]))
    ri, fc = hit
    return r0 <= ri <= r1 and c0 <= fc <= c1


def start_paste(state: EditorState) -> bool:
    """Begin floating-paste mode at the remembered clipboard origin.

    Returns False if the clipboard is empty.
    """
    if state.clipboard is None:
        return False
    state.floating = [row[:] for row in state.clipboard]
    state.floating_origin = state.clipboard_origin or (0, 0)
    state.floating_anchor = (0, 0)
    state.floating_lifted = False
    state.selection = None
    return True


def lift_selection_for_drag(state: EditorState,
                            click: tuple[int, int]) -> bool:
    """Lift the current selection into the floating buffer for drag-positioning.

    The clicked cell becomes the anchor (stays under the cursor). Pushes
    history so a cancel can roll back the source clear cleanly.
    """
    if state.selection is None:
        return False
    if not click_in_selection(state.selection, click):
        return False
    sel = state.selection
    r0, r1 = sorted((sel[0], sel[2]))
    c0, c1 = sorted((sel[1], sel[3]))
    ri, fc = click

    push_history(state)
    buf = get_selection(state.fabric, state.config, sel)
    state.floating = buf
    state.floating_origin = (r0, c0)
    state.floating_anchor = (ri - r0, fc - c0)
    state.floating_lifted = True
    state.selection = None
    state.clipboard = [row[:] for row in buf]
    state.clipboard_origin = (r0, c0)

    nrows = len(state.fabric)
    ncols = state.config.columns
    for r in range(r0, r1 + 1):
        if not (0 <= r < nrows):
            continue
        active = set(state.config.cols_for_row(r))
        for c in range(c0, c1 + 1):
            if c in active and 0 <= c < ncols:
                state.fabric[r][c] = 0
    return True


def commit_floating(state: EditorState) -> None:
    """Write the floating buffer to fabric at floating_origin and exit float mode."""
    if state.floating is None or state.floating_origin is None:
        return
    if not state.floating_lifted:
        push_history(state)
    paste_at(state.fabric, state.config, state.floating, *state.floating_origin)
    state.clipboard_origin = state.floating_origin
    state.floating = None
    state.floating_origin = None
    state.floating_anchor = (0, 0)
    state.floating_lifted = False


def cancel_floating(state: EditorState) -> None:
    """Drop the floating buffer; if lifted from a drag, restore the source."""
    if state.floating is None:
        return
    if state.floating_lifted:
        # Lift pushed history; undo restores the source. Then drop the redo
        # entry so the user doesn't see a phantom "redo lift" they never did.
        undo(state)
        if state.redo_stack:
            state.redo_stack.pop()
    state.floating = None
    state.floating_origin = None
    state.floating_anchor = (0, 0)
    state.floating_lifted = False


def nudge_floating(state: EditorState, dri: int, dfc: int) -> None:
    if state.floating_origin is None:
        return
    r, c = state.floating_origin
    state.floating_origin = (r + dri, c + dfc)


def set_floating_origin_from_hit(state: EditorState,
                                 hit: tuple[int, int]) -> None:
    """Position the floating buffer so its anchor cell sits under `hit`."""
    if state.floating is None:
        return
    dr, dc = state.floating_anchor
    state.floating_origin = (hit[0] - dr, hit[1] - dc)


def cut(state: EditorState) -> None:
    """Copy selection to clipboard then clear to background (index 0)."""
    if state.selection is None:
        return
    push_history(state)
    state.clipboard = get_selection(state.fabric, state.config, state.selection)
    r0, c0, r1, c1 = state.selection
    r0, r1 = sorted((r0, r1))
    c0, c1 = sorted((c0, c1))
    state.clipboard_origin = (r0, c0)
    for ri in range(r0, r1 + 1):
        if 0 <= ri < len(state.fabric):
            active = set(state.config.cols_for_row(ri))
            for fc in range(c0, c1 + 1):
                if fc in active and 0 <= fc < state.config.columns:
                    state.fabric[ri][fc] = 0


def copy(state: EditorState) -> None:
    if state.selection is None:
        return
    state.clipboard = get_selection(state.fabric, state.config, state.selection)
    r0, c0, *_ = state.selection
    state.clipboard_origin = (r0, c0)


# ─── History ───────────────────────────────────────────────────────────

def _snapshot(fabric: list[list[int]]) -> list[list[int]]:
    return [row[:] for row in fabric]


def push_history(state: EditorState) -> None:
    """Capture current fabric state; trims redo stack and caps history depth."""
    state.history.append(_snapshot(state.fabric))
    if len(state.history) > HISTORY_CAP:
        state.history.pop(0)
    state.redo_stack.clear()


def undo(state: EditorState) -> bool:
    if not state.history:
        return False
    state.redo_stack.append(_snapshot(state.fabric))
    prev = state.history.pop()
    # Replace in place so external references to state.fabric stay valid.
    for ri, row in enumerate(prev):
        state.fabric[ri] = list(row)
    return True


def redo(state: EditorState) -> bool:
    if not state.redo_stack:
        return False
    state.history.append(_snapshot(state.fabric))
    nxt = state.redo_stack.pop()
    for ri, row in enumerate(nxt):
        state.fabric[ri] = list(row)
    return True


# ─── Palette ───────────────────────────────────────────────────────────

def add_palette_color(palette: ColorPalette, hex_color: str,
                      name: str | None = None) -> int:
    """Append a color to the palette, or return existing index on duplicate hex."""
    hex_lower = hex_color.lower()
    for idx, col in palette.colors.items():
        if col.lower() == hex_lower:
            return idx
    idx = max(palette.colors.keys(), default=-1) + 1
    palette.colors[idx] = hex_color
    palette.names[idx] = name or f"Custom {idx}"
    palette.strokes[idx] = darken(hex_color)
    palette.text_colors[idx] = text_color_for(hex_color)
    return idx


def use_color(state: EditorState, idx: int) -> None:
    """Set active color and bump recent_colors (MRU, capped)."""
    state.active_color = idx
    if idx in state.recent_colors:
        state.recent_colors.remove(idx)
    state.recent_colors.insert(0, idx)
    del state.recent_colors[RECENT_COLORS_CAP:]


# ─── Overlay SVG ───────────────────────────────────────────────────────

def _bead_bounds(ri: int, fc: int, config: BeadConfig) -> tuple[float, float, float, float]:
    cx, cy = bead_center(ri, fc, config)
    bw, bh = config.bead_width, config.bead_height
    return cx - bw / 2, cy - bh / 2, bw, bh


def make_overlay_svg(state: EditorState, config: BeadConfig) -> str:
    """SVG fragment for the interactive_image foreground layer.

    Renders drag previews and active selection. Coordinates are in the same
    SVG viewBox space as the fabric image, so nothing is scaled.
    """
    frags: list[str] = []
    drag = state.drag
    if drag and drag.start_cell and drag.last_cell:
        sri, sfc = drag.start_cell
        eri, efc = drag.last_cell
        sx, sy = bead_center(sri, sfc, config)
        ex, ey = bead_center(eri, efc, config)
        if drag.tool == "line":
            frags.append(
                f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{ex:.1f}" y2="{ey:.1f}" '
                f'stroke="#1976d2" stroke-width="2" stroke-dasharray="4 4"/>'
            )
        elif drag.tool in ("rect", "rect_fill", "select"):
            x0, y0 = min(sx, ex), min(sy, ey)
            x1, y1 = max(sx, ex), max(sy, ey)
            stroke = "#1976d2" if drag.tool.startswith("rect") else "#d32f2f"
            frags.append(
                f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" '
                f'height="{y1 - y0:.1f}" fill="none" stroke="{stroke}" '
                f'stroke-width="2" stroke-dasharray="4 4"/>'
            )
        elif drag.tool == "circle":
            dx, dy = ex - sx, ey - sy
            r = (dx * dx + dy * dy) ** 0.5
            frags.append(
                f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="{r:.1f}" fill="none" '
                f'stroke="#1976d2" stroke-width="2" stroke-dasharray="4 4"/>'
            )

    if state.selection:
        r0, c0, r1, c1 = state.selection
        r0, r1 = sorted((r0, r1))
        c0, c1 = sorted((c0, c1))
        x0, y0, _, _ = _bead_bounds(r0, c0, config)
        x1, y1, bw, bh = _bead_bounds(r1, c1, config)
        frags.append(
            f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{x1 + bw - x0:.1f}" '
            f'height="{y1 + bh - y0:.1f}" fill="none" stroke="#d32f2f" '
            f'stroke-width="2" stroke-dasharray="6 4"/>'
        )

    if state.floating is not None and state.floating_origin is not None:
        o_ri, o_fc = state.floating_origin
        nrows = len(state.fabric)
        bw, bh = config.bead_width, config.bead_height
        slot = config.slot
        for dr, row in enumerate(state.floating):
            tr = o_ri + dr
            if not (0 <= tr < nrows):
                continue
            active = set(config.cols_for_row(tr))
            for dc, val in enumerate(row):
                if val is None:
                    continue
                tfc = o_fc + dc
                if tfc not in active:
                    continue
                color = state.palette.colors.get(val, '#cccccc')
                cx, cy = bead_center(tr, tfc, config)
                frags.append(
                    f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" '
                    f'rx="{bw / 2:.1f}" ry="{bh / 2:.1f}" '
                    f'fill="{color}" fill-opacity="0.85" '
                    f'stroke="#1976d2" stroke-width="0.6"/>'
                )
        nrows_buf = len(state.floating)
        ncols_buf = max((len(r) for r in state.floating), default=0)
        if nrows_buf and ncols_buf:
            x0 = PL + o_fc * slot
            y0 = PT + o_ri * bh / 2
            x1 = PL + (o_fc + ncols_buf - 1) * slot + bw
            y1 = PT + (o_ri + nrows_buf - 1) * bh / 2 + bh
            frags.append(
                f'<rect x="{x0:.1f}" y="{y0:.1f}" '
                f'width="{x1 - x0:.1f}" height="{y1 - y0:.1f}" '
                f'fill="none" stroke="#1976d2" stroke-width="2" '
                f'stroke-dasharray="6 4"/>'
            )
    return "".join(frags)


# ─── JSON I/O ──────────────────────────────────────────────────────────

def fabric_to_json(state: EditorState) -> str:
    return json.dumps(
        _state_to_dict(state.fabric, state.config, state.palette, state.title),
        indent=2,
    )


def fabric_from_json(json_str: str) -> tuple[list[list[int]], BeadConfig,
                                             ColorPalette, str]:
    return _dict_to_state(json.loads(json_str))
