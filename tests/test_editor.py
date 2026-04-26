"""Unit tests for peyote.editor — pure logic, no NiceGUI."""

from peyote.colors import ColorPalette
from peyote.editor import (
    EditorState, add_palette_color, bead_center, clear_fabric,
    cut, fabric_from_json, fabric_to_json, flood_fill, get_selection,
    hit_test, paint_circle, paint_line, paint_pencil, paint_rect,
    paste_at, push_history, redo, undo, use_color,
)
from peyote.grid import blank_grid
from peyote.sizing import BeadConfig


def _make_state(columns=20, rows=40, active_color=1):
    config = BeadConfig(columns=columns, rows=rows)
    fabric = blank_grid(config, fill=0)
    palette = ColorPalette.from_pairs([("#ffffff", "White"), ("#000000", "Black")])
    state = EditorState(
        fabric=fabric, config=config, palette=palette, title="t",
        snapshot=[r[:] for r in fabric],
        snapshot_palette=ColorPalette.from_pairs([("#ffffff", "White")]),
        active_color=active_color,
    )
    return state


# ─── hit_test ──────────────────────────────────────────────────────────

def test_hit_test_dead_center():
    config = BeadConfig(columns=20, rows=40)
    fabric = blank_grid(config)
    # Row 0 (N=1, odd), fabric col 1 — center should hit
    cx, cy = bead_center(0, 1, config)
    assert hit_test(cx, cy, fabric, config) == (0, 1)
    # Row 1 (N=2, even), fabric col 0 — center should hit
    cx, cy = bead_center(1, 0, config)
    assert hit_test(cx, cy, fabric, config) == (1, 0)


def test_hit_test_all_quadrants():
    config = BeadConfig(columns=20, rows=40)
    fabric = blank_grid(config)
    # Row 0,N=1 odd → odd fcs active; row 39,N=40 even → even fcs active.
    for ri, fc in [(0, 1), (0, 19), (39, 0), (39, 18)]:
        cx, cy = bead_center(ri, fc, config)
        assert hit_test(cx, cy, fabric, config) == (ri, fc)


def test_hit_test_just_inside_edge():
    config = BeadConfig(columns=20, rows=40)
    fabric = blank_grid(config)
    # Row 5 is N=6, even → even fcs active. Use fc=4.
    cx, cy = bead_center(5, 4, config)
    eps = 0.1
    hw, hh = config.bead_width / 2 - eps, config.bead_height / 2 - eps
    for dx, dy in [(hw, 0), (-hw, 0), (0, hh), (0, -hh)]:
        assert hit_test(cx + dx, cy + dy, fabric, config) == (5, 4)


def test_hit_test_gutter_returns_none():
    config = BeadConfig(columns=20, rows=40)
    fabric = blank_grid(config)
    # A click midway between row-0 beads at fc=1 and fc=3, at y=PT (top edge
    # of row 0), is above row 1 and between beads on row 0 — a true gutter.
    cx_1, _ = bead_center(0, 1, config)
    cx_3, _ = bead_center(0, 3, config)
    gx = (cx_1 + cx_3) / 2
    from peyote.editor import PT
    assert hit_test(gx, PT, fabric, config) is None


def test_hit_test_outside_both_parities():
    config = BeadConfig(columns=20, rows=40)
    fabric = blank_grid(config)
    # Y midway between rows 0 and 1, X at a position that's in a gutter
    # for both parities (halfway between their bead centers).
    _, y0 = bead_center(0, 1, config)
    _, y1 = bead_center(1, 0, config)
    cy = (y0 + y1) / 2
    # This cy should still be valid (rows overlap), but choose x far off-grid
    assert hit_test(-50, cy, fabric, config) is None


def test_hit_test_single_row_edge():
    config = BeadConfig(columns=10, rows=1)
    fabric = blank_grid(config)
    cx, cy = bead_center(0, 1, config)
    assert hit_test(cx, cy, fabric, config) == (0, 1)
    cx, cy = bead_center(0, 9, config)
    assert hit_test(cx, cy, fabric, config) == (0, 9)


def test_hit_test_last_row():
    config = BeadConfig(columns=10, rows=5)
    fabric = blank_grid(config)
    cx, cy = bead_center(4, 1, config)  # N=5, odd
    assert hit_test(cx, cy, fabric, config) == (4, 1)


# ─── Odd-count peyote ──────────────────────────────────────────────────

def test_odd_columns_r1_has_higher_count():
    """Odd-count peyote: R1 must have the larger bead count for the
    turnaround to work. Parity flips relative to even-count."""
    config = BeadConfig(columns=11, rows=4)
    assert config.cols_for_row(0) == [0, 2, 4, 6, 8, 10]   # R1: 6 beads
    assert config.cols_for_row(1) == [1, 3, 5, 7, 9]       # R2: 5 beads
    assert config.cols_for_row(2) == [0, 2, 4, 6, 8, 10]   # R3: 6
    assert config.cols_for_row(3) == [1, 3, 5, 7, 9]       # R4: 5


