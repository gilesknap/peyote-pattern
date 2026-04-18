"""Command-line interface for peyote pattern generator."""

import argparse
import subprocess
import sys

from .sizing import BeadConfig, PRESETS
from .colors import ColorPalette, PALETTE_DEFS, get_palette
from .font import text_to_fabric
from .font_ttf import available_fonts, resolve_font, DEFAULT_FONT_NAME
from .patterns import PATTERN_CATALOG
from .compose import (
    compose_text_with_border,
    compose_pattern_only,
)
from .export import (
    save_png, save_svg, save_pdf, save_json,
    format_bead_count, load_json,
)


def main():
    parser = argparse.ArgumentParser(
        description='Generate peyote bead patterns with text and decorative patterns')

    parser.add_argument('text', nargs='?',
                        help='Text to render (characters stack vertically)')

    # Size
    parser.add_argument('--preset', choices=list(PRESETS.keys()),
                        help='Size preset (overrides --columns/--rows)')
    parser.add_argument('--columns', type=int, default=None,
                        help='Number of bead columns (must be even, default: 10)')
    parser.add_argument('--rows', type=int, default=None,
                        help='Number of fabric rows (default: 72)')

    # Font
    parser.add_argument('--font', choices=['auto', 'ttf', 'bitmap'], default='auto',
                        help='Font engine (default: auto)')
    parser.add_argument('--font-name', choices=available_fonts(),
                        default=DEFAULT_FONT_NAME,
                        help=f'Curated font (default: {DEFAULT_FONT_NAME}). '
                             f'Overridden by --font-path.')
    parser.add_argument('--font-path', default=None,
                        help='Path to TTF font file (overrides --font-name)')
    parser.add_argument('--orientation', choices=['sideways', 'straight'], default='sideways',
                        help='Text direction: sideways (rings) or straight (bracelets)')

    # Patterns
    parser.add_argument('--pattern', choices=list(PATTERN_CATALOG.keys()),
                        help='Decorative pattern (no text, fills entire grid)')
    parser.add_argument('--border', choices=list(PATTERN_CATALOG.keys()),
                        help='Border pattern around text')
    parser.add_argument('--border-rows', type=int, default=None,
                        help='Rows for border pattern bands (default: auto-sized)')
    parser.add_argument('--wrap-border', action='store_true',
                        help='Extend border pattern into the left/right margin '
                             'strips so it frames the text on all four sides')
    parser.add_argument('--gap', type=int, default=2,
                        help='Background bead rows between text and border '
                             '(default: 2)')
    parser.add_argument('--margin', type=int, default=0,
                        help='Background bead columns on the long sides of '
                             'text (default: 0)')

    # Colors
    parser.add_argument('--bg-color', default='#E8A0A8',
                        help='Background bead color (default: #E8A0A8)')
    parser.add_argument('--fg-color', default='#C82020',
                        help='Foreground bead color (default: #C82020)')
    parser.add_argument('--bg-name', default='Background',
                        help='Background color name for legend')
    parser.add_argument('--fg-name', default='Foreground',
                        help='Foreground color name for legend')
    parser.add_argument('--palette', choices=list(PALETTE_DEFS.keys()),
                        help='Named color palette (overrides --bg/fg-color)')

    # Output
    parser.add_argument('--title', default=None, help='Pattern title')
    parser.add_argument('--format', choices=['png', 'svg', 'pdf', 'json'], default='png',
                        help='Output format (default: png)')
    parser.add_argument('--view', choices=['both', 'pattern', 'fabric'], default='both',
                        help='Which view(s) to render (default: both)')
    parser.add_argument('--output', '-o', default=None,
                        help='Output file path')
    parser.add_argument('--no-open', action='store_true',
                        help='Do not open the image after saving')
    parser.add_argument('--bead-count', action='store_true',
                        help='Print bead count summary')

    # Legacy
    parser.add_argument('--fabric', default=None,
                        help='Path to JSON file with custom fabric grid')

    args = parser.parse_args()

    # Build config
    if args.preset:
        config = PRESETS[args.preset]
        if args.rows:
            config = BeadConfig(columns=config.columns, rows=args.rows)
    else:
        columns = args.columns or 10
        rows = args.rows or 72
        config = BeadConfig(columns=columns, rows=rows)

    # Build palette — pad to 4 slots (bg, text/accent1, accent2, accent3) so
    # pattern indices in Text+Border and pattern-with-text layouts always
    # resolve to a concrete color instead of the renderer's gray fallback.
    if args.palette:
        base_pairs = list(PALETTE_DEFS[args.palette])
    else:
        base_pairs = [(args.bg_color, args.bg_name),
                      (args.fg_color, args.fg_name)]
    while len(base_pairs) < 4:
        base_pairs.append(base_pairs[-1])
    palette = ColorPalette.from_pairs(base_pairs)

    rotate = args.orientation == 'sideways'

    # Resolve font: --font-path wins, else look up --font-name in the catalog
    font_path = args.font_path or resolve_font(args.font_name)

    # Build fabric
    if args.fabric:
        # Load from JSON
        fabric, loaded_config, loaded_palette, loaded_title, _ = load_json(args.fabric)
        config = loaded_config
        palette = loaded_palette
        title = args.title or loaded_title or 'Custom Pattern'

    elif args.pattern:
        # Pattern only (no text)
        fabric = compose_pattern_only(args.pattern, config)
        title = args.title or f'{args.pattern} pattern'

    elif args.text:
        if args.border:
            fabric = compose_text_with_border(
                args.text, config,
                border_pattern=args.border,
                border_rows=args.border_rows,
                font_mode=args.font,
                font_path=font_path,
                rotate=rotate,
                margin=args.margin,
                gap=args.gap,
                wrap_border=args.wrap_border,
            )
        else:
            fabric = text_to_fabric(
                args.text, config,
                font_mode=args.font,
                font_path=font_path,
                rotate=rotate,
                margin=args.margin,
            )
        title = args.title or args.text
    else:
        parser.error('Provide text, --pattern, or --fabric')

    # Default output filename
    if args.output is None:
        args.output = f'peyote-pattern.{args.format}'

    # Save
    if args.format == 'png':
        out = save_png(fabric, title, config, palette,
                       output=args.output, view=args.view)
    elif args.format == 'svg':
        out = save_svg(fabric, title, config, palette,
                       output=args.output, view=args.view)
    elif args.format == 'pdf':
        out = save_pdf(fabric, title, config, palette,
                       output=args.output, view=args.view)
    elif args.format == 'json':
        out = save_json(fabric, config, palette, title=title,
                        output=args.output)

    print(f'Saved: {out}')

    if args.bead_count:
        print('\nBead count:')
        print(format_bead_count(fabric, config, palette))

    if not args.no_open and args.format in ('png', 'pdf', 'svg'):
        subprocess.Popen(['xdg-open', out],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == '__main__':
    main()
