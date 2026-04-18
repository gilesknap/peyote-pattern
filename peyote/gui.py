"""NiceGUI-based peyote pattern designer."""

import base64
import copy
import io
import json as json_mod
from pathlib import Path

from nicegui import app, ui

from peyote import editor as ed
from peyote.colors import PALETTE_DEFS, ColorPalette, darken
from peyote.compose import (
    compose_pattern_only,
    compose_text_with_background,
    compose_text_with_border,
)
from peyote.export import _dict_to_state, _state_to_dict, render_combined_png
from peyote.font import text_to_fabric
from peyote.font_ttf import DEFAULT_FONT_NAME, available_fonts, resolve_font
from peyote.grid import count_beads
from peyote.patterns import (
    SINGLE_COLOR_PATTERNS,
    TWO_COLOR_PATTERNS,
    pattern_repeat_default,
    pattern_repeat_kwargs,
)
from peyote.renderer import (
    make_fabric_svg,
    make_pattern_svg,
    pattern_checkbox_bounds,
)
from peyote.sizing import PRESETS, BeadConfig


STORAGE_KEY = 'peyote_state_v1'

# Keys in `state` that are persisted across browser sessions. Excludes derived
# (_fabric/_config/_palette/_title), transient (editor, _syncing, mode), and
# the custom edit which is persisted separately as 'custom_state'.
PERSISTED_KEYS = (
    'text', 'preset', 'columns', 'rows', 'layout', 'pattern',
    'margin', 'gap', 'repeat', 'font_mode', 'font_name', 'rotate',
    'palette_name', 'bg_color', 'text_color', 'accent1_color', 'accent2_color',
    'zoom', 'editor_zoom', 'save_filename', 'save_folder',
    'progress_row', 'custom',
)


TOOL_ICONS = [
    ('pencil', 'edit', 'Pencil'),
    ('line', 'show_chart', 'Line'),
    ('rect', 'crop_square', 'Rectangle'),
    ('rect_fill', 'stop', 'Filled Rectangle'),
    ('circle', 'radio_button_unchecked', 'Circle'),
    ('select', 'select_all', 'Select'),
    ('fill', 'format_color_fill', 'Bucket Fill'),
    ('eyedropper', 'colorize', 'Eyedropper'),
]


def build_fabric(text, preset, columns, rows, layout, pattern_name,
                 font_mode, rotate, margin,
                 bg_color, text_color, accent1_color, accent2_color,
                 font_path=None, gap=2, repeat=None):
    """Build fabric grid and palette from current settings."""
    # Config
    if preset != 'custom':
        p = PRESETS[preset]
        config = BeadConfig(columns=p.columns, rows=rows or p.rows)
    else:
        config = BeadConfig(columns=columns, rows=rows)

    # Palette slot layout depends on whether text is present:
    #   Text Only               → bg, text
    #   Pattern Only            → bg, accent1, accent2  (patterns emit 1/2 natively)
    #   Text + Border/Background → bg, text, accent1, accent2 (patterns shifted to 2/3)
    if layout == 'Text Only':
        palette = ColorPalette.two_color(bg_color, text_color, fg_name='Text')
    elif layout == 'Pattern Only':
        palette = ColorPalette.three_color(bg_color, accent1_color, accent2_color)
    else:
        palette = ColorPalette.four_color(bg_color, text_color,
                                          accent1_color, accent2_color)

    repeat_kwargs = pattern_repeat_kwargs(pattern_name, repeat)

    # Fabric
    if layout == 'Text Only':
        fabric = text_to_fabric(text or 'TASH', config, font_mode=font_mode,
                                font_path=font_path, rotate=rotate, margin=margin)
        title = text or 'Pattern'
    elif layout in ('Text + Border', 'Text + Border Wrap'):
        fabric = compose_text_with_border(
            text or 'TASH', config,
            border_pattern=pattern_name,
            font_mode=font_mode, font_path=font_path, rotate=rotate,
            margin=margin, gap=gap,
            wrap_border=(layout == 'Text + Border Wrap'),
            **repeat_kwargs)
        title = text or 'Pattern'
    elif layout == 'Text + Background':
        fabric = compose_text_with_background(
            text or 'TASH', config,
            background_pattern=pattern_name,
            font_mode=font_mode, font_path=font_path, rotate=rotate, margin=margin,
            **repeat_kwargs)
        title = text or 'Pattern'
    elif layout == 'Pattern Only':
        fabric = compose_pattern_only(pattern_name, config, **repeat_kwargs)
        title = f'{pattern_name} pattern'
    else:
        fabric = text_to_fabric(text or 'TASH', config, font_mode=font_mode,
                                font_path=font_path, rotate=rotate, margin=margin)
        title = text or 'Pattern'

    return fabric, config, palette, title


def render_to_bytes(fabric, title, config, palette, view='fabric'):
    """Render to PNG bytes (for downloads)."""
    img = render_combined_png(fabric, title, config, palette, view=view)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def render_svg(fabric, title, config, palette, view='fabric',
               progress_through: int = 0) -> str:
    """Render SVG string directly (for live browser preview — skips cairosvg)."""
    if view == 'pattern':
        svg, _, _ = make_pattern_svg(fabric, title, config, palette,
                                     progress_through=progress_through)
    else:
        svg, _, _ = make_fabric_svg(fabric, title, config, palette)
    return svg


def _svg_data_url(svg: str) -> str:
    return f'data:image/svg+xml;base64,{base64.b64encode(svg.encode()).decode()}'