def test_even_columns_unchanged():
    """Sanity-check that switching odd_cols/even_cols didn't break the
    long-standing even-count layout."""
    config = BeadConfig(columns=10, rows=2)
    assert config.cols_for_row(0) == [1, 3, 5, 7, 9]
    assert config.cols_for_row(1) == [0, 2, 4, 6, 8]


def test_hit_test_odd_columns_r1_first_and_last():
    """Both edge beads in R1 should be reachable when columns is odd —
    R1 owns col 0 and col columns-1."""
    config = BeadConfig(columns=11, rows=4)
    fabric = blank_grid(config)
    for fc in (0, 2, 4, 6, 8, 10):
        cx, cy = bead_center(0, fc, config)
        assert hit_test(cx, cy, fabric, config) == (0, fc)


def test_hit_test_odd_columns_r2_offset():
    """R2 beads on odd-count strip live at fc=1,3,...,columns-2."""
    config = BeadConfig(columns=11, rows=4)
    fabric = blank_grid(config)
    for fc in (1, 3, 5, 7, 9):
        cx, cy = bead_center(1, fc, config)
        assert hit_test(cx, cy, fabric, config) == (1, fc)


def test_paint_pencil_odd_columns_active_cells():
    """fc=0 is active on R1 and inactive on R2 when columns is odd."""
    config = BeadConfig(columns=11, rows=4)
    fabric = blank_grid(config)
    palette = ColorPalette.from_pairs([("#ffffff", "W"), ("#000000", "B")])
    state = EditorState(
        fabric=fabric, config=config, palette=palette, title="t",
        snapshot=[r[:] for r in fabric],
        snapshot_palette=ColorPalette.from_pairs([("#ffffff", "W")]),
        active_color=1,
    )
    assert paint_pencil(state, 0, 0) is True   # R1 col 0 active
    assert paint_pencil(state, 1, 0) is False  # R2 col 0 inactive
    assert paint_pencil(state, 0, 10) is True  # R1 col 10 active


# ─── paint_* ────────────────────────────────────────────────────────────

def test_paint_pencil_writes_and_idempotent():
    state = _make_state()
    assert paint_pencil(state, 0, 1) is True
    assert state.fabric[0][1] == 1
    # Second call returns False (no change)
    assert paint_pencil(state, 0, 1) is False


def test_paint_pencil_rejects_inactive_cell():
    state = _make_state()
    # Row 0 (N=1, odd) — fc=0 is inactive
    assert paint_pencil(state, 0, 0) is False
    assert state.fabric[0][0] == 0


def test_paint_line_horizontal_active_only():
    state = _make_state()
    # Horizontal line across row 0 (odd): active fcs are 1,3,5,...
    paint_line(state.fabric, state.config, (0, 1), (0, 11), color=1)
    # Every odd fc from 1..11 should be 1
    assert all(state.fabric[0][fc] == 1 for fc in (1, 3, 5, 7, 9, 11))
    # Even cells should remain 0
    assert all(state.fabric[0][fc] == 0 for fc in (0, 2, 4, 6, 8, 10))


def test_paint_line_diagonal():
    state = _make_state()
    paint_line(state.fabric, state.config, (0, 1), (4, 5), color=1)
    # At least the endpoints should be painted
    assert state.fabric[0][1] == 1
    assert state.fabric[4][5] == 1


def test_paint_rect_outline_vs_fill():
    state = _make_state()
    # Outline rect, ri 2..4, fc 1..5 (all active — odd rows have odd fc, even rows have even fc)
    paint_rect(state.fabric, state.config, (2, 1), (4, 5), color=1, fill=False)
    outlined = sum(row.count(1) for row in state.fabric)

    state2 = _make_state()
    paint_rect(state2.fabric, state2.config, (2, 1), (4, 5), color=1, fill=True)
    filled = sum(row.count(1) for row in state2.fabric)

    assert outlined > 0
    assert filled > outlined


def test_paint_circle_writes_pixels():
    state = _make_state()
    # Circle on a 20x40 grid
    paint_circle(state.fabric, state.config, (20, 11), (20, 15), color=1)
    written = sum(row.count(1) for row in state.fabric)
    assert written > 0


def test_flood_fill_respects_adjacency():
    state = _make_state()
    # Paint an isolated cell; flood fill should only fill reachable region
    state.fabric[0][1] = 0  # already 0
    flood_fill(state.fabric, state.config, 0, 1, color=1)
    # All active cells should flip to 1 (fully connected blank fabric)
    total_active = 0
    for ri in range(state.config.rows):
        for fc in state.config.cols_for_row(ri):
            total_active += 1
            assert state.fabric[ri][fc] == 1


