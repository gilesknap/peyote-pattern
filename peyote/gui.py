"""NiceGUI-based peyote pattern designer."""

import io
import json as json_mod
import base64

from nicegui import ui, app

from peyote.sizing import BeadConfig, PRESETS
from peyote.colors import ColorPalette, PALETTE_DEFS
from peyote.font import text_to_fabric
from peyote.patterns import PATTERN_CATALOG
from peyote.compose import (
    compose_text_with_border,
    compose_text_with_background,
    compose_pattern_only,
    default_border_rows,
)
from peyote.export import render_combined_png
from peyote.grid import count_beads


def build_fabric(text, preset, columns, rows, layout, pattern_name,
                 border_rows_val, font_mode, rotate, border,
                 bg_color, fg_color, border_color):
    """Build fabric grid and palette from current settings."""
    # Config
    if preset != 'custom':
        p = PRESETS[preset]
        config = BeadConfig(columns=p.columns, rows=rows or p.rows)
    else:
        config = BeadConfig(columns=columns, rows=rows)

    # Palette
    if layout == 'Text + Border':
        palette = ColorPalette.three_color(bg_color, fg_color, border_color)
    else:
        palette = ColorPalette.two_color(bg_color, fg_color)

    # Fabric
    if layout == 'Text Only':
        fabric = text_to_fabric(text or 'HELLO', config, font_mode=font_mode, rotate=rotate, border=border)
        title = text or 'Pattern'
    elif layout == 'Text + Border':
        fabric = compose_text_with_border(
            text or 'HELLO', config,
            border_pattern=pattern_name, border_rows=border_rows_val,
            font_mode=font_mode, rotate=rotate, border=border)
        title = text or 'Pattern'
    elif layout == 'Text + Background':
        fabric = compose_text_with_background(
            text or 'HELLO', config,
            background_pattern=pattern_name,
            font_mode=font_mode, rotate=rotate, border=border)
        title = text or 'Pattern'
    elif layout == 'Pattern Only':
        fabric = compose_pattern_only(pattern_name, config)
        title = f'{pattern_name} pattern'
    else:
        fabric = text_to_fabric(text or 'HELLO', config, font_mode=font_mode, rotate=rotate, border=border)
        title = text or 'Pattern'

    return fabric, config, palette, title


