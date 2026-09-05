"""vizz — pure-Python charts (SVG + ASCII). Stdlib only, by design."""

from .svg import Figure, nice_ticks, PALETTE
from . import ascii as ascii

__all__ = ["Figure", "nice_ticks", "PALETTE", "ascii"]