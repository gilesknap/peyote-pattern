"""Bead configuration and size presets for different jewelry types."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BeadConfig:
    """Configuration for a peyote stitch piece.

    Even-count flat peyote: columns must be even.
    Odd rows (N=1,3,5...) use even-indexed columns (0,2,4,...).
    Even rows (N=2,4,6...) use odd-indexed columns (1,3,5,...).
    """
    columns: int = 10
    rows: int = 72
    bead_width: int = 22
    bead_height: int = 22
    bead_margin: int = 1
    corner_radius: int = 5

    def __post_init__(self):
        if self.columns % 2 != 0:
            raise ValueError(f"columns must be even for peyote stitch, got {self.columns}")

    @property
    def slot(self) -> int:
        return self.bead_width + self.bead_margin * 2

    @property
    def half(self) -> int:
        return self.columns // 2

    def odd_cols(self) -> list[int]:
        """Columns active on odd fabric rows (N=1,3,5...)."""
        return list(range(0, self.columns, 2))

    def even_cols(self) -> list[int]:
        """Columns active on even fabric rows (N=2,4,6...)."""
        return list(range(1, self.columns, 2))

    def cols_for_row(self, row_index: int) -> list[int]:
        """Active columns for a given 0-indexed fabric row."""
        N = row_index + 1
        return self.odd_cols() if N % 2 == 1 else self.even_cols()


PRESETS: dict[str, BeadConfig] = {
    'ring':           BeadConfig(columns=10, rows=72),
    'wide-ring':      BeadConfig(columns=20, rows=72),
    'bracelet':       BeadConfig(columns=40, rows=180),
    'wide-bracelet':  BeadConfig(columns=50, rows=200),
    'bookmark':       BeadConfig(columns=20, rows=200),
}
