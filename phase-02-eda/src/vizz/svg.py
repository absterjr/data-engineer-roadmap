"""vizz — charts from scratch, in pure Python.

No matplotlib. No PIL. No third-party anything. SVG is plain text,
so stdlib Python can draw professional charts: the whole library is
scale math (data -> pixels) plus string building.

    from vizz import Figure

    fig = Figure(900, 500, "Monthly revenue")
    fig.line(months, revenue)
    fig.save("monthly_revenue.svg")

Chart types: barh (horizontal bars), bar (vertical), line,
histogram, scatter.
"""
from __future__ import annotations

import math
from pathlib import Path

PALETTE = [
    "#00D4FF",  # cyan (brand)
    "#FF6B6B",  # coral
    "#7BED9F",  # mint
    "#FFA502",  # amber
    "#A29BFE",  # lavender
    "#FAB1A0",  # peach
    "#70A1FF",  # blue
    "#2ED573",  # green
]

BG = "#1F3864"       # navy
CARD = "#0A1628"     # dark panel
GRID = "#2A4A7F"     # gridline
TEXT = "#FFFFFF"
MUTED = "#7FA8D9"


def _esc(s: str) -> str:
    """Escape the five XML entities so labels can't break the SVG."""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _fmt(v: float, prefix: str = "") -> str:
    """Compact number formatting for axis and value labels."""
    a = abs(v)
    if a >= 1_000_000:
        s = f"{v / 1_000_000:.1f}M"
    elif a >= 1_000:
        s = f"{v / 1_000:.0f}k"
    elif float(v).is_integer():
        s = f"{int(v)}"
    else:
        s = f"{v:g}"
    return prefix + s


def nice_ticks(lo: float, hi: float, target: int = 5) -> list[float]:
    """Axis ticks at 'nice' numbers (1, 2, 5 x 10^k) — what humans expect.

    Algorithm: take a rough step (span / target), round it up to the
    nearest 1/2/5 x 10^k, then lay out ticks from floor to ceiling.
    """
    if hi <= lo:
        hi = lo + 1
    span = hi - lo
    rough = span / max(1, target)
    mag = 10 ** math.floor(math.log10(rough)) if rough > 0 else 1
    for mult in (1, 2, 5, 10):
        step = mult * mag
        if step >= rough:
            break
    lo_t = math.floor(lo / step) * step
    hi_t = math.ceil(hi / step) * step
    ticks, t = [], lo_t
    while t <= hi_t + step * 1e-9:
        ticks.append(round(t, 10))
        t += step
    return ticks


