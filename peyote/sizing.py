"""Bead configuration and size presets for different jewelry types."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BeadConfig:
    """Configuration for a peyote stitch piece.

    Even-count peyote (columns even): both rows have columns/2 beads.
    Odd rows (N=1,3,5...) use cols 1,3,5,...; even rows (N=2,4,6...) use
    cols 0,2,4,.... A single bead anchors the start and two stack at the
    turnaround — the standard even-count thread path.

    Odd-count peyote (columns odd): rows alternate counts. The first row
    has the larger count (required for a correct turnaround). Odd rows
    (R1, R3, ...) use cols 0,2,4,...,columns-1 — (columns+1)//2 beads.
    Even rows (R2, R4, ...) use cols 1,3,5,...,columns-2 — columns//2
    beads.
    """
    columns: int = 10
    rows: int = 72
    bead_width: int = 22
    bead_height: int = 22
    bead_margin: int = 1
    corner_radius: int = 5

    @property
    def slot(self) -> int:
        return self.bead_width + self.bead_margin * 2

    @property
    def half(self) -> int:
        return self.columns // 2

    def odd_cols(self) -> list[int]:
        """Columns active on odd fabric rows (N=1,3,5...)."""
        # For odd-count peyote we flip parity so R1 gets the higher count.
        start = 0 if self.columns % 2 == 1 else 1
        return list(range(start, self.columns, 2))

    def even_cols(self) -> list[int]:
        """Columns active on even fabric rows (N=2,4,6...)."""
        start = 1 if self.columns % 2 == 1 else 0
        return list(range(start, self.columns, 2))

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
