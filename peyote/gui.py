"""NiceGUI-based peyote pattern designer."""

import io
import json as json_mod
import base64

from nicegui import ui, app

from peyote.sizing import BeadConfig, PRESETS
from peyote.colors import ColorPalette, PALETTE_DEFS, darken
from peyote.font import text_to_fabric
from peyote.patterns import PATTERN_CATALOG
from peyote.compose import (
    compose_text_with_border,
    compose_text_with_background,
    compose_pattern_only,
)
from peyote.export import render_combined_png
from peyote.renderer import make_fabric_svg, make_pattern_svg
from peyote.grid import count_beads
from peyote.font_ttf import available_fonts, resolve_font, DEFAULT_FONT_NAME


def build_fabric(text, preset, columns, rows, layout, pattern_name,
                 font_mode, rotate, margin,
                 bg_color, text_color, accent1_color, accent2_color,
                 font_path=None, gap=2):
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

    # Fabric
    if layout == 'Text Only':
        fabric = text_to_fabric(text or 'HELLO', config, font_mode=font_mode,
                                font_path=font_path, rotate=rotate, margin=margin)
        title = text or 'Pattern'
    elif layout in ('Text + Border', 'Text + Border Wrap'):
        fabric = compose_text_with_border(
            text or 'HELLO', config,
            border_pattern=pattern_name,
            font_mode=font_mode, font_path=font_path, rotate=rotate,
            margin=margin, gap=gap,
            wrap_border=(layout == 'Text + Border Wrap'))
        title = text or 'Pattern'
    elif layout == 'Text + Background':
        fabric = compose_text_with_background(
            text or 'HELLO', config,
            background_pattern=pattern_name,
            font_mode=font_mode, font_path=font_path, rotate=rotate, margin=margin)
        title = text or 'Pattern'
    elif layout == 'Pattern Only':
        fabric = compose_pattern_only(pattern_name, config)
        title = f'{pattern_name} pattern'
    else:
        fabric = text_to_fabric(text or 'HELLO', config, font_mode=font_mode,
                                font_path=font_path, rotate=rotate, margin=margin)
        title = text or 'Pattern'

    return fabric, config, palette, title


def render_to_bytes(fabric, title, config, palette, view='fabric'):
    """Render to PNG bytes (for downloads)."""
    img = render_combined_png(fabric, title, config, palette, view=view)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def render_svg(fabric, title, config, palette, view='fabric') -> str:
    """Render SVG string directly (for live browser preview — skips cairosvg)."""
    if view == 'pattern':
        svg, _, _ = make_pattern_svg(fabric, title, config, palette)
    else:
        svg, _, _ = make_fabric_svg(fabric, title, config, palette)
    return svg