@ui.page('/')
def create_ui():
    # State defaults
    _default_preset = 'ring'
    _default_preset_config = PRESETS[_default_preset]
    state = {
        'text': 'TASH',
        'preset': _default_preset,
        'columns': _default_preset_config.columns,
        'rows': _default_preset_config.rows,
        'layout': 'Pattern Only',
        'pattern': 'kinetic',
        'margin': 0,
        'gap': 2,
        'repeat': 12,  # inert when pattern has no period
        'font_mode': 'auto',  # kept for build_fabric compat
        'font_name': DEFAULT_FONT_NAME,
        'rotate': True,
        'palette_name': 'classic',
        # Classic palette: Pink / Red + a darkened Red for Accent 2
        'bg_color': '#E8A0A8',
        'text_color': '#C82020',
        'accent1_color': '#C82020',
        'accent2_color': '#781313',
        'zoom': 300,  # px max-width per image
        'editor_zoom': 600,     # px width for the editor canvas (2× procedural default)
        'mode': 'procedural',   # or 'editor'
        'editor': None,         # ed.EditorState when in editor mode
        'save_filename': None,  # full path; set after first save, reused on subsequent saves
        'save_folder': None,    # last folder chosen in the save dialog
        'custom': False,        # True once editor edits have been kept
        '_syncing': False,      # guards cascading set_value() -> on_change loops
        'progress_row': 0,      # rows 1..progress_row are marked complete in pattern view
    }

    # ── Persistence ───────────────────────────────────────────────────
    def persist_state():
        """Write the current session to app.storage.user."""
        try:
            data = {k: state[k] for k in PERSISTED_KEYS if k in state}
            if state.get('custom') and state.get('_fabric') is not None:
                data['custom_state'] = _state_to_dict(
                    state['_fabric'], state['_config'],
                    state['_palette'], state.get('_title', ''),
                    state.get('progress_row', 0),
                )
            app.storage.user[STORAGE_KEY] = data
        except Exception:
            # Storage is best-effort; never break the UI if it's unavailable.
            pass

    def restore_state():
        """Load any saved session into `state`. Returns True if custom_state was restored."""
        data = app.storage.user.get(STORAGE_KEY)
        if not isinstance(data, dict):
            return False
        for k in PERSISTED_KEYS:
            if k in data:
                state[k] = data[k]
        cs = data.get('custom_state')
        if state.get('custom') and isinstance(cs, dict):
            try:
                fabric, config, palette, title, progress = _dict_to_state(cs)
            except Exception:
                return False
            state['_fabric'] = fabric
            state['_config'] = config
            state['_palette'] = palette
            state['_title'] = title
            # progress_row already came from PERSISTED_KEYS, but prefer the
            # custom_state value if present (they should agree).
            state['progress_row'] = progress
            return True
        return False

    def update_preview(reset_progress: bool = True):
        # In editor mode, procedural changes are suppressed — the editor
        # owns the fabric. Controls are disabled, but an in-flight change
        # event from a widget transition shouldn't stomp edits.
        if state['mode'] == 'editor':
            return
        try:
            fabric, config, palette, title = build_fabric(
                state['text'], state['preset'], state['columns'], state['rows'],
                state['layout'], state['pattern'],
                state['font_mode'], state['rotate'], state['margin'],
                state['bg_color'], state['text_color'],
                state['accent1_color'], state['accent2_color'],
                font_path=resolve_font(state['font_name']),
                gap=state['gap'], repeat=state['repeat'])

            # Regenerating from procedural settings wipes any kept custom edits
            # and the user's tick-off progress on the pattern view. The initial
            # restore from browser storage passes reset_progress=False so the
            # ticked-off rows survive a refresh.
            state['custom'] = False
            if reset_progress:
                state['progress_row'] = 0

            fabric_svg = render_svg(fabric, title, config, palette, view='fabric')
            fabric_img.set_source(_svg_data_url(fabric_svg))

            pat_svg = render_svg(fabric, title, config, palette, view='pattern',
                                 progress_through=state['progress_row'])
            pattern_img.set_source(_svg_data_url(pat_svg))

            z = state['zoom']
            fabric_container.style(f'width: {z}px;')
            pattern_container.style(f'width: {z}px;')

            # Store for downloads / editor snapshots
            state['_fabric'] = fabric
            state['_config'] = config
            state['_palette'] = palette
            state['_title'] = title

            refresh_bead_count(fabric, config, palette)
            persist_state()

        except Exception as e:
            bead_count_container.clear()
            with bead_count_container:
                ui.label(f'Error: {e}').classes('text-red')

    def refresh_bead_count(fabric, config, palette):
        counts = count_beads(fabric, config)
        total = sum(counts.values())
        bead_count_container.clear()
        with bead_count_container:
            ui.label(f'{config.columns} beads per row').classes(
                'text-caption text-grey-7')
            for idx in sorted(counts.keys()):
                name = palette.names.get(idx, f'Color {idx}')
                fill = palette.colors.get(idx, '#cccccc')
                with ui.row().classes('w-full items-center gap-2 no-wrap'):
                    ui.element('div').style(
                        f'width: 14px; height: 14px; border-radius: 3px; '
                        f'background: {fill}; '
                        f'border: 1px solid rgba(0,0,0,0.2); flex-shrink: 0;'
                    )
                    ui.label(name).classes('flex-1').style('min-width: 0;')
                    ui.label(f'{counts[idx]}')
            ui.separator()
            with ui.row().classes('w-full items-center gap-2 no-wrap'):
                ui.label('Total').classes('flex-1 font-bold')
                ui.label(f'{total}').classes('font-bold')

    # ── Editor mode plumbing ──────────────────────────────────────────
    def refresh_fabric_from_editor():
        es = state['editor']
        svg = render_svg(es.fabric, es.title, es.config, es.palette,
                         view='fabric')
        fabric_img.set_source(_svg_data_url(svg))
        fabric_img.content = ed.make_overlay_svg(es, es.config)
        refresh_bead_count(es.fabric, es.config, es.palette)

    def enter_editor():
        if state.get('_fabric') is None:
            return
        es = ed.EditorState(
            fabric=[row[:] for row in state['_fabric']],
            config=state['_config'],
            palette=copy.deepcopy(state['_palette']),
            title=state['_title'],
            snapshot=[row[:] for row in state['_fabric']],
            snapshot_palette=copy.deepcopy(state['_palette']),
            active_color=1 if 1 in state['_palette'].colors else 0,
        )
        state['editor'] = es
        state['mode'] = 'editor'
        state['save_filename'] = None
        state['editor_zoom'] = max(200, min(2000, state['zoom'] * 2))
        fabric_container.style(f'width: {state["editor_zoom"]}px;')
        edit_button.set_visibility(False)
        procedural_panel.set_visibility(False)
        editor_panel.set_visibility(True)
        pattern_container.set_visibility(False)
        build_editor_panel()
        refresh_fabric_from_editor()

    def exit_to_procedural():
        state['mode'] = 'procedural'
        state['editor'] = None
        edit_button.set_visibility(True)
        procedural_panel.set_visibility(True)
        editor_panel.set_visibility(False)
        pattern_container.set_visibility(True)
        fabric_container.style(f'width: {state["zoom"]}px;')
        fabric_img.content = ''

    def render_current():
        """Re-render fabric/pattern images from state['_fabric'] without regenerating."""
        if not state.get('_fabric'):
            return
        fabric_svg = render_svg(state['_fabric'], state['_title'],
                                state['_config'], state['_palette'],
                                view='fabric')
        fabric_img.set_source(_svg_data_url(fabric_svg))
        pat_svg = render_svg(state['_fabric'], state['_title'],
                             state['_config'], state['_palette'],
                             view='pattern',
                             progress_through=state['progress_row'])
        pattern_img.set_source(_svg_data_url(pat_svg))
        refresh_bead_count(state['_fabric'], state['_config'],
                           state['_palette'])

    def rerender_pattern():
        """Re-render pattern image only (honours current progress_row)."""
        if not state.get('_fabric'):
            return
        pat_svg = render_svg(state['_fabric'], state['_title'],
                             state['_config'], state['_palette'],
                             view='pattern',
                             progress_through=state['progress_row'])
        pattern_img.set_source(_svg_data_url(pat_svg))

    def on_pattern_click(e):
        # Only act on the initial mouse-down of a click — ignore drag/move.
        if e.type != 'mousedown':
            return
        if not state.get('_fabric'):
            return
        x, y = e.image_x, e.image_y
        bounds = pattern_checkbox_bounds(state['_fabric'], state['_config'])
        for N_click, cx, cy, sz in bounds:
            if cx <= x <= cx + sz and cy <= y <= cy + sz:
                current = state['progress_row']
                # Toggle: ticking a checked box unwinds to one row below
                # (or to 0 for the merged R1+2). Ticking an unchecked box
                # sets progress to that row — all boxes above are ticked too.
                if current >= N_click:
                    state['progress_row'] = 0 if N_click <= 2 else N_click - 1
                else:
                    state['progress_row'] = N_click
                rerender_pattern()
                persist_state()
                return

    def done_editor():
        es = state['editor']
        if es is not None:
            state['_fabric'] = es.fabric
            state['_palette'] = es.palette
            state['_title'] = es.title
            state['custom'] = True
        exit_to_procedural()
        render_current()
        persist_state()

    def discard_editor():
        # Throw away the editor session. state['_fabric'] still holds the
        # pre-edit pattern (procedural OR a previously kept custom edit), so
        # just re-render — don't regenerate from procedural settings.
        exit_to_procedural()
        render_current()

    def has_editor_changes() -> bool:
        es = state['editor']
        if es is None:
            return False
        if es.fabric != es.snapshot:
            return True
        return es.palette.colors != es.snapshot_palette.colors

    def _default_save_folder() -> Path:
        if state.get('save_folder'):
            return Path(state['save_folder']).expanduser()
        downloads = Path.home() / 'Downloads'
        return downloads if downloads.is_dir() else Path.home()

    def _resolve_save_path(folder: str, name: str) -> Path:
        name = name.strip()
        if not name.lower().endswith('.json'):
            name += '.json'
        base = Path(folder).expanduser() if folder.strip() else _default_save_folder()
        return (base / name).expanduser().resolve()

    def _current_pattern_sources():
        """Return (fabric, config, palette, title, progress_row) for saving.

        Prefers the live editor when in editor mode, else the outer procedural
        or custom fabric. Returns None if nothing has been rendered yet.
        """
        es = state.get('editor')
        if es is not None:
            return (es.fabric, es.config, es.palette, es.title,
                    state.get('progress_row', 0))
        fabric = state.get('_fabric')
        if fabric is None:
            return None
        return (fabric, state['_config'], state['_palette'],
                state.get('_title', ''), state.get('progress_row', 0))

    def _write_pattern_json(path: Path) -> None:
        src = _current_pattern_sources()
        if src is None:
            return
        fabric, config, palette, title, progress_row = src
        payload = _state_to_dict(fabric, config, palette, title, progress_row)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json_mod.dumps(payload, indent=2), encoding='utf-8')
        except OSError as err:
            ui.notify(f'Save failed: {err}', type='negative')
            return
        ui.notify(f'Saved {path}', type='positive')

    def _confirm_overwrite_then(path: Path, on_confirm) -> None:
        if not path.exists():
            on_confirm()
            return
        with ui.dialog() as dlg, ui.card():
            ui.label(f'{path} already exists.').classes('text-subtitle1')
            ui.label('Overwrite?').classes('text-body2')
            with ui.row().classes('w-full justify-end gap-2'):
                ui.button('Cancel', on_click=dlg.close).props('flat')

                def yes():
                    dlg.close()
                    on_confirm()

                ui.button('Overwrite', on_click=yes).props('color=negative')
        dlg.open()

    def prompt_save_filename(after_save) -> None:
        """Ask for folder + filename, write JSON (with overwrite confirm), then call after_save()."""
        src = _current_pattern_sources()
        src_title = src[3] if src else ''
        default_name = src_title if src_title else 'peyote-pattern'
        # Pre-populate from the last save when re-prompting, else default folder.
        if state.get('save_filename'):
            prev = Path(state['save_filename'])
            default_folder = str(prev.parent)
            default_name = prev.stem
        else:
            default_folder = str(_default_save_folder())
        with ui.dialog() as dlg, ui.card():
            ui.label('Save pattern as').classes('text-subtitle1')
            folder_input = ui.input(label='Folder', value=default_folder).props(
                'outlined dense').classes('w-full').style('min-width: 360px;')
            name_input = ui.input(label='Filename', value=default_name).props(
                'outlined dense').classes('w-full')
            with ui.row().classes('w-full justify-end gap-2'):
                ui.button('Cancel', on_click=dlg.close).props('flat')

                def confirm():
                    name = (name_input.value or default_name).strip()
                    if not name:
                        return
                    folder = folder_input.value or ''
                    path = _resolve_save_path(folder, name)
                    dlg.close()

                    def do_save():
                        state['save_filename'] = str(path)
                        state['save_folder'] = str(path.parent)
                        _write_pattern_json(path)
                        persist_state()
                        after_save()

                    _confirm_overwrite_then(path, do_save)

                ui.button('Save', on_click=confirm).props('color=primary')
        dlg.open()

    def save_pattern_json(after_save=lambda: None) -> None:
        """Write JSON using the remembered path, or prompt on first save."""
        name = state.get('save_filename')
        if not name:
            prompt_save_filename(after_save)
            return
        path = Path(name)

        def do_save():
            _write_pattern_json(path)
            after_save()

        _confirm_overwrite_then(path, do_save)

    def request_close_editor():
        if not has_editor_changes():
            discard_editor()
            return
        with ui.dialog() as dlg, ui.card():
            ui.label('You have unsaved changes.').classes('text-subtitle1')
            with ui.row().classes('w-full justify-end gap-2'):
                ui.button('Cancel', on_click=dlg.close).props('flat')
                ui.button(
                    'Discard',
                    on_click=lambda: (dlg.close(), discard_editor()),
                ).props('flat color=negative')

                def save_and_close():
                    dlg.close()
                    save_pattern_json(done_editor)

                def save_as_and_close():
                    dlg.close()
                    prompt_save_filename(done_editor)

                ui.button('Save As', on_click=save_as_and_close).props('flat')
                ui.button('Save', on_click=save_and_close).props('color=primary')
        dlg.open()

    # ── Editor mouse handler ──────────────────────────────────────────
    def on_fabric_mouse(e):
        if state['mode'] != 'editor':
            return
        es = state['editor']
        if es is None:
            return
        hit = ed.hit_test(e.image_x, e.image_y, es.fabric, es.config)
        etype = e.type

        # Drag-move floating mode: mousemove tracks the cursor (anchor cell
        # stays under it), mouseup commits.
        if es.floating is not None:
            if etype == 'mousemove':
                if hit is None:
                    return
                dr, dc = es.floating_anchor
                new_origin = (hit[0] - dr, hit[1] - dc)
                if new_origin != es.floating_origin:
                    es.floating_origin = new_origin
                    refresh_fabric_from_editor()
            elif etype == 'mouseup':
                if hit:
                    ed.set_floating_origin_from_hit(es, hit)
                ed.commit_floating(es)
                refresh_fabric_from_editor()
            return

        if etype == 'mousedown':
            # Click inside an existing selection with the Select tool lifts
            # the selection into a floating buffer for drag-move.
            if (es.tool == 'select' and es.selection is not None
                    and hit is not None
                    and ed.click_in_selection(es.selection, hit)):
                if ed.lift_selection_for_drag(es, hit):
                    refresh_fabric_from_editor()
                    return
            es.drag = ed.DragState(tool=es.tool,
                                   start_cell=hit, last_cell=hit,
                                   color=es.active_color)
            if es.tool == 'pencil' and hit:
                ed.push_history(es)
                ed.paint_pencil(es, *hit)
                refresh_fabric_from_editor()
            elif es.tool == 'eyedropper' and hit:
                ri, fc = hit
                ed.use_color(es, es.fabric[ri][fc])
                build_editor_panel()
            elif es.tool == 'fill' and hit:
                ed.push_history(es)
                ed.flood_fill(es.fabric, es.config, *hit,
                              color=es.active_color)
                refresh_fabric_from_editor()
            elif es.tool == 'select':
                es.selection = None
                fabric_img.content = ''

        elif etype == 'mousemove' and es.drag is not None:
            if hit is None or hit == es.drag.last_cell:
                return
            if es.drag.tool == 'pencil':
                ed.paint_pencil(es, *hit)
                es.drag.last_cell = hit
                refresh_fabric_from_editor()
            elif es.drag.tool in ('line', 'rect', 'rect_fill', 'circle',
                                  'select'):
                es.drag.last_cell = hit
                fabric_img.content = ed.make_overlay_svg(es, es.config)

        elif etype == 'mouseup' and es.drag is not None:
            drag = es.drag
            es.drag = None
            if drag.start_cell and drag.last_cell and drag.tool != 'pencil':
                a, b = drag.start_cell, drag.last_cell
                if drag.tool == 'line':
                    ed.push_history(es)
                    ed.paint_line(es.fabric, es.config, a, b, es.active_color)
                elif drag.tool == 'rect':
                    ed.push_history(es)
                    ed.paint_rect(es.fabric, es.config, a, b,
                                  es.active_color, fill=False)
                elif drag.tool == 'rect_fill':
                    ed.push_history(es)
                    ed.paint_rect(es.fabric, es.config, a, b,
                                  es.active_color, fill=True)
                elif drag.tool == 'circle':
                    ed.push_history(es)
                    ed.paint_circle(es.fabric, es.config, a, b,
                                    es.active_color)
                elif drag.tool == 'select':
                    es.selection = (a[0], a[1], b[0], b[1])
            refresh_fabric_from_editor()

    # ── Export actions (procedural or custom fabric) ────────────────────
    def download_png():
        fabric = state.get('_fabric')
        if not fabric:
            return
        png = render_to_bytes(fabric, state['_title'], state['_config'],
                              state['_palette'], view='both')
        ui.download(png, 'peyote-pattern.png')

    def download_svg():
        fabric = state.get('_fabric')
        if not fabric:
            return
        svg_str, _, _ = make_fabric_svg(fabric, state['_title'],
                                        state['_config'], state['_palette'])
        ui.download(svg_str.encode('utf-8'), 'peyote-pattern.svg')

    def download_json():
        from peyote.export import _state_to_dict
        fabric = state.get('_fabric')
        if not fabric:
            return
        data = _state_to_dict(fabric, state['_config'], state['_palette'],
                              state['_title'])
        ui.download(json_mod.dumps(data, indent=2).encode(),
                    'peyote-pattern.json')

    # ── Layout ────────────────────────────────────────────────────────
    # Restore any prior session before widgets read state defaults.
    restored_custom = restore_state()

    ui.page_title('Peyote Pattern Designer')

    with ui.header().classes('bg-primary'):
        ui.label('Peyote Pattern Designer').classes('text-h5 text-white')

    def on_key(e):
        if not e.action.keydown:
            return
        if state['mode'] != 'editor':
            return
        es = state['editor']
        if es is None:
            return

        # Ctrl+X / C / V — clipboard shortcuts.
        if e.modifiers.ctrl and not e.modifiers.alt and not e.modifiers.meta:
            name = e.key.name.lower() if isinstance(e.key.name, str) else ''
            if name == 'x':
                ed.cut(es)
                refresh_fabric_from_editor()
                return
            if name == 'c':
                ed.copy(es)
                return
            if name == 'v':
                if ed.do_paste(es):
                    refresh_fabric_from_editor()
                return

        # Arrows: nudge the floating buffer if active, else the selection.
        if e.key.arrow_left:
            dri, dfc = 0, -2
        elif e.key.arrow_right:
            dri, dfc = 0, 2
        elif e.key.arrow_up:
            dri, dfc = -1, 0
        elif e.key.arrow_down:
            dri, dfc = 1, 0
        elif e.key.escape and es.floating is not None:
            ed.cancel_floating(es)
            refresh_fabric_from_editor()
            return
        elif e.key.enter and es.floating is not None:
            ed.commit_floating(es)
            refresh_fabric_from_editor()
            return
        else:
            return

        if es.floating is not None:
            ed.nudge_floating(es, dri, dfc)
            refresh_fabric_from_editor()
        elif es.selection is not None:
            if ed.move_selection(es, dri, dfc):
                fabric_img.content = ed.make_overlay_svg(es, es.config)

    ui.keyboard(on_key=on_key)

    with ui.row().classes('w-full flex-wrap'):
        with ui.column().classes('p-4 gap-2').style(
            'min-width: 280px; flex: 0 0 25%; max-width: 100%;'
        ):
            # Edit mode toggle — hides procedural panel and reveals the
            # editor toolbar. Hidden while the editor is open.
            edit_button = ui.button('Edit', icon='edit', on_click=enter_editor).props(
                'outlined').classes('w-full')

            # ─── Procedural panel ─────────────────────────────────────
            procedural_panel = ui.column().classes('w-full gap-2')
            with procedural_panel:
                # Size
                ui.label('Size').classes('text-subtitle1 font-bold')
                def on_preset_change(value):
                    state['preset'] = value
                    if value != 'custom':
                        p = PRESETS[value]
                        state['columns'] = p.columns
                        state['rows'] = p.rows
                        state['_syncing'] = True
                        try:
                            cols_input.set_value(p.columns)
                            rows_input.set_value(p.rows)
                        finally:
                            state['_syncing'] = False
                    update_preview()

                def on_cols_change(value):
                    if state['_syncing']:
                        return
                    new_cols = int(value) if value else 10
                    if new_cols == state['columns']:
                        return
                    state['columns'] = new_cols
                    state['preset'] = 'custom'
                    state['_syncing'] = True
                    try:
                        preset_select.set_value('custom')
                    finally:
                        state['_syncing'] = False
                    update_preview()

                def on_rows_change(value):
                    if state['_syncing']:
                        return
                    new_rows = int(value) if value else 72
                    if new_rows == state['rows']:
                        return
                    state['rows'] = new_rows
                    state['preset'] = 'custom'
                    state['_syncing'] = True
                    try:
                        preset_select.set_value('custom')
                    finally:
                        state['_syncing'] = False
                    update_preview()

                preset_select = ui.select(
                    list(PRESETS.keys()) + ['custom'],
                    value=state['preset'], label='Preset',
                    on_change=lambda e: (
                        None if state['_syncing'] else on_preset_change(e.value)
                    ),
                ).props('outlined dense').classes('w-full')

                with ui.row().classes('w-full gap-2'):
                    cols_input = ui.number('Cols', value=state['columns'],
                                           min=4, max=100, step=2,
                                           on_change=lambda e: on_cols_change(e.value),
                                           ).props('outlined dense').classes('flex-1')

                    rows_input = ui.number('Rows', value=state['rows'],
                                            min=10, max=500,
                                            on_change=lambda e: on_rows_change(e.value),
                                            ).props('outlined dense').classes('flex-1')

                    ui.number('Margin', value=state['margin'],
                              min=0, max=20,
                              on_change=lambda e: (
                                  state.update({'margin': int(e.value) if e.value else 0}),
                                  update_preview(),
                              )).props('outlined dense').classes('flex-1')

                # Content
                ui.label('Content').classes('text-subtitle1 font-bold mt-4')
                ui.select(
                    ['Text Only', 'Text + Border', 'Text + Border Wrap',
                     'Text + Background', 'Pattern Only'],
                    value=state['layout'], label='Layout',
                    on_change=lambda e: (
                        state.update({'layout': e.value}),
                        update_preview(),
                    )
                ).props('outlined dense').classes('w-full')

                ui.input('Text', value=state['text'],
                         on_change=lambda e: (
                             state.update({'text': e.value}),
                             update_preview(),
                         )).props('outlined dense').classes('w-full')

                ui.select(
                    available_fonts(),
                    value=state['font_name'], label='Font',
                    on_change=lambda e: (
                        state.update({'font_name': e.value}),
                        update_preview(),
                    )
                ).props('outlined dense').classes('w-full')

                ui.switch('Sideways text (rings)',
                          value=state['rotate'],
                          on_change=lambda e: (
                              state.update({'rotate': e.value}),
                              update_preview(),
                          ))

                def on_pattern_change(new_name):
                    state['pattern'] = new_name
                    # Snap Repeat back to the new pattern's natural default so
                    # users never inherit a stale value from the previous pick.
                    new_default = pattern_repeat_default(new_name)
                    if new_default is not None:
                        state['repeat'] = new_default
                        repeat_input.set_value(new_default)
                    update_preview()

                pattern_options = {
                    **{n: n for n in SINGLE_COLOR_PATTERNS},
                    **{n: f'{n}  (2-color)' for n in TWO_COLOR_PATTERNS},
                }

                with ui.row().classes('w-full gap-2 no-wrap'):
                    ui.select(
                        pattern_options,
                        value=state['pattern'], label='Pattern',
                        on_change=lambda e: on_pattern_change(e.value),
                    ).props('outlined dense').classes('flex-1')

                    ui.number('Gap', value=state['gap'],
                              min=0, max=20,
                              on_change=lambda e: (
                                  state.update({'gap': int(e.value) if e.value is not None else 2}),
                                  update_preview(),
                              )).props('outlined dense').style('width: 80px;')

                    repeat_input = ui.number('Repeat', value=state['repeat'],
                              min=1, max=100,
                              on_change=lambda e: (
                                  state.update({'repeat': int(e.value) if e.value is not None else 8}),
                                  update_preview(),
                              ))
                    repeat_input.props('outlined dense').style('width: 90px;')

                # Colors
                ui.label('Colors').classes('text-subtitle1 font-bold mt-4')

                def apply_palette(name):
                    colors = PALETTE_DEFS[name]
                    state['bg_color'] = colors[0][0]
                    state['text_color'] = colors[1][0]
                    accent1 = colors[2][0] if len(colors) > 2 else colors[1][0]
                    state['accent1_color'] = accent1
                    state['accent2_color'] = darken(accent1, factor=0.6)
                    bg_picker.set_value(state['bg_color'])
                    text_picker.set_value(state['text_color'])
                    accent1_picker.set_value(state['accent1_color'])
                    accent2_picker.set_value(state['accent2_color'])
                    update_preview()

                ui.select(
                    list(PALETTE_DEFS.keys()),
                    value=state['palette_name'], label='Palette',
                    on_change=lambda e: apply_palette(e.value),
                ).props('outlined dense').classes('w-full')

                bg_picker = ui.color_input('Background', value=state['bg_color'],
                                           on_change=lambda e: (
                                               state.update({'bg_color': e.value}),
                                               update_preview(),
                                           )).props('outlined dense').classes('w-full')
                text_picker = ui.color_input('Text', value=state['text_color'],
                                             on_change=lambda e: (
                                                 state.update({'text_color': e.value}),
                                                 update_preview(),
                                             )).props('outlined dense').classes('w-full')
                accent1_picker = ui.color_input('Accent 1', value=state['accent1_color'],
                                                on_change=lambda e: (
                                                    state.update({'accent1_color': e.value}),
                                                    update_preview(),
                                                )).props('outlined dense').classes('w-full')
                accent2_picker = ui.color_input('Accent 2', value=state['accent2_color'],
                                                on_change=lambda e: (
                                                    state.update({'accent2_color': e.value}),
                                                    update_preview(),
                                                )).props('outlined dense').classes('w-full')

                # Bead Count
                ui.label('Bead Count').classes('text-subtitle1 font-bold mt-4')
                bead_count_container = ui.column().classes('w-full gap-1').style(
                    'border: 1px solid rgba(0,0,0,0.24); border-radius: 4px; '
                    'padding: 8px 12px;'
                )

                # Downloads
                ui.label('Export').classes('text-subtitle1 font-bold mt-4')
                with ui.row().classes('w-full gap-1 no-wrap').style(
                    'border: 1px solid rgba(0,0,0,0.24); border-radius: 4px; '
                    'padding: 6px 8px;'
                ):
                    ui.button('PNG', on_click=download_png, icon='image').props(
                        'flat dense').classes('flex-1')
                    ui.button('SVG', on_click=download_svg, icon='code').props(
                        'flat dense').classes('flex-1')
                    ui.button('JSON', on_click=download_json,
                              icon='data_object').props('flat dense').classes('flex-1')

                # File (save/load pattern + progress)
                async def on_procedural_upload(e):
                    try:
                        text = await e.file.text()
                        fabric, config, palette, title, progress = (
                            ed.fabric_from_json(text))
                    except Exception as err:
                        ui.notify(f'Load failed: {err}', type='negative')
                        return
                    state['_fabric'] = fabric
                    state['_config'] = config
                    state['_palette'] = palette
                    state['_title'] = title
                    state['custom'] = True
                    state['progress_row'] = progress
                    state['save_filename'] = None
                    render_current()
                    persist_state()
                    ui.notify('Loaded pattern', type='positive')

                ui.label('File').classes('text-subtitle1 font-bold mt-4')
                with ui.column().classes('w-full gap-1').style(
                    'border: 1px solid rgba(0,0,0,0.24); border-radius: 4px; '
                    'padding: 6px 8px;'
                ):
                    ui.button('Save .json', icon='save',
                              on_click=lambda: save_pattern_json()
                              ).props('flat dense').classes('w-full')
                    ui.upload(label='Load .json',
                              on_upload=on_procedural_upload,
                              auto_upload=True,
                              ).props('accept=.json flat dense').classes('w-full')

                # Zoom
                def set_zoom(v):
                    v = max(100, min(800, int(v)))
                    if v == state['zoom']:
                        return
                    state['zoom'] = v
                    zoom_slider.value = v
                    update_preview()

                ui.label('Zoom').classes('text-subtitle1 font-bold mt-4')
                with ui.row().classes('w-full items-center gap-1 no-wrap').style(
                    'border: 1px solid rgba(0,0,0,0.24); border-radius: 4px; '
                    'padding: 4px 8px;'
                ):
                    ui.button(icon='remove',
                              on_click=lambda: set_zoom(state['zoom'] - 50)
                              ).props('flat dense round size=sm')
                    zoom_slider = ui.slider(
                        min=100, max=800, step=50, value=state['zoom'],
                        on_change=lambda e: set_zoom(e.value),
                    ).props('label').classes('flex-1')
                    ui.button(icon='add',
                              on_click=lambda: set_zoom(state['zoom'] + 50)
                              ).props('flat dense round size=sm')
                    ui.button(icon='refresh',
                              on_click=lambda: set_zoom(300)
                              ).props('flat dense round size=sm')

            # ─── Editor panel (hidden until Edit pressed) ─────────────
            editor_panel = ui.column().classes('w-full gap-2')
            editor_panel.set_visibility(False)

            def set_tool(name: str):
                es = state['editor']
                if es is None:
                    return
                es.tool = name
                if name != 'select':
                    es.selection = None
                build_editor_panel()
                refresh_fabric_from_editor()

            def set_active_color(idx: int):
                es = state['editor']
                if es is None:
                    return
                ed.use_color(es, idx)
                build_editor_panel()

            def add_custom_color(hex_color: str):
                es = state['editor']
                if es is None or not hex_color:
                    return
                idx = ed.add_palette_color(es.palette, hex_color)
                ed.use_color(es, idx)
                build_editor_panel()
                refresh_fabric_from_editor()

            def do_undo():
                es = state['editor']
                if es and ed.undo(es):
                    refresh_fabric_from_editor()

            def do_redo():
                es = state['editor']
                if es and ed.redo(es):
                    refresh_fabric_from_editor()

            def do_cut():
                es = state['editor']
                if es is None:
                    return
                ed.cut(es)
                refresh_fabric_from_editor()

            def do_copy():
                es = state['editor']
                if es is None:
                    return
                ed.copy(es)

            def do_paste():
                es = state['editor']
                if es is None:
                    return
                if not ed.do_paste(es):
                    return
                refresh_fabric_from_editor()

            def do_clear():
                es = state['editor']
                if es is None:
                    return
                ed.push_history(es)
                ed.clear_fabric(es.fabric, 0)
                refresh_fabric_from_editor()

            def do_save_json():
                if state['editor'] is None:
                    return
                save_pattern_json()

            async def on_upload(e):
                try:
                    text = await e.file.text()
                    fabric, config, palette, title, progress = ed.fabric_from_json(text)
                except Exception as err:
                    ui.notify(f'Load failed: {err}', type='negative')
                    return
                es = state['editor']
                if es is None:
                    return
                es.fabric = fabric
                es.config = config
                es.palette = palette
                es.title = title
                es.snapshot = [r[:] for r in fabric]
                es.snapshot_palette = copy.deepcopy(palette)
                es.history.clear()
                es.redo_stack.clear()
                es.selection = None
                es.drag = None
                # Loaded JSON becomes the new baseline — also commit to the
                # outer state so a no-changes exit preserves it instead of
                # reverting render_current() to the pre-load fabric.
                state['_fabric'] = fabric
                state['_palette'] = palette
                state['_title'] = title
                state['_config'] = config
                state['custom'] = True
                state['progress_row'] = progress
                state['save_filename'] = None
                build_editor_panel()
                refresh_fabric_from_editor()
                persist_state()
                ui.notify('Loaded pattern', type='positive')

            editor_zoom_slider = None

            def set_editor_zoom(v):
                v = max(200, min(2000, int(v)))
                if v == state['editor_zoom']:
                    return
                state['editor_zoom'] = v
                fabric_container.style(f'width: {v}px;')
                if editor_zoom_slider is not None:
                    editor_zoom_slider.value = v
                persist_state()

            def build_editor_panel():
                nonlocal editor_zoom_slider
                editor_panel.clear()
                es = state['editor']
                if es is None:
                    return
                with editor_panel:
                    with ui.row().classes('w-full items-center gap-2'):
                        ui.label('Editor').classes('text-subtitle1 font-bold flex-1')
                        ui.button('Close', icon='close',
                                  on_click=request_close_editor).props('flat dense')

                    # Tools
                    ui.label('Tools').classes('text-caption text-grey-7 mt-2')
                    with ui.row().classes('w-full gap-1 flex-wrap'):
                        for tname, icon, tooltip in TOOL_ICONS:
                            color = 'primary' if es.tool == tname else 'grey-7'
                            btn = ui.button(
                                icon=icon,
                                on_click=lambda _, n=tname: set_tool(n),
                            ).props(f'flat dense round size=sm color={color}')
                            btn.tooltip(tooltip)

                    # Active color + add
                    ui.label('Color').classes('text-caption text-grey-7 mt-2')
                    with ui.row().classes('w-full items-center gap-2'):
                        active_hex = es.palette.colors.get(es.active_color,
                                                           '#ffffff')
                        ui.element('div').style(
                            f'width: 36px; height: 36px; border-radius: 6px; '
                            f'background: {active_hex}; '
                            f'border: 2px solid rgba(0,0,0,0.3);'
                        )
                        active_name = es.palette.names.get(es.active_color,
                                                           '?')
                        ui.label(f'{active_name} ({active_hex})').classes('flex-1')
                        ui.color_input(
                            label='+', value='#ff0000',
                            on_change=lambda e: add_custom_color(e.value),
                        ).props('outlined dense').style('width: 80px;')

                    # Palette swatches
                    with ui.row().classes('w-full gap-1 flex-wrap'):
                        for idx in sorted(es.palette.colors.keys()):
                            hex_c = es.palette.colors[idx]
                            border = ('3px solid #1976d2' if idx == es.active_color
                                      else '1px solid rgba(0,0,0,0.24)')
                            btn = ui.element('div').style(
                                f'width: 28px; height: 28px; border-radius: 4px; '
                                f'background: {hex_c}; border: {border}; '
                                f'cursor: pointer;'
                            )
                            btn.on('click', lambda _, i=idx: set_active_color(i))
                            btn.tooltip(es.palette.names.get(idx, f'Color {idx}'))

                    # Recent colors
                    if es.recent_colors:
                        ui.label('Recent').classes('text-caption text-grey-7 mt-2')
                        with ui.row().classes('w-full gap-1 flex-wrap'):
                            for idx in es.recent_colors:
                                hex_c = es.palette.colors.get(idx, '#cccccc')
                                btn = ui.element('div').style(
                                    f'width: 22px; height: 22px; border-radius: 3px; '
                                    f'background: {hex_c}; '
                                    f'border: 1px solid rgba(0,0,0,0.24); '
                                    f'cursor: pointer;'
                                )
                                btn.on('click', lambda _, i=idx: set_active_color(i))

                    # Actions
                    ui.label('Actions').classes('text-caption text-grey-7 mt-2')
                    with ui.row().classes('w-full gap-1 flex-wrap'):
                        ui.button(icon='undo', on_click=do_undo).props(
                            'flat dense').tooltip('Undo')
                        ui.button(icon='redo', on_click=do_redo).props(
                            'flat dense').tooltip('Redo')
                        ui.button(icon='content_cut', on_click=do_cut).props(
                            'flat dense').tooltip('Cut')
                        ui.button(icon='content_copy', on_click=do_copy).props(
                            'flat dense').tooltip('Copy')
                        ui.button(icon='content_paste', on_click=do_paste).props(
                            'flat dense').tooltip('Paste')
                        ui.button(icon='delete_sweep', on_click=do_clear).props(
                            'flat dense').tooltip('Clear')

                    # File I/O
                    ui.label('File').classes('text-caption text-grey-7 mt-2')
                    with ui.row().classes('w-full gap-1'):
                        ui.button('Save .json', icon='save',
                                  on_click=do_save_json).props('flat dense').classes('flex-1')
                    ui.upload(
                        label='Load .json',
                        on_upload=on_upload,
                        auto_upload=True,
                    ).props('accept=.json flat dense').classes('w-full')

                    # Zoom
                    ui.label('Zoom').classes('text-subtitle1 font-bold mt-4')
                    with ui.row().classes('w-full items-center gap-1 no-wrap').style(
                        'border: 1px solid rgba(0,0,0,0.24); border-radius: 4px; '
                        'padding: 4px 8px;'
                    ):
                        ui.button(icon='remove',
                                  on_click=lambda: set_editor_zoom(state['editor_zoom'] - 100)
                                  ).props('flat dense round size=sm')
                        editor_zoom_slider = ui.slider(
                            min=200, max=2000, step=100,
                            value=state['editor_zoom'],
                            on_change=lambda e: set_editor_zoom(e.value),
                        ).props('label').classes('flex-1')
                        ui.button(icon='add',
                                  on_click=lambda: set_editor_zoom(state['editor_zoom'] + 100)
                                  ).props('flat dense round size=sm')
                        ui.button(icon='refresh',
                                  on_click=lambda: set_editor_zoom(state['zoom'] * 2)
                                  ).props('flat dense round size=sm')

        with ui.column().classes('p-4 gap-2 items-start').style(
            'min-width: 300px; flex: 1 1 0%;'
        ):
            with ui.row().classes('gap-4 items-start'):
                pattern_container = ui.element('div').style(f'width: {state["zoom"]}px;')
                with pattern_container:
                    pattern_img = ui.interactive_image(
                        content='', cross=False,
                        events=['mousedown'],
                        on_mouse=lambda e: on_pattern_click(e),
                    ).classes('w-full')
                fabric_container = ui.element('div').style(f'width: {state["zoom"]}px;')
                with fabric_container:
                    fabric_img = ui.interactive_image(
                        content='', cross=False,
                        events=['mousedown', 'mousemove', 'mouseup'],
                        on_mouse=on_fabric_mouse,
                    ).classes('w-full')

    # Initial render: if we restored a custom edit, draw it directly so we
    # don't regenerate from procedural settings and wipe it. Otherwise
    # rebuild from procedural settings but preserve any restored progress.
    if restored_custom:
        render_current()
    else:
        update_preview(reset_progress=False)


def main(reload: bool = False):
    ui.run(title='Peyote Pattern Designer', port=8080,
           reload=reload, storage_secret='peyote-pattern-local')


if __name__ in {'__main__', '__mp_main__'}:
    main(reload=True)
