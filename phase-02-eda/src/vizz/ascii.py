"""vizz.ascii — charts for the terminal, in plain unicode text.

Same zero-dependency rule as the rest of vizz: these render inside any
SSH session, CI log, or code review. Sometimes the fastest chart is the
one already in your terminal.

HOW IT WORKS: the same scale math as the SVG side (value -> bar length),
but instead of emitting <rect> elements we emit unicode block characters
padded to fixed widths with f-string alignment. That's it.
"""

from __future__ import annotations

SPARK = "▁▂▃▄▅▆▇█"  # 8 vertical levels, low -> high


def sparkline(values, width: int | None = None) -> str:
    """A one-line trend: ▁▂▄▆█ — one character per value.

    HOW: normalize every value into 0..1 ((v - lo) / span), multiply by
    7.999 and truncate to pick one of the 8 block characters. The 7.999
    (not 8) matters: the highest value must map to index 7, never 8.
    Optionally resample first (one char per `width` columns).
    """
    values = list(values)
    if not values:
        return ""
    if width and width != len(values):
        # crude resampling: take every (n/width)-th value
        step = len(values) / width
        values = [values[int(i * step)] for i in range(width)]
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1          # constant data: avoid division by zero
    return "".join(SPARK[min(7, int((v - lo) / span * 7.999))] for v in values)


def barh(rows: list[tuple[str, float]], width: int = 36, fmt=str,
         title: str = "") -> str:
    """Horizontal bars, aligned: 'label ..... ████  1,234'.

    HOW: three columns — label (padded to the widest label), a bar of █
    scaled to `width` chars, and the value (right-padded to the widest).
    Computing each column's width FIRST is what makes the rows align.
    """
    rows = [(str(k), v) for k, v in rows]
    out = []
    if title:
        out.append(title)
    lab_w = max((len(str(k)) for k, _ in rows), default=0)
    val_w = max((len(fmt(v)) for _, v in rows), default=0)
    vmax = max((v for _, v in rows), default=0) or 1
    for k, v in rows:
        bar = "█" * max(1, round(v / vmax * width))
        out.append(f"{str(k):<{lab_w}} │ {bar:<{width}} {fmt(v):>{val_w}}")
    return "\n".join(out)


def histogram(values, bins: int = 12, width: int = 36, fmt=str,
              title: str = "") -> str:
    """ASCII histogram: bin ranges on the left, ▉ bars for counts.

    Same binning as the SVG histogram: bucket index =
    int((v - lo) / bin_width), clamped to the last bin.
    """
    values = list(values)
    lo, hi = min(values), max(values)
    if hi == lo:
        hi = lo + 1
    w = (hi - lo) / bins
    counts = [0] * bins
    for v in values:
        counts[min(bins - 1, int((v - lo) / w))] += 1
    vmax = max(counts) or 1
    out = [title] if title else []
    for i, c in enumerate(counts):
        a, b = lo + w * i, lo + w * (i + 1)
        bar = "▉" * round(c / vmax * width)
        out.append(f"{a:>10.1f} – {b:<10.1f} │ {bar:<{width}} {c}")
    return "\n".join(out)