def create_ui():
    # State defaults
    state = {
        'text': 'HELLO',
        'preset': 'ring',
        'columns': 10,
        'rows': 72,
        'layout': 'Text Only',
        'pattern': 'chevron',
        'margin': 0,
        'gap': 2,
        'font_mode': 'auto',  # kept for build_fabric compat
        'font_name': DEFAULT_FONT_NAME,
        'rotate': True,
        'palette_name': 'classic',
        'bg_color': '#E8A0A8',
        'text_color': '#C82020',
        'accent1_color': '#8B4513',
        'accent2_color': '#53290b',
        'zoom': 300,  # px max-width per image
    }

    def update_preview():
        try:
            fabric, config, palette, title = build_fabric(
                state['text'], state['preset'], state['columns'], state['rows'],
                state['layout'], state['pattern'],
                state['font_mode'], state['rotate'], state['margin'],
                state['bg_color'], state['text_color'],
                state['accent1_color'], state['accent2_color'],
                font_path=resolve_font(state['font_name']),
                gap=state['gap'])

            # Fabric preview — send SVG directly to browser (browser renders natively,
            # avoiding the cairosvg→PNG roundtrip that dominates render time).
            fabric_svg = render_svg(fabric, title, config, palette, view='fabric')
            fabric_img.set_source(
                f'data:image/svg+xml;base64,{base64.b64encode(fabric_svg.encode()).decode()}')

            # Pattern preview
            pat_svg = render_svg(fabric, title, config, palette, view='pattern')
            pattern_img.set_source(
                f'data:image/svg+xml;base64,{base64.b64encode(pat_svg.encode()).decode()}')

            # Update zoom sizing
            z = state['zoom']
            fabric_container.style(f'width: {z}px;')
            pattern_container.style(f'width: {z}px;')

            # Bead count
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

            # Store for downloads
            state['_fabric'] = fabric
            state['_config'] = config
            state['_palette'] = palette
            state['_title'] = title

        except Exception as e:
            bead_count_container.clear()
            with bead_count_container:
                ui.label(f'Error: {e}').classes('text-red')

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
        from peyote.renderer import make_fabric_svg
        svg_str, _, _ = make_fabric_svg(fabric, state['_title'],
                                        state['_config'], state['_palette'])
        ui.download(svg_str.encode('utf-8'), 'peyote-pattern.svg')

    def download_json():
        fabric = state.get('_fabric')
        if not fabric:
            return
        config = state['_config']
        palette = state['_palette']
        data = {
            'title': state['_title'],
            'config': {
                'columns': config.columns, 'rows': config.rows,
                'bead_width': config.bead_width, 'bead_height': config.bead_height,
                'bead_margin': config.bead_margin, 'corner_radius': config.corner_radius,
            },
            'palette': {
                'colors': {str(k): v for k, v in palette.colors.items()},
                'names': {str(k): v for k, v in palette.names.items()},
            },
            'fabric': fabric,
        }
        ui.download(json_mod.dumps(data, indent=2).encode(), 'peyote-pattern.json')

    # ── Layout ────────────────────────────────────────────────────────
    ui.page_title('Peyote Pattern Designer')

    with ui.header().classes('bg-primary'):
        ui.label('Peyote Pattern Designer').classes('text-h5 text-white')

    with ui.row().classes('w-full flex-wrap'):
        with ui.column().classes('p-4 gap-2').style(
            'min-width: 280px; flex: 0 0 25%; max-width: 100%;'
        ):
            # Size
            ui.label('Size').classes('text-subtitle1 font-bold')
            preset_select = ui.select(
                list(PRESETS.keys()) + ['custom'],
                value=state['preset'], label='Preset',
                on_change=lambda e: (
                    state.update({'preset': e.value}),
                    state.update({'columns': PRESETS[e.value].columns,
                                  'rows': PRESETS[e.value].rows}
                                 if e.value != 'custom' else {}),
                    cols_input.set_value(state['columns']),
                    rows_input.set_value(state['rows']),
                    update_preview(),
                )
            ).props('outlined dense').classes('w-full')

            with ui.row().classes('w-full gap-2'):
                cols_input = ui.number('Cols', value=state['columns'],
                                       min=4, max=100, step=2,
                                       on_change=lambda e: (
                                           state.update({'columns': int(e.value) if e.value else 10,
                                                         'preset': 'custom'}),
                                           preset_select.set_value('custom'),
                                           update_preview(),
                                       )).props('outlined dense').classes('flex-1')

                rows_input = ui.number('Rows', value=state['rows'],
                                        min=10, max=500,
                                        on_change=lambda e: (
                                            state.update({'rows': int(e.value) if e.value else 72,
                                                          'preset': 'custom'}),
                                            preset_select.set_value('custom'),
                                            update_preview(),
                                        )).props('outlined dense').classes('flex-1')

                ui.number('Margin', value=state['margin'],
                          min=0, max=20,
                          on_change=lambda e: (
                              state.update({'margin': int(e.value) if e.value else 0}),
                              update_preview(),
                          )).props('outlined dense').classes('flex-1')

            # Content
            ui.label('Content').classes('text-subtitle1 font-bold mt-4')
            layout_select = ui.select(
                ['Text Only', 'Text + Border', 'Text + Border Wrap',
                 'Text + Background', 'Pattern Only'],
                value=state['layout'], label='Layout',
                on_change=lambda e: (
                    state.update({'layout': e.value}),
                    update_preview(),
                )
            ).props('outlined dense').classes('w-full')

            text_input = ui.input('Text', value=state['text'],
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

            with ui.row().classes('w-full gap-2 no-wrap'):
                pattern_select = ui.select(
                    list(PATTERN_CATALOG.keys()),
                    value=state['pattern'], label='Pattern',
                    on_change=lambda e: (
                        state.update({'pattern': e.value}),
                        update_preview(),
                    )
                ).props('outlined dense').classes('flex-1')

                ui.number('Gap', value=state['gap'],
                          min=0, max=20,
                          on_change=lambda e: (
                              state.update({'gap': int(e.value) if e.value is not None else 2}),
                              update_preview(),
                          )).props('outlined dense').style('width: 90px;')

            # Colors
            ui.label('Colors').classes('text-subtitle1 font-bold mt-4')

            def apply_palette(name):
                colors = PALETTE_DEFS[name]
                state['bg_color'] = colors[0][0]
                state['text_color'] = colors[1][0]
                # Accent 1 picks up the 3rd palette color when available, so
                # it stays distinct from Text. Accent 2 is synthesised as a
                # darkened shade of Accent 1 — the built-in palettes only
                # ship 2-3 colors, so we generate a 4th to keep each picker
                # on a unique color.
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

        with ui.column().classes('p-4 gap-2 items-start').style(
            'min-width: 300px; flex: 1 1 0%;'
        ):
            with ui.row().classes('gap-4 items-start'):
                pattern_container = ui.element('div').style(f'width: {state["zoom"]}px;')
                with pattern_container:
                    pattern_img = ui.image().classes('w-full')
                fabric_container = ui.element('div').style(f'width: {state["zoom"]}px;')
                with fabric_container:
                    fabric_img = ui.image().classes('w-full')

    # Initial render
    update_preview()


create_ui()
ui.run(title='Peyote Pattern Designer', port=8080)
