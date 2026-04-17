"""Color utilities, palettes, and Miyuki Delica bead codes."""

from dataclasses import dataclass, field


def darken(hex_color: str, factor: float = 0.65) -> str:
    """Darken a hex color by a factor."""
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r, g, b = int(r * factor), int(g * factor), int(b * factor)
    return f'#{r:02x}{g:02x}{b:02x}'


def text_color_for(hex_color: str) -> str:
    """Choose white or dark text for contrast against a background color."""
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return '#ffffff' if luminance < 0.5 else '#333333'


@dataclass
class ColorPalette:
    """Maps integer color indices to hex colors, names, strokes, and text colors."""
    colors: dict[int, str] = field(default_factory=dict)
    names: dict[int, str] = field(default_factory=dict)
    strokes: dict[int, str] = field(default_factory=dict)
    text_colors: dict[int, str] = field(default_factory=dict)

    @classmethod
    def from_pairs(cls, pairs: list[tuple[str, str]]) -> 'ColorPalette':
        """Create from [(hex, name), ...] list. Index 0 = background."""
        colors, names, strokes, text_cols = {}, {}, {}, {}
        for i, (hex_color, name) in enumerate(pairs):
            colors[i] = hex_color
            names[i] = name
            strokes[i] = darken(hex_color)
            text_cols[i] = text_color_for(hex_color)
        return cls(colors=colors, names=names, strokes=strokes, text_colors=text_cols)

    @classmethod
    def two_color(cls, bg: str, fg: str,
                  bg_name: str = 'Background', fg_name: str = 'Accent 1') -> 'ColorPalette':
        """Convenience for the common two-color case."""
        return cls.from_pairs([(bg, bg_name), (fg, fg_name)])

    @classmethod
    def three_color(cls, bg: str, accent1: str, accent2: str,
                    bg_name: str = 'Background', accent1_name: str = 'Accent 1',
                    accent2_name: str = 'Accent 2') -> 'ColorPalette':
        """Background + two accent colors (text uses Accent 1, patterns can use both)."""
        return cls.from_pairs([(bg, bg_name), (accent1, accent1_name), (accent2, accent2_name)])

    @classmethod
    def four_color(cls, bg: str, text: str, accent1: str, accent2: str,
                   bg_name: str = 'Background', text_name: str = 'Text',
                   accent1_name: str = 'Accent 1',
                   accent2_name: str = 'Accent 2') -> 'ColorPalette':
        """Background + text + two accent colors.

        Slot layout: 0=bg, 1=text, 2=accent1, 3=accent2. Text uses slot 1; patterns
        use slots 2/3 so pattern colors stay independent from text color.
        """
        return cls.from_pairs([(bg, bg_name), (text, text_name),
                               (accent1, accent1_name), (accent2, accent2_name)])

    def label(self, index: int) -> str:
        """Short label for a color index (A, B, C, ...)."""
        return chr(ord('A') + index)

    @property
    def num_colors(self) -> int:
        return len(self.colors)


# Built-in palette definitions: [(hex, name), ...]
PALETTE_DEFS: dict[str, list[tuple[str, str]]] = {
    'classic':    [('#E8A0A8', 'Pink'), ('#C82020', 'Red')],
    'ocean':      [('#E8F4F8', 'Ice Blue'), ('#1565C0', 'Ocean'), ('#0D47A1', 'Deep Blue')],
    'earth':      [('#F5E6D3', 'Sand'), ('#8D6E63', 'Brown'), ('#4E342E', 'Dark Brown')],
    'forest':     [('#E8F5E9', 'Mint'), ('#2E7D32', 'Forest'), ('#1B5E20', 'Dark Green')],
    'sunset':     [('#FFF3E0', 'Cream'), ('#FF6F00', 'Amber'), ('#E65100', 'Burnt Orange')],
    'monochrome': [('#FFFFFF', 'White'), ('#000000', 'Black')],
    'berry':      [('#FFF0F5', 'Lavender'), ('#C2185B', 'Raspberry'), ('#4A148C', 'Plum')],
    'gold':       [('#FFFDE7', 'Ivory'), ('#FFD600', 'Gold'), ('#FF6F00', 'Amber')],
    'teal':       [('#E0F2F1', 'Pale Teal'), ('#00897B', 'Teal'), ('#004D40', 'Dark Teal')],
    'day-to-night': [('#FAFAFA', 'Day'), ('#1A1A1A', 'Night'), ('#00838F', 'Dusk')],
}


def get_palette(name: str) -> ColorPalette:
    """Get a named palette."""
    if name not in PALETTE_DEFS:
        raise ValueError(f"Unknown palette '{name}'. Available: {list(PALETTE_DEFS.keys())}")
    return ColorPalette.from_pairs(PALETTE_DEFS[name])


# Miyuki Delica 11/0 approximate hex colors (common codes)
MIYUKI_DELICA: dict[str, tuple[str, str]] = {
    'DB0010': ('#000000', 'Black'),
    'DB0200': ('#FFFFFF', 'Opaque White'),
    'DB0310': ('#1a1a1a', 'Matte Black'),
    'DB0723': ('#C82020', 'Opaque Red'),
    'DB0727': ('#D84315', 'Opaque Vermillion'),
    'DB0745': ('#FF8F00', 'Opaque Tangerine'),
    'DB0751': ('#FFD600', 'Opaque Yellow'),
    'DB0754': ('#43A047', 'Opaque Green'),
    'DB0759': ('#00838F', 'Opaque Turquoise'),
    'DB0726': ('#1565C0', 'Opaque Blue'),
    'DB0696': ('#6A1B9A', 'Opaque Purple'),
    'DB0796': ('#E8A0A8', 'Matte Dyed Rose'),
    'DB0353': ('#F5E6D3', 'Opaque Cream'),
    'DB0389': ('#A1887F', 'Opaque Taupe'),
    'DB0734': ('#4E342E', 'Opaque Chocolate'),
    'DB0035': ('#C0C0C0', 'Galvanized Silver'),
    'DB0031': ('#FFD700', 'Galvanized Gold'),
    'DB0167': ('#B0BEC5', 'Opaque Grey'),
    'DB0263': ('#FFB6C1', 'Opaque Pink'),
    'DB0165': ('#FF5722', 'Opaque Orange'),
}
