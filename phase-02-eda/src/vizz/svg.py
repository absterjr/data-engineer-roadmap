"""vizz — charts from scratch, in pure Python.

No matplotlib. No PIL. No third-party anything. SVG is plain text,
so stdlib Python can draw professional charts: the whole library is
scale math (data -> pixels) plus string building.

    from vizz import Figure

    fig = Figure(900, 500, "Monthly revenue")
    fig.line(months, revenue)
    fig.save("monthly_revenue.svg")

-----------------------------------------------------------------------
HOW A CHART LIBRARY ACTUALLY WORKS (the whole secret)
-----------------------------------------------------------------------
1. RESERVE SPACE:  the figure reserves margins around a "plot area"
   (the rectangle where data is allowed to be drawn).
2. SCALE:          map data values to pixels inside that rectangle:
                       pixel = area_start + (value / max_value) * area_size
   Every chart in this file is that one formula, applied to x and/or y.
3. TICKS:          humans don't want gridlines at 0, 37.3, 74.6 — they
   want 0, 50, 100. nice_ticks() below picks those 1-2-5 numbers.
4. EMIT STRINGS:   circles, lines, rects and text are appended to a
   list as SVG strings and joined at save() time.

Read `nice_ticks`, then `bar`, then `line` — the rest are variations.
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

BG = "#1F3864"       # navy background
CARD = "#0A1628"     # dark panel
GRID = "#2A4A7F"     # gridline blue
TEXT = "#FFFFFF"
MUTED = "#7FA8D9"


def _esc(s: str) -> str:
    """Escape the five XML entities so labels can't break the SVG.

    WHY: SVG *is* XML. A product named 'AT&T <big>' would inject raw
    '&' and '<' characters into the markup and corrupt the file. Every
    chart library does this; now you've seen it done by hand.
    """
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _fmt(v: float, prefix: str = "") -> str:
    """Compact number formatting for axis and value labels.

    8,191,234 -> '8.2M', 28,466 -> '28k', 2.55 -> '2.55'.
    Axis labels must be SHORT or they collide — that's the whole job.
    """
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
    """Axis ticks at 'nice' numbers (1, 2 or 5 x 10^k) — what humans expect.

    HOW (the classic 1-2-5 algorithm):
      1. rough step = value range / how many ticks we'd like (5)
      2. round that step UP to the nearest 1, 2 or 5 x 10^k
         (e.g. rough 58 -> 100; rough 0.9 -> 1; rough 2.4 -> 5... no:
         2.4 -> 5 is too big — the loop picks the FIRST of 1,2,5,10
         that is >= the rough step, so 2.4 -> 5? No: 1<2.4, 2<2.4,
         5>=2.4 -> step 5. Ticks land on multiples of the step.)
      3. lay out ticks from floor(lo) to ceil(hi) in that step

    Example: range 0..291 -> rough 58 -> step 100 -> ticks 0,100,200,300.
    """
    if hi <= lo:
        hi = lo + 1                      # a single value still deserves an axis
    span = hi - lo
    rough = span / max(1, target)
    # magnitude = the power of ten just below the rough step
    mag = 10 ** math.floor(math.log10(rough)) if rough > 0 else 1
    for mult in (1, 2, 5, 10):
        step = mult * mag
        if step >= rough:
            break                        # first 'nice' step big enough wins
    lo_t = math.floor(lo / step) * step  # snap the bottom DOWN
    hi_t = math.ceil(hi / step) * step   # snap the top UP
    ticks, t = [], lo_t
    while t <= hi_t + step * 1e-9:       # 1e-9 guards float drift
        ticks.append(round(t, 10))
        t += step
    return ticks


def _lerp_color(c1: str, c2: str, t: float) -> str:
    """Linear interpolation between two hex colors — the engine of every
    color scale. t=0 returns c1, t=1 returns c2, t=0.5 the midpoint.

    HOW: split '#RRGGBB' into three channels, lerp each channel
    separately, reassemble. (Color ramps made of 2+ stops are just
    several of these chained together.)
    """
    t = max(0.0, min(1.0, t))
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    r = round(r1 + (r2 - r1) * t)
    g = round(g1 + (g2 - g1) * t)
    b = round(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


class Figure:
    """A single SVG chart. Create it, call ONE chart method, save it.

    The Figure owns three things:
      - the canvas size (w, h) and background
      - the plot-area MARGINS: space reserved for title, y-labels, x-labels
      - `el`: the list of SVG element strings, in draw order
        (things drawn EARLIER sit BEHIND things drawn later — that's
        why gridlines are emitted before bars in every chart)
    """

    def __init__(self, width: int = 900, height: int = 520, title: str = "", bg: str = BG):
        self.w, self.h = width, height
        self.title = title
        self.bg = bg
        # margins: left holds y-axis labels, top the title, bottom x-labels
        self.m = dict(l=88, r=36, t=64, b=60)
        self.el: list[str] = []
        self._color_i = 0

    # -- primitives ---------------------------------------------------------
    # Each primitive appends one SVG element string. f-strings with :.1f
    # keep coordinates to one decimal place (smaller files, same look).

    def _next_color(self) -> str:
        """Cycle through the palette so successive charts differ."""
        c = PALETTE[self._color_i % len(PALETTE)]
        self._color_i += 1
        return c

    def _text(self, x, y, s, size=12, fill=TEXT, anchor="start", weight="400",
              mono=False, opacity=1.0, ls=0.5):
        """A text label. anchor='middle'/'end' controls what x means:
        start = left edge of text, middle = center, end = right edge."""
        font = "'Courier New', monospace" if mono else "'Inter', sans-serif"
        self.el.append(
            f'<text x="{x:.1f}" y="{y:.1f}" fill="{fill}" font-size="{size}" '
            f'font-weight="{weight}" text-anchor="{anchor}" letter-spacing="{ls}" '
            f'opacity="{opacity}" font-family="{font}">{_esc(s)}</text>'
        )

    def _rect(self, x, y, w, h, fill, rx=0, opacity=1.0, stroke=None, sw=1):
        """A rectangle — the background, and every BAR in every chart."""
        stroke_attr = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
        self.el.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'fill="{fill}" rx="{rx}" opacity="{opacity}"{stroke_attr}/>'
        )

    def _line(self, x1, y1, x2, y2, stroke, sw=1, opacity=1.0):
        """A straight line — gridlines and axis baselines."""
        self.el.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{stroke}" stroke-width="{sw}" opacity="{opacity}"/>'
        )

    def _circle(self, cx, cy, r, fill, opacity=1.0):
        """A circle — line-chart dots and scatter points."""
        self.el.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{fill}" opacity="{opacity}"/>'
        )

    # -- frame --------------------------------------------------------------

    def _frame(self, ylabel: str = "") -> tuple[float, float, float, float]:
        """Draw background + title, return the PLOT AREA bounds.

        Returns (x0, y0, x1, y1): top-left and bottom-right of the
        rectangle data may be drawn in. Every chart computes positions
        from these four numbers — never from the canvas edges.
        """
        self._rect(0, 0, self.w, self.h, self.bg)
        if self.title:
            self._text(24, 34, self.title, size=19, weight="700", ls=0.5)
        x0, y0 = self.m["l"], self.m["t"]
        x1, y1 = self.w - self.m["r"], self.h - self.m["b"]
        if ylabel:
            self._text(24, y0 - 12, ylabel, size=11, fill=MUTED, mono=True)
        return x0, y0, x1, y1

    def _ygrid(self, x0, x1, y0, y1, ymax, prefix=""):
        """Horizontal gridlines + y tick labels for a 0..ymax scale.

        THE scale formula in its purest form:
            pixel_y = y1 - (tick / ymax) * (y1 - y0)
        y1 is the BOTTOM (SVG's y grows downward), so bigger values =
        smaller pixel_y = higher on screen.
        """
        for t in nice_ticks(0, ymax):
            if t == 0:
                continue                              # the axis line covers 0
            y = y1 - (t / ymax) * (y1 - y0)
            self._line(x0, y, x1, y, GRID, sw=1, opacity=0.55)
            self._text(x0 - 8, y + 4, _fmt(t, prefix), size=11, fill=MUTED,
                       anchor="end", mono=True)       # +4 centers on the line
        self._line(x0, y1, x1, y1, GRID, sw=1.5)      # the x-axis baseline

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
        """Horizontal bars — best for ranked categories with long names
        ('United Kingdom' fits; it wouldn't under a vertical bar).

        GEOMETRY: divide the plot height into n equal SLOTS, center each
        bar in its slot at 62% thickness (leaves even white space). Bar
        LENGTH = value / vmax * plot width — the scale formula again.
        Gridlines are drawn BEFORE the bars (earlier = behind).
        """
        color = color or self._next_color()
        x0, y0, x1, y1 = self._frame(ylabel=prefix.strip() or "value")
        n = len(labels)
        vmax = max(values) * 1.06            # 6% headroom for value labels
        row_h = (y1 - y0) / n
        bar_h = row_h * 0.62
        self._xgrid(x0, x1, y0, y1, vmax, prefix)
        for i, (lab, v) in enumerate(zip(labels, values)):
            cy = y0 + row_h * (i + 0.5)      # vertical center of slot i
            w = (v / vmax) * (x1 - x0)
            self._rect(x0, cy - bar_h / 2, w, bar_h, color, rx=3, opacity=0.92)
            self._text(x0 - 8, cy + 4, str(lab), size=12, fill=TEXT, anchor="end")
            if value_labels:
                self._text(x0 + w + 6, cy + 4, _fmt(v, prefix), size=11,
                           fill=MUTED, mono=True)

    def bar(self, labels, values, color: str | None = None, prefix: str = "",
            value_labels: bool = False, label_every: int = 1):
        """Vertical bars — best for short ordered categories (months,
        weekdays, hours). label_every thins crowded x-labels."""
        color = color or self._next_color()
        x0, y0, x1, y1 = self._frame()
        n = len(labels)
        vmax = max(values) * 1.12
        self._ygrid(x0, x1, y0, y1, vmax, prefix)
        slot = (x1 - x0) / n
        bar_w = slot * 0.62
        for i, (lab, v) in enumerate(zip(labels, values)):
            cx = x0 + slot * (i + 0.5)
            h = (v / vmax) * (y1 - y0)       # bar grows UP from the baseline
            self._rect(cx - bar_w / 2, y1 - h, bar_w, h, color, rx=3, opacity=0.92)
            if value_labels:
                self._text(cx, y1 - h - 6, _fmt(v, prefix), size=10.5,
                           fill=MUTED, anchor="middle", mono=True)
            if i % label_every == 0:
                self._text(cx, y1 + 18, str(lab), size=11, fill=TEXT,
                           anchor="middle")

    def line(self, labels, values, color: str | None = None, prefix: str = "",
             dots: bool = True, label_every: int | None = None):
        """Line chart with dots — time series.

        GEOMETRY: x positions are EVENLY SPACED (slot width = plot width
        / (n-1)), y positions come from the scale formula. All points
        join into one <polyline>. label_every thins crowded x-labels
        (default: show at most ~14).
        """
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
        # one polyline element joins every point — cheaper than n-1 lines
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
        """Histogram — the shape of a distribution.

        HOW: cut the value range into `bins` equal-width buckets, COUNT
        how many values fall in each, then draw those counts as a bar
        chart. (A histogram is just a bar chart of counts — the work is
        in the binning: bucket index = int((v - lo) / bin_width), clamped
        so the max value lands in the last bin, not one past it.)
        """
        color = color or self._next_color()
        x0, y0, x1, y1 = self._frame(ylabel=label)
        lo, hi = min(values), max(values)
        if hi == lo:
            hi = lo + 1                      # constant data still gets an axis
        width = (hi - lo) / bins
        counts = [0] * bins
        for v in values:
            b = min(bins - 1, int((v - lo) / width))
            counts[b] += 1
        vmax = max(counts) * 1.12
        self._ygrid(x0, x1, y0, y1, vmax)
        slot = (x1 - x0) / bins
        bar_w = slot * 0.88                  # histogram bars nearly touch
        for i, c in enumerate(counts):
            h = (c / vmax) * (y1 - y0)
            bx = x0 + slot * i + (slot - bar_w) / 2
            self._rect(bx, y1 - h, bar_w, h, color, rx=2, opacity=0.92)
        every = max(1, math.ceil(bins / 8))  # thin the edge labels
        for i in range(0, bins, every):
            edge = lo + width * i
            self._text(x0 + slot * (i + 0.5), y1 + 18, _fmt(edge), size=10.5,
                       fill=MUTED, anchor="middle", mono=True)
        self._text(x1, y1 + 18, _fmt(hi), size=10.5, fill=MUTED,
                   anchor="end", mono=True)

    def scatter(self, xs, ys, color: str | None = None, r: float = 3.0,
                opacity: float = 0.55, xlabel: str = "", prefix: str = ""):
        """Scatter plot — relationships between two numbers.

        Both axes get the scale formula; each point is one circle.
        opacity < 1 lets dense regions show as darker clumps.
        """
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

    # -- unconventional charts ----------------------------------------------
    # Four chart types you rarely see in dashboards — each earns its place
    # by answering a question bars and lines answer badly.

    def calendar_heatmap(self, dates, values, color_low: str = CARD,
                         color_high: str = "#00D4FF"):
        """Calendar heatmap — a value per DAY laid out as a real calendar.

        WHAT: GitHub's contribution graph. Columns are weeks, rows are
        weekdays; color encodes the value. Unbeatable for 'show me every
        day at once' — daily spikes, quiet weekends, and end-of-month
        surges are visible as PATTERNS, not as 365 bars.

        HOW:
          1. map each date to (week column, weekday row) using ISO
             calendar math: col = ISO week number - first week, row = weekday
          2. color each day's cell by interpolating color_low -> color_high
             with t = value's position in the min..max range
          3. month labels above the first week in which they appear
        """
        x0, y0, x1, y1 = self._frame()
        # normalize input to (date, value) pairs, sorted by date
        pairs = sorted(
            (d.date() if hasattr(d, "date") else d, v) for d, v in zip(dates, values)
        )
        if not pairs:
            return
        first = pairs[0][0]

        # week column of a date = whole weeks since the first date
        def col_of(d):
            return (d - first).days // 7

        n_weeks = max(col_of(d) for d, _ in pairs) + 1
        vmax = max(v for _, v in pairs)
        vmin = min(v for _, v in pairs)
        span = (vmax - vmin) or 1

        cw = (x1 - x0) / n_weeks
        ch = (y1 - y0) / 7
        pad = min(cw, ch) * 0.12         # gap between cells

        last_month = None
        for d, v in pairs:
            col, row = col_of(d), d.weekday()   # Monday = row 0
            t = (v - vmin) / span
            cx, cy = x0 + col * cw, y0 + row * ch
            self._rect(cx + pad, cy + pad, cw - 2 * pad, ch - 2 * pad,
                       _lerp_color(color_low, color_high, t), rx=2)
            # month label: once, above the first week where a new month starts
            if d.month != last_month:
                self._text(cx + pad, y0 - 8, d.strftime("%b"), size=11,
                           fill=MUTED, anchor="start", mono=True)
                last_month = d.month
        # weekday labels on the left (Mon, Wed, Fri only — thin to fit)
        for r, name in [(0, "Mon"), (2, "Wed"), (4, "Fri")]:
            self._text(x0 - 8, y0 + ch * (r + 0.5) + 4, name, size=10.5,
                       fill=MUTED, anchor="end", mono=True)

    def slope(self, items, left_values, right_values,
              left_label: str = "before", right_label: str = "after"):
        """Slope chart — before vs after for the same categories.

        WHAT: two vertical axes (left = before, right = after); one line
        per category connecting its two values. Lines fanning UP grew,
        lines diving DOWN shrank — direction is the message. Perfect for
        'how did our top markets move between two periods?', which a
        grouped bar chart buries.

        HOW: both sides share ONE y-scale (comparable!), each item is a
        two-point polyline colored by whether it rose or fell.
        """
        color = self._next_color()
        x0, y0, x1, y1 = self._frame()
        pad = 150                          # room for labels outside the axes
        xl, xr = x0 + pad, x1 - pad
        vmax = max(max(left_values), max(right_values)) * 1.06
        y = lambda v: y1 - (v / vmax) * (y1 - y0)

        self._line(xl, y0, xl, y1, GRID, sw=1.5)
        self._line(xr, y0, xr, y1, GRID, sw=1.5)
        self._text(xl, y0 - 12, left_label, size=12, fill=MUTED,
                   anchor="middle", mono=True)
        self._text(xr, y0 - 12, right_label, size=12, fill=MUTED,
                   anchor="middle", mono=True)
        for t in nice_ticks(0, vmax):
            self._text(xl - 8, y(t) + 4, _fmt(t), size=10.5, fill=MUTED,
                       anchor="end", mono=True)

        for lab, lv, rv in zip(items, left_values, right_values):
            rose = rv >= lv
            c = "#7BED9F" if rose else "#FF6B6B"   # mint up, coral down
            self._line(xl, y(lv), xr, y(rv), c, sw=2)
            self._circle(xl, y(lv), 3.5, c)
            self._circle(xr, y(rv), 3.5, c)
            self._text(xl - 10, y(lv) + 4, str(lab), size=11.5, fill=TEXT,
                       anchor="end")
            self._text(xr + 10, y(rv) + 4, str(lab), size=11.5, fill=TEXT,
                       anchor="start")
        self._text((xl + xr) / 2, y1 + 30, "mint = up · coral = down",
                   size=10.5, fill=MUTED, anchor="middle", mono=True)

    def ridgeline(self, series: list[tuple[str, list]], bins: int = 30,
                  peak_fraction: float = 0.55, xlabel: str = "",
                  prefix: str = ""):
        """Ridgeline plot ('joyplot') — one distribution per group,
        stacked with overlap so the whole family reads as a landscape.

        WHAT: compares DISTRIBUTIONS across groups. A bar chart of
        averages hides shape — bimodal? long-tailed? A ridgeline shows
        every group's entire distribution at once. Here: order-value
        distributions per quarter.

        HOW:
          1. all groups share ONE set of bin edges (comparable shapes)
          2. per group: histogram counts -> a polygon whose top edge is
             the distribution, sitting on that group's baseline
          3. baselines march UP the canvas; ridges are drawn back-to-
             front (top first) so each overlaps the one behind it —
             the overlap IS the aesthetic
          4. fill is the dark panel color, stroke is the group color:
             only the top edge of each ridge stays visible.
        """
        x0, y0, x1, y1 = self._frame(ylabel=xlabel)
        n = len(series)
        all_vals = [v for _, vals in series for v in vals]
        lo, hi = min(all_vals), max(all_vals)
        if hi == lo:
            hi = lo + 1
        width = (hi - lo) / bins

        # shared bin edges -> shared x positions
        xs = [x0 + (x1 - x0) * i / bins for i in range(bins)]
        ridge_h = (y1 - y0) * peak_fraction
        # baselines: first group at the bottom, later groups march up
        base = lambda i: y1 - i * ((y1 - y0) - ridge_h) / max(1, n - 1) if n > 1 else y1

        vmax = max(
            max(
                sum(1 for v in vals if lo + width * b <= v < lo + width * (b + 1))
                for b in range(bins)
            )
            for _, vals in series
        )
        if vmax == 0:
            vmax = 1

        # draw top (last) groups first so bottom groups overlap them
        for i in range(n - 1, -1, -1):
            lab, vals = series[i]
            counts = [0] * bins
            for v in vals:
                counts[min(bins - 1, int((v - lo) / width))] += 1
            pts = [(x0, base(i))] + [
                (xs[b], base(i) - counts[b] / vmax * ridge_h) for b in range(bins)
            ] + [(x1, base(i))]
            poly = " ".join(f"{px:.1f},{py:.1f}" for px, py in pts)
            c = PALETTE[i % len(PALETTE)]
            self.el.append(
                f'<polygon points="{poly}" fill="{CARD}" fill-opacity="0.92" '
                f'stroke="{c}" stroke-width="1.8"/>'
            )
            self._text(x0 - 8, base(i) - 4, str(lab), size=11, fill=TEXT,
                       anchor="end", mono=True)
        # value axis labels along the bottom
        for t in nice_ticks(lo, hi, 5):
            x = x0 + (t - lo) / (hi - lo) * (x1 - x0)
            self._text(x, y1 + 18, _fmt(t, prefix), size=10.5, fill=MUTED,
                       anchor="middle", mono=True)

    def waffle(self, labels, values, total_squares: int = 100, cols: int = 10,
               prefix: str = ""):
        """Waffle chart — the total as a grid of unit squares.

        WHAT: each square = one unit (usually 1% of the total). Where a
        pie chart forces angle-reading, a waffle lets you literally
        COUNT squares. Great for shares that matter in whole units
        ('84 of 100 squares are the UK').

        HOW:
          1. convert values to square counts with LARGEST-REMAINDER
             rounding so the counts sum to exactly total_squares
             (naive rounding would give 99 or 101 squares)
          2. fill the grid row by row, one color per category
          3. legend to the right: swatch + label + true share
        """
        x0, y0, x1, y1 = self._frame()
        total = sum(values) or 1

        # largest-remainder rounding: floor each share, then hand the
        # leftover squares to the biggest fractional remainders
        exact = [v / total * total_squares for v in values]
        counts = [int(e) for e in exact]
        remainder = total_squares - sum(counts)
        order = sorted(range(len(values)), key=lambda i: exact[i] - counts[i], reverse=True)
        for i in order[:remainder]:
            counts[i] += 1

        rows = math.ceil(total_squares / cols)
        cell = min((x1 - x0 - 200) / cols, (y1 - y0) / rows)   # 200px for legend
        gx, gy = x0, y0 + ((y1 - y0) - cell * rows) / 2        # vertically center

        idx = 0
        for cat_i, count in enumerate(counts):
            c = PALETTE[cat_i % len(PALETTE)]
            for _ in range(count):
                if idx >= total_squares:
                    break
                r, cc = divmod(idx, cols)
                self._rect(gx + cc * cell + 1.5, gy + r * cell + 1.5,
                           cell - 3, cell - 3, c, rx=2, opacity=0.95)
                idx += 1

        # legend: swatch, label, and the real (unrounded) share
        ly = y0 + 10
        for cat_i, (lab, v) in enumerate(zip(labels, values)):
            c = PALETTE[cat_i % len(PALETTE)]
            self._rect(x0 + cols * cell + 24, ly - 9, 12, 12, c, rx=2)
            self._text(x0 + cols * cell + 44, ly + 2, f"{lab}  {_fmt(v / total * 100, prefix)}%",
                       size=12, fill=TEXT)
            ly += 24

    # -- output -------------------------------------------------------------

    def svg(self) -> str:
        """Assemble the final SVG document: header + all elements."""
        head = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" '
            f'width="{self.w}" height="{self.h}">\n'
        )
        return head + "  " + "\n  ".join(self.el) + "\n</svg>\n"

    def save(self, path: str | Path) -> Path:
        """Write the SVG to disk (creating parent folders if needed)."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.svg(), encoding="utf-8")
        return path