def render_to_bytes(fabric, title, config, palette, view='fabric'):
    """Render to PNG bytes."""
    img = render_combined_png(fabric, title, config, palette, view=view)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def create_ui():
    # State defaults
    state = {
        'text': 'HELLO',
        'preset': 'ring',
        'columns': 10,
        'rows': 72,
        'layout': 'Text Only',
        'pattern': 'chevron',
        'border': 0,
        'border_rows': 10,
        'font_mode': 'auto',  # kept for build_fabric compat
        'rotate': True,
        'palette_name': 'classic',
        'bg_color': '#E8A0A8',
        'fg_color': '#C82020',
        'border_color': '#8B4513',
        'zoom': 300,  # px max-width per image
    }

    def update_preview():
        try:
            fabric, config, palette, title = build_fabric(
                state['text'], state['preset'], state['columns'], state['rows'],
                state['layout'], state['pattern'], state['border_rows'],
                state['font_mode'], state['rotate'], state['border'],
                state['bg_color'], state['fg_color'], state['border_color'])

            # Fabric preview
            png_bytes = render_to_bytes(fabric, title, config, palette, view='fabric')
            fabric_img.set_source(f'data:image/png;base64,{base64.b64encode(png_bytes).decode()}')

            # Pattern preview
            pat_bytes = render_to_bytes(fabric, title, config, palette, view='pattern')
            pattern_img.set_source(f'data:image/png;base64,{base64.b64encode(pat_bytes).decode()}')

            # Update zoom sizing
            z = state['zoom']
            fabric_container.style(f'width: {z}px;')
            pattern_container.style(f'width: {z}px;')

            # Bead count
            counts = count_beads(fabric, config)
            total = sum(counts.values())
            count_lines = [f'**{config.columns} beads per row**']
            for idx in sorted(counts.keys()):
                name = palette.names.get(idx, f'Color {idx}')
                lbl = palette.label(idx)
                count_lines.append(f'{lbl} ({name}): {counts[idx]} beads')
            count_lines.append(f'**Total: {total} beads**')
            bead_count_label.set_content('\n\n'.join(count_lines))

            # Store for downloads
            state['_fabric'] = fabric
            state['_config'] = config
            state['_palette'] = palette
            state['_title'] = title

        except Exception as e:
            bead_count_label.set_content(f'Error: {e}')

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

    def download_pdf():
        fabric = state.get('_fabric')
        if not fabric:
            return
        from peyote.renderer import make_pattern_svg
        import cairosvg
        svg_str, _, _ = make_pattern_svg(fabric, state['_title'],
                                         state['_config'], state['_palette'])
        pdf_bytes = cairosvg.svg2pdf(bytestring=svg_str.encode('utf-8'))
        ui.download(pdf_bytes, 'peyote-pattern.pdf')

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
            ).classes('w-full')

            with ui.row().classes('w-full gap-2'):
                cols_input = ui.number('Cols', value=state['columns'],
                                       min=4, max=100, step=2,
                                       on_change=lambda e: (
                                           state.update({'columns': int(e.value) if e.value else 10,
                                                         'preset': 'custom'}),
                                           preset_select.set_value('custom'),
                                           update_preview(),
                                       )).classes('flex-1')

                rows_input = ui.number('Rows', value=state['rows'],
                                        min=10, max=500,
                                        on_change=lambda e: (
                                            state.update({'rows': int(e.value) if e.value else 72,
                                                          'preset': 'custom'}),
                                            preset_select.set_value('custom'),
                                            update_preview(),
                                        )).classes('flex-1')

                ui.number('Border', value=state['border'],
                          min=0, max=20,
                          on_change=lambda e: (
                              state.update({'border': int(e.value) if e.value else 0}),
                              update_preview(),
                          )).classes('flex-1')

            ui.separator()

            # Content
            ui.label('Content').classes('text-subtitle1 font-bold')
            layout_select = ui.select(
                ['Text Only', 'Text + Border', 'Text + Background', 'Pattern Only'],
                value=state['layout'], label='Layout',
                on_change=lambda e: (
                    state.update({'layout': e.value}),
                    update_preview(),
                )
            ).classes('w-full')

            text_input = ui.input('Text', value=state['text'],
                                   on_change=lambda e: (
                                       state.update({'text': e.value}),
                                       update_preview(),
                                   )).classes('w-full')

            ui.switch('Sideways text (rings)',
                      value=state['rotate'],
                      on_change=lambda e: (
                          state.update({'rotate': e.value}),
                          update_preview(),
                      ))

            pattern_select = ui.select(
                list(PATTERN_CATALOG.keys()),
                value=state['pattern'], label='Pattern',
                on_change=lambda e: (
                    state.update({'pattern': e.value}),
                    update_preview(),
                )
            ).classes('w-full')

            border_slider = ui.slider(min=1, max=40, value=state['border_rows'],
                                      on_change=lambda e: (
                                          state.update({'border_rows': int(e.value)}),
                                          update_preview(),
                                      )).props('label')
            ui.label('Border rows').classes('text-caption')

            ui.separator()

            # Colors
            ui.label('Colors').classes('text-subtitle1 font-bold')

            def apply_palette(name):
                colors = PALETTE_DEFS[name]
                state['bg_color'] = colors[0][0]
                state['fg_color'] = colors[1][0]
                if len(colors) > 2:
                    state['border_color'] = colors[2][0]
                bg_picker.set_value(state['bg_color'])
                fg_picker.set_value(state['fg_color'])
                border_picker.set_value(state['border_color'])
                update_preview()

            ui.select(
                list(PALETTE_DEFS.keys()),
                value=state['palette_name'], label='Palette',
                on_change=lambda e: apply_palette(e.value),
            ).classes('w-full')

            bg_picker = ui.color_input('Background', value=state['bg_color'],
                                       on_change=lambda e: (
                                           state.update({'bg_color': e.value}),
                                           update_preview(),
                                       )).classes('w-full')
            fg_picker = ui.color_input('Foreground', value=state['fg_color'],
                                       on_change=lambda e: (
                                           state.update({'fg_color': e.value}),
                                           update_preview(),
                                       )).classes('w-full')
            border_picker = ui.color_input('Border', value=state['border_color'],
                                           on_change=lambda e: (
                                               state.update({'border_color': e.value}),
                                               update_preview(),
                                           )).classes('w-full')

            ui.separator()

            # Downloads
            ui.label('Export').classes('text-subtitle1 font-bold')
            with ui.row().classes('w-full gap-1'):
                ui.button('PNG', on_click=download_png, icon='image').props('dense')
                ui.button('SVG', on_click=download_svg, icon='code').props('dense')
                ui.button('PDF', on_click=download_pdf, icon='picture_as_pdf').props('dense')
                ui.button('JSON', on_click=download_json, icon='data_object').props('dense')

        with ui.column().classes('p-4 gap-2 items-start').style(
            'min-width: 300px; flex: 1 1 0%;'
        ):
            with ui.row().classes('gap-2 items-center'):
                ui.label('Zoom:').classes('text-caption')
                ui.button(icon='remove', on_click=lambda: (
                    state.update({'zoom': max(100, state['zoom'] - 50)}),
                    update_preview(),
                )).props('round outline').style('min-width: 40px; min-height: 40px;')
                ui.button(icon='add', on_click=lambda: (
                    state.update({'zoom': min(800, state['zoom'] + 50)}),
                    update_preview(),
                )).props('round outline').style('min-width: 40px; min-height: 40px;')
                ui.button('Reset', on_click=lambda: (
                    state.update({'zoom': 300}),
                    update_preview(),
                )).props('outline dense')

            with ui.row().classes('gap-4 items-start'):
                with ui.column().classes('items-center'):
                    ui.label('Working Pattern').classes('text-subtitle1 font-bold')
                    pattern_container = ui.element('div').style(f'width: {state["zoom"]}px;')
                    with pattern_container:
                        pattern_img = ui.image().classes('w-full')
                with ui.column().classes('items-center'):
                    ui.label('Fabric Preview').classes('text-subtitle1 font-bold')
                    fabric_container = ui.element('div').style(f'width: {state["zoom"]}px;')
                    with fabric_container:
                        fabric_img = ui.image().classes('w-full')

            ui.label('Bead Count').classes('text-subtitle1 font-bold')
            bead_count_label = ui.markdown('').classes('w-full')

    # Calculate initial border rows from default text
    if state['preset'] != 'custom':
        p = PRESETS[state['preset']]
        cfg = BeadConfig(columns=p.columns, rows=state['rows'] or p.rows)
    else:
        cfg = BeadConfig(columns=state['columns'], rows=state['rows'])
    br = default_border_rows(state['text'] or 'HELLO', cfg, rotate=state['rotate'])
    state['border_rows'] = br
    border_slider.set_value(br)

    # Initial render
    update_preview()


create_ui()
ui.run(title='Peyote Pattern Designer', port=8080)