def test_flood_fill_stops_at_boundary():
    state = _make_state()
    # Draw a horizontal barrier on row 5
    for fc in state.config.cols_for_row(5):
        state.fabric[5][fc] = 2
    # Also block row 4 — peyote neighbours are (ri±1, fc±1); barrier on
    # adjacent rows above and below row 6 isolates row 6+.
    # Actually: flood from (0,1). Neighbours include (1, fc±1). The barrier
    # on row 5 blocks traversal through any row-5 cell (since color != orig).
    flood_fill(state.fabric, state.config, 0, 1, color=1)
    # Row 6+ should remain 0
    for ri in range(6, state.config.rows):
        for fc in state.config.cols_for_row(ri):
            assert state.fabric[ri][fc] == 0, f"leak at ({ri},{fc})"
    # Rows 0..4 should be 1
    for ri in range(5):
        for fc in state.config.cols_for_row(ri):
            assert state.fabric[ri][fc] == 1


def test_clear_fabric_sets_all_cells():
    state = _make_state()
    clear_fabric(state.fabric, 3)
    assert all(v == 3 for row in state.fabric for v in row)


# ─── Palette ───────────────────────────────────────────────────────────

def test_add_palette_color_dedupes():
    palette = ColorPalette.from_pairs([("#ffffff", "W"), ("#000000", "B")])
    idx_a = add_palette_color(palette, "#ff0000", "Red")
    assert idx_a == 2
    # Same hex (different case) returns existing
    idx_b = add_palette_color(palette, "#FF0000")
    assert idx_b == idx_a
    assert len(palette.colors) == 3


def test_add_palette_color_generates_stroke_and_text_color():
    palette = ColorPalette.from_pairs([("#ffffff", "W")])
    idx = add_palette_color(palette, "#ff0000")
    assert idx in palette.strokes
    assert idx in palette.text_colors
    assert palette.names[idx] == "Custom 1"


def test_use_color_bumps_recent_mru():
    state = _make_state()
    use_color(state, 1)
    use_color(state, 2)
    use_color(state, 1)  # re-select
    assert state.recent_colors[0] == 1
    assert state.recent_colors[1] == 2
    assert state.active_color == 1


# ─── History ───────────────────────────────────────────────────────────

def test_push_history_and_undo_roundtrip():
    state = _make_state()
    for i in range(5):
        push_history(state)
        paint_pencil(state, i, i * 2 + 1 if (i + 1) % 2 == 1 else i * 2)
    # Current: 5 mutations done, history has 5 entries
    for _ in range(5):
        assert undo(state) is True
    # After 5 undos, fabric should be empty again
    assert all(v == 0 for row in state.fabric for v in row)


def test_redo_replays_mutations():
    state = _make_state()
    push_history(state)
    paint_pencil(state, 0, 1)
    assert state.fabric[0][1] == 1
    undo(state)
    assert state.fabric[0][1] == 0
    redo(state)
    assert state.fabric[0][1] == 1


def test_new_mutation_clears_redo_stack():
    state = _make_state()
    push_history(state)
    paint_pencil(state, 0, 1)
    undo(state)
    push_history(state)  # starts a new branch — redo should be cleared
    assert state.redo_stack == []


# ─── Selection / clipboard ─────────────────────────────────────────────

def test_get_selection_inactive_cells_are_none():
    state = _make_state()
    paint_pencil(state, 0, 1)
    paint_pencil(state, 1, 0)
    sel = get_selection(state.fabric, state.config, (0, 0, 1, 1))
    # Row 0 (odd-N): fc 0 inactive → None, fc 1 active
    assert sel[0][0] is None
    assert sel[0][1] == 1
    # Row 1 (even-N): fc 0 active, fc 1 inactive → None
    assert sel[1][0] == 1
    assert sel[1][1] is None


def test_cut_and_paste_roundtrip():
    state = _make_state()
    paint_pencil(state, 0, 1)
    paint_pencil(state, 0, 3)
    state.selection = (0, 1, 0, 3)
    cut(state)
    # After cut, those cells are 0
    assert state.fabric[0][1] == 0
    assert state.fabric[0][3] == 0
    # Paste back at original position
    paste_at(state.fabric, state.config, state.clipboard, 0, 1)
    assert state.fabric[0][1] == 1
    assert state.fabric[0][3] == 1


# ─── JSON I/O ──────────────────────────────────────────────────────────

def test_json_roundtrip_identity():
    state = _make_state()
    # Make a non-trivial pattern
    paint_pencil(state, 0, 1)
    paint_pencil(state, 5, 4)
    paint_pencil(state, 10, 9)

    s = fabric_to_json(state, progress_row=7)
    fabric2, config2, palette2, title2, progress2 = fabric_from_json(s)
    assert fabric2 == state.fabric
    assert config2.columns == state.config.columns
    assert config2.rows == state.config.rows
    assert palette2.colors == state.palette.colors
    assert title2 == state.title
    assert progress2 == 7
