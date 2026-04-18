"""Export utilities — PNG, PDF, SVG, bead counts, print-friendly output."""

import io
import json

import cairosvg
from PIL import Image

from .sizing import BeadConfig
from .colors import ColorPalette
from .grid import count_beads
from .renderer import make_fabric_svg, make_pattern_svg


def svg_to_pil(svg_str: str, scale: int = 2) -> Image.Image:
    """Convert an SVG string to a PIL Image."""
    png = cairosvg.svg2png(bytestring=svg_str.encode('utf-8'), scale=scale)
    return Image.open(io.BytesIO(png))


def render_combined_png(fabric: list[list[int]], title: str,
                        config: BeadConfig, palette: ColorPalette,
                        view: str = 'both', scale: int = 2) -> Image.Image:
    """Render fabric/pattern views to a combined PIL Image.

    Args:
        view: 'both', 'fabric', or 'pattern'.
    """
    if view == 'fabric':
        svg, _, _ = make_fabric_svg(fabric, title, config, palette)
        return svg_to_pil(svg, scale)
    elif view == 'pattern':
        svg, _, _ = make_pattern_svg(fabric, title, config, palette)
        return svg_to_pil(svg, scale)
    else:
        svg1, _, _ = make_pattern_svg(fabric, title, config, palette)
        svg2, _, _ = make_fabric_svg(fabric, title, config, palette)
        img1 = svg_to_pil(svg1, scale)
        img2 = svg_to_pil(svg2, scale)

        max_h = max(img1.height, img2.height)

        def pad_h(img, h):
            if img.height == h:
                return img
            new = Image.new('RGBA', (img.width, h), (255, 255, 255, 255))
            new.paste(img, (0, 0))
            return new

        img1 = pad_h(img1, max_h)
        img2 = pad_h(img2, max_h)

        GAP = 40
        out = Image.new('RGBA', (img1.width + GAP + img2.width, max_h),
                        (255, 255, 255, 255))
        out.paste(img1, (0, 0))
        out.paste(img2, (img1.width + GAP, 0))
        return out


def save_png(fabric: list[list[int]], title: str,
             config: BeadConfig, palette: ColorPalette,
             output: str = 'peyote-pattern.png',
             view: str = 'both') -> str:
    """Render and save to PNG."""
    img = render_combined_png(fabric, title, config, palette, view=view)
    img.save(output)
    return output


def save_svg(fabric: list[list[int]], title: str,
             config: BeadConfig, palette: ColorPalette,
             output: str = 'peyote-pattern.svg',
             view: str = 'fabric') -> str:
    """Save raw SVG."""
    if view == 'pattern':
        svg, _, _ = make_pattern_svg(fabric, title, config, palette)
    else:
        svg, _, _ = make_fabric_svg(fabric, title, config, palette)
    with open(output, 'w') as f:
        f.write(svg)
    return output


def save_pdf(fabric: list[list[int]], title: str,
             config: BeadConfig, palette: ColorPalette,
             output: str = 'peyote-pattern.pdf',
             view: str = 'both') -> str:
    """Save as PDF via cairosvg."""
    if view == 'pattern':
        svg, _, _ = make_pattern_svg(fabric, title, config, palette)
    elif view == 'fabric':
        svg, _, _ = make_fabric_svg(fabric, title, config, palette)
    else:
        # For 'both', render to PNG first then embed
        # (cairosvg can only convert one SVG at a time)
        svg, _, _ = make_pattern_svg(fabric, title, config, palette)

    pdf_bytes = cairosvg.svg2pdf(bytestring=svg.encode('utf-8'))
    with open(output, 'wb') as f:
        f.write(pdf_bytes)
    return output


def _state_to_dict(fabric: list[list[int]], config: BeadConfig,
                   palette: ColorPalette, title: str = '',
                   progress_row: int = 0) -> dict:
    """Serialize project state to a plain dict."""
    return {
        'title': title,
        'config': {
            'columns': config.columns,
            'rows': config.rows,
            'bead_width': config.bead_width,
            'bead_height': config.bead_height,
            'bead_margin': config.bead_margin,
            'corner_radius': config.corner_radius,
        },
        'palette': {
            'colors': {str(k): v for k, v in palette.colors.items()},
            'names': {str(k): v for k, v in palette.names.items()},
        },
        'fabric': fabric,
        'progress_row': progress_row,
    }


def _dict_to_state(data: dict) -> tuple[list[list[int]], BeadConfig,
                                         ColorPalette, str, int]:
    config = BeadConfig(**data['config'])
    palette = ColorPalette.from_pairs([
        (data['palette']['colors'][str(i)], data['palette']['names'][str(i)])
        for i in range(len(data['palette']['colors']))
    ])
    return (data['fabric'], config, palette,
            data.get('title', ''),
            int(data.get('progress_row', 0)))


def save_json(fabric: list[list[int]], config: BeadConfig,
              palette: ColorPalette, title: str = '',
              output: str = 'peyote-pattern.json',
              progress_row: int = 0) -> str:
    """Save full project state as JSON."""
    with open(output, 'w') as f:
        json.dump(
            _state_to_dict(fabric, config, palette, title, progress_row),
            f, indent=2,
        )
    return output


def load_json_from_str(s: str) -> tuple[list[list[int]], BeadConfig,
                                         ColorPalette, str, int]:
    """Load project state from a JSON string."""
    return _dict_to_state(json.loads(s))


def load_json(path: str) -> tuple[list[list[int]], BeadConfig,
                                   ColorPalette, str, int]:
    """Load project state from JSON file."""
    with open(path) as f:
        return load_json_from_str(f.read())


def format_bead_count(fabric: list[list[int]], config: BeadConfig,
                      palette: ColorPalette) -> str:
    """Format bead count as a human-readable string."""
    counts = count_beads(fabric, config)
    lines = []
    total = 0
    for idx in sorted(counts.keys()):
        name = palette.names.get(idx, f'Color {idx}')
        lbl = palette.label(idx)
        color = palette.colors.get(idx, '???')
        count = counts[idx]
        total += count
        lines.append(f"  {lbl} ({name}, {color}): {count} beads")
    lines.append(f"  Total: {total} beads")
    return '\n'.join(lines)