class Figure:
    """A single SVG chart. Create it, call one chart method, save it."""

    def __init__(self, width: int = 900, height: int = 520, title: str = "", bg: str = BG):
        self.w, self.h = width, height
        self.title = title
        self.bg = bg
        # plot area margins
        self.m = dict(l=88, r=36, t=64, b=60)
        self.el: list[str] = []
        self._color_i = 0

    # -- primitives ---------------------------------------------------------

    def _next_color(self) -> str:
        c = PALETTE[self._color_i % len(PALETTE)]
        self._color_i += 1
        return c

    def _text(self, x, y, s, size=12, fill=TEXT, anchor="start", weight="400",
              mono=False, opacity=1.0, ls=0.5):
        font = "'Courier New', monospace" if mono else "'Inter', sans-serif"
        self.el.append(
            f'<text x="{x:.1f}" y="{y:.1f}" fill="{fill}" font-size="{size}" '
            f'font-weight="{weight}" text-anchor="{anchor}" letter-spacing="{ls}" '
            f'opacity="{opacity}" font-family="{font}">{_esc(s)}</text>'
        )

    def _rect(self, x, y, w, h, fill, rx=0, opacity=1.0, stroke=None, sw=1):
        stroke_attr = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
        self.el.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'fill="{fill}" rx="{rx}" opacity="{opacity}"{stroke_attr}/>'
        )

    def _line(self, x1, y1, x2, y2, stroke, sw=1, opacity=1.0):
        self.el.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{stroke}" stroke-width="{sw}" opacity="{opacity}"/>'
        )

    def _circle(self, cx, cy, r, fill, opacity=1.0):
        self.el.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{fill}" opacity="{opacity}"/>'
        )

    # -- frame --------------------------------------------------------------

    def _frame(self, ylabel: str = "") -> tuple[float, float, float, float]:
        """Background + title + plot-area bounds. Returns (x0, y0, x1, y1)."""
        self._rect(0, 0, self.w, self.h, self.bg)
        if self.title:
            self._text(24, 34, self.title, size=19, weight="700", ls=0.5)
        x0, y0 = self.m["l"], self.m["t"]
        x1, y1 = self.w - self.m["r"], self.h - self.m["b"]
        if ylabel:
            self._text(24, y0 - 12, ylabel, size=11, fill=MUTED, mono=True)
        return x0, y0, x1, y1

    def _ygrid(self, x0, x1, y0, y1, ymax, prefix=""):
        """Horizontal gridlines + y tick labels for a 0..ymax scale."""
        for t in nice_ticks(0, ymax):
            if t == 0:
                continue
            y = y1 - (t / ymax) * (y1 - y0)
            self._line(x0, y, x1, y, GRID, sw=1, opacity=0.55)
            self._text(x0 - 8, y + 4, _fmt(t, prefix), size=11, fill=MUTED,
                       anchor="end", mono=True)
        self._line(x0, y1, x1, y1, GRID, sw=1.5)

    def _xgrid(self, x0, x1, y0, y1, xmax, prefix=""):
        """Vertical gridlines + bottom tick labels for a 0..xmax scale
        (used by horizontal bar charts, where the value axis is x)."""
        for t in nice_ticks(0, xmax):
            x = x0 + (t / xmax) * (x1 - x0)
            self._line(x, y0, x, y1, GRID, sw=1, opacity=0.35)
            self._text(x, y1 + 18, _fmt(t, prefix), size=11, fill=MUTED,
                       anchor="middle", mono=True)

    # -- charts -------------------------------------------------------------

    def barh(self, labels, values, color: str | None = None, prefix: str = "",
             value_labels: bool = True):
        """Horizontal bars — best for ranked categories with long names."""
        color = color or self._next_color()
        x0, y0, x1, y1 = self._frame(ylabel=prefix.strip() or "value")
        n = len(labels)
        vmax = max(values) * 1.06
        row_h = (y1 - y0) / n
        bar_h = row_h * 0.62
        self._xgrid(x0, x1, y0, y1, vmax, prefix)
        for i, (lab, v) in enumerate(zip(labels, values)):
            cy = y0 + row_h * (i + 0.5)
            w = (v / vmax) * (x1 - x0)
            self._rect(x0, cy - bar_h / 2, w, bar_h, color, rx=3, opacity=0.92)
            self._text(x0 - 8, cy + 4, str(lab), size=12, fill=TEXT, anchor="end")
            if value_labels:
                self._text(x0 + w + 6, cy + 4, _fmt(v, prefix), size=11,
                           fill=MUTED, mono=True)

    def bar(self, labels, values, color: str | None = None, prefix: str = "",
            value_labels: bool = False, label_every: int = 1):
        """Vertical bars — best for short ordered categories."""
        color = color or self._next_color()
        x0, y0, x1, y1 = self._frame()
        n = len(labels)
        vmax = max(values) * 1.12
        self._ygrid(x0, x1, y0, y1, vmax, prefix)
        slot = (x1 - x0) / n
        bar_w = slot * 0.62
        for i, (lab, v) in enumerate(zip(labels, values)):
            cx = x0 + slot * (i + 0.5)
            h = (v / vmax) * (y1 - y0)
            self._rect(cx - bar_w / 2, y1 - h, bar_w, h, color, rx=3, opacity=0.92)
            if value_labels:
                self._text(cx, y1 - h - 6, _fmt(v, prefix), size=10.5,
                           fill=MUTED, anchor="middle", mono=True)
            if i % label_every == 0:
                self._text(cx, y1 + 18, str(lab), size=11, fill=TEXT,
                           anchor="middle")

    def line(self, labels, values, color: str | None = None, prefix: str = "",
             dots: bool = True, label_every: int | None = None):
        """Line chart with dots — time series."""
        color = color or self._next_color()
        x0, y0, x1, y1 = self._frame()
        n = len(labels)
        vmax = max(values) * 1.12
        self._ygrid(x0, x1, y0, y1, vmax, prefix)
        step = (x1 - x0) / max(1, n - 1) if n > 1 else 0
        pts = []
        for i, (lab, v) in enumerate(zip(labels, values)):
            x = x0 + step * i
            y = y1 - (v / vmax) * (y1 - y0)
            pts.append((x, y))
        poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        self.el.append(
            f'<polyline points="{poly}" fill="none" stroke="{color}" '
            f'stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>'
        )
        if dots:
            for x, y in pts:
                self._circle(x, y, 3.5, color)
        every = label_every or max(1, math.ceil(n / 14))
        for i, (lab, _) in enumerate(zip(labels, values)):
            if i % every == 0:
                self._text(pts[i][0], y1 + 18, str(lab), size=11, fill=TEXT,
                           anchor="middle", mono=True)

    def histogram(self, values, bins: int = 20, color: str | None = None,
                  label: str = "count"):
        """Histogram — the shape of a distribution."""
        color = color or self._next_color()
        x0, y0, x1, y1 = self._frame(ylabel=label)
        lo, hi = min(values), max(values)
        if hi == lo:
            hi = lo + 1
        width = (hi - lo) / bins
        counts = [0] * bins
        for v in values:
            b = min(bins - 1, int((v - lo) / width))
            counts[b] += 1
        vmax = max(counts) * 1.12
        self._ygrid(x0, x1, y0, y1, vmax)
        slot = (x1 - x0) / bins
        bar_w = slot * 0.88
        for i, c in enumerate(counts):
            h = (c / vmax) * (y1 - y0)
            bx = x0 + slot * i + (slot - bar_w) / 2
            self._rect(bx, y1 - h, bar_w, h, color, rx=2, opacity=0.92)
        every = max(1, math.ceil(bins / 8))
        for i in range(0, bins, every):
            edge = lo + width * i
            self._text(x0 + slot * (i + 0.5), y1 + 18, _fmt(edge), size=10.5,
                       fill=MUTED, anchor="middle", mono=True)
        self._text(x1, y1 + 18, _fmt(hi), size=10.5, fill=MUTED,
                   anchor="end", mono=True)

    def scatter(self, xs, ys, color: str | None = None, r: float = 3.0,
                opacity: float = 0.55, xlabel: str = "", prefix: str = ""):
        """Scatter plot — relationships between two numbers."""
        color = color or self._next_color()
        x0, y0, x1, y1 = self._frame(ylabel=prefix.strip() or "y")
        xmax, ymax = max(xs), max(ys)
        self._ygrid(x0, x1, y0, y1, ymax, prefix)
        xticks = nice_ticks(0, xmax)
        for t in xticks:
            x = x0 + (t / xmax) * (x1 - x0)
            self._line(x, y0, x, y1, GRID, sw=1, opacity=0.35)
            self._text(x, y1 + 18, _fmt(t), size=10.5, fill=MUTED,
                       anchor="middle", mono=True)
        for x, y in zip(xs, ys):
            px = x0 + (x / xmax) * (x1 - x0)
            py = y1 - (y / ymax) * (y1 - y0)
            self._circle(px, py, r, color, opacity)
        if xlabel:
            self._text((x0 + x1) / 2, y1 + 38, xlabel, size=11, fill=MUTED,
                       anchor="middle", mono=True)

    # -- output -------------------------------------------------------------

    def svg(self) -> str:
        head = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" '
            f'width="{self.w}" height="{self.h}">\n'
        )
        return head + "  " + "\n  ".join(self.el) + "\n</svg>\n"

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.svg(), encoding="utf-8")
        return path