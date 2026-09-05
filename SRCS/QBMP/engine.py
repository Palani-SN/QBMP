"""
QBMP - Quoins, Bricks, Mortar & Pointing.

Subclass QBMP, declare a `model` dict, and decorate one engine per output with
@rule. The sampler lays quoins first - sparse landmarks placed at equidistant
points in OUTPUT space using the highest-weight input - then widens along each
next input in turn, tiling the gap the previous pass left open, and finally
points mortar into whatever bins are still empty.

Every input and every output is exactly one of two kinds, never both. A
CONTINUATIONAL column carries a continuous "range": (min, max) and is swept and
solved. A COMBINATIONAL column carries "categories" in place of "range" and is
enumerated:

    "locality_tier": {"categories": ["A", "B", "C"], "default": "B"}

Pointing - the fourth course, which rebalances a covered range toward flatness -
is on the roadmap; the three courses that buy coverage are what runs today.
"""

import functools
import html
import itertools
import math
import random
import time
from datetime import datetime
from pathlib import Path
from typing import ClassVar

import pandas as pd


def rule(output_name: str):
    """
    Bind a method to an output and complete its kwargs.

    The output's `weights` dict is the dependency edge list - it originates at
    the output and connects to the N inputs that output depends on. Whatever the
    sampler has not assigned for the current pass is filled in from that input's
    declared `default`, so the body always receives every input it depends on
    and never has to check for absence.

    Keys the sampler passes that this output does not depend on are dropped, so
    a whole row can be handed to any engine.
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(self, **assigned):
            deps = self.model["Outputs"][output_name]["weights"]
            kwargs = {
                name: assigned.get(name, self.model["Inputs"][name]["default"])
                for name in deps
            }
            return fn(self, **kwargs)

        wrapper._qbmp_output = output_name
        return wrapper
    return decorator


class QBMP:

    model: ClassVar[dict] = {}

    # Forward-sweep resolution used to land on output targets without having to
    # invert the rule function.
    PROBE = 400

    # Relative closeness at which a target counts as met and the cascade stops
    # falling through to lower-weight inputs.
    TOL = 1e-3

    # Average rows a bin needs before its emptiness means anything. The dyadic
    # ladder stops doubling once bins would hold fewer than this.
    MIN_PER_BIN = 8

    # Past this many slices a combinational band is too narrow to show a split,
    # so its ladder stops here even when the continuational one climbs further.
    MAX_BANDS = 256

    # The finest resolution worth asking for, whatever the caller requests.
    #
    # Readability binds first. A rung this deep already draws each bar at well
    # under half a pixel on a normal page, so the rung stops being readable
    # even when it is completely full - and an unreadable rung certifies
    # nothing, which is the only thing the ladder is there to do.
    #
    # The solver gives out later than the eye does: refining six rounds down
    # from a PROBE-wide grid it still places a value inside the bin it aims at
    # at 8192 bins, and only breaks down at 16384, which comes back 39% empty.
    # That headroom is deliberate - the ceiling is set by what can be read,
    # not by what can be solved, so every rung shown is a rung that means
    # something. Raise it if you are reading the numbers rather than the bars.
    #
    # One ceiling for every column, deliberately. A per-column limit derived
    # from each range would have every column wanting a different bin count out
    # of one shared row set, which there is no way to satisfy at once.
    MAX_BINS = 2048

    # One colour per option, held consistent between a column's composition bar
    # and every band of its ladder, so the legend is learned once. Chosen for
    # distinct hue AND lightness, so they survive both themes and greyscale.
    CATEGORY_COLOURS: ClassVar[tuple] = (
        "#4E79A7", "#F28E2B", "#59A14F", "#B07AA1",
        "#76B7B2", "#9C755F", "#D4A017", "#8CA252",
    )

    SHEET_CSS: ClassVar[str] = """
:root {
  --bg:#fbfaf8; --panel:#fff; --ink:#1a1a1a; --muted:#6b6b6b; --line:#e6e2dc;
  --bar:#3b6ea5; --bar-lo:#9db9d6; --gap:#c8553d; --good:#3f7d58; --accent:#8a6d3b;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg:#16181c; --panel:#1d2025; --ink:#e8e6e3; --muted:#9a9691; --line:#2d3138;
    --bar:#6fa3d6; --bar-lo:#3c5a7a; --gap:#e0705a; --good:#6fbf8e; --accent:#c9a86a;
  }
}
* { box-sizing:border-box; }
body {
  margin:0; background:var(--bg); color:var(--ink);
  font:14px/1.55 ui-sans-serif,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
}
.wrap { max-width:min(1580px, 97vw); margin:0 auto;
        padding:40px 24px 72px; }
/* prose stays narrow enough to read; plots and tables run wide */
.sub, footer { max-width:920px; }
h1 { font-size:26px; letter-spacing:-.02em; margin:0 0 4px; font-weight:640; }
h2 { font-size:17px; letter-spacing:-.01em; margin:0; font-weight:620; }
.sub { color:var(--muted); margin:0 0 30px; font-size:13px; }
.meta { display:flex; flex-wrap:wrap; gap:0 30px; margin:0 0 30px;
        padding:14px 18px; background:var(--panel); border:1px solid var(--line);
        border-radius:9px; }
.meta div { font-size:12.5px; }
.meta span { display:block; color:var(--muted); font-size:11px;
             text-transform:uppercase; letter-spacing:.07em; margin-bottom:2px; }
.mono { font-family:ui-monospace,SFMono-Regular,"Cascadia Code",Consolas,monospace;
        font-variant-numeric:tabular-nums; }
table.sum { width:100%; border-collapse:collapse; margin:0 0 34px; font-size:13px; }
table.sum th { text-align:left; font-weight:600; color:var(--muted); font-size:11px;
               text-transform:uppercase; letter-spacing:.07em;
               border-bottom:1px solid var(--line); padding:0 12px 7px 0; }
table.sum td { padding:9px 12px 9px 0; border-bottom:1px solid var(--line); }
table.sum tr:last-child td { border-bottom:none; }
.card { background:var(--panel); border:1px solid var(--line); border-radius:9px;
        padding:20px 16px 12px; margin:0 0 20px; }
.chead { display:flex; align-items:baseline; justify-content:space-between;
         gap:16px; flex-wrap:wrap; margin-bottom:4px; }
.facts { color:var(--muted); font-size:12.5px; margin:0 0 18px; }
.facts b { color:var(--ink); font-weight:600; }
.lvl { display:grid; grid-template-columns:58px 1fr 96px; align-items:center;
       gap:10px; padding:3px 0; }
.lvl-n { text-align:right; color:var(--muted); font-size:12px; }
.lvl.beyond .lvl-n { opacity:.55; font-style:italic; }
.lvl.beyond .strip { opacity:.8; }
.lvl-note { color:var(--muted); font-size:11.5px; }
.strip { width:100%; height:30px; display:block; }
.strip rect.bar  { fill:var(--bar); }
.strip rect.gap  { fill:var(--gap); opacity:.85; }
.strip rect:hover { fill:var(--accent); }
.strip { cursor:crosshair; }
.legend { display:flex; gap:18px; align-items:center; color:var(--muted);
          font-size:11.5px; margin:16px 0 4px; }
.key { display:inline-block; width:10px; height:10px; border-radius:2px;
       vertical-align:-1px; margin-right:5px; }
.ok   { color:var(--good); font-weight:600; }
.bad  { color:var(--gap); font-weight:600; }
.warn { color:var(--accent); font-weight:600; }
.muted{ color:var(--muted); }
footer { color:var(--muted); font-size:12px; margin-top:34px;
         border-top:1px solid var(--line); padding-top:16px; }

/* accordion */
details.card > summary { list-style:none; cursor:pointer; display:flex;
    align-items:baseline; justify-content:space-between; gap:16px;
    flex-wrap:wrap; margin:-2px 0 2px; }
details.card > summary::-webkit-details-marker { display:none; }
details.card > summary::before { content:"\25B8"; color:var(--muted);
    margin-right:9px; font-size:11px; transition:transform .15s; }
details.card[open] > summary::before { content:"\25BE"; }
summary h2 { display:inline; }
.kind { font-size:10.5px; text-transform:uppercase; letter-spacing:.09em;
    color:var(--muted); border:1px solid var(--line); border-radius:20px;
    padding:2px 9px; margin-left:10px; vertical-align:2px; }

/* overall panels */
.panel { margin:14px 0 20px; padding:16px 14px; border:1px solid var(--line);
    border-radius:7px; background:var(--bg); }
.panel-h { font-size:11px; text-transform:uppercase; letter-spacing:.08em;
    color:var(--muted); margin:0 0 12px; }
.comp { display:grid; grid-template-columns:auto 1fr 56px; gap:7px 12px;
    align-items:center; }
.comp-n { font-size:12.5px; white-space:nowrap; }
.comp-n i { display:inline-block; width:9px; height:9px; border-radius:2px;
    margin-right:7px; vertical-align:0; }
.comp-t { height:14px; border-radius:3px; background:var(--line);
    overflow:hidden; }
.comp-t span { display:block; height:100%; border-radius:3px; }
.comp-v { text-align:right; font-size:12.5px; }
.absent { color:var(--gap); font-weight:600; }
.quant { display:flex; justify-content:space-between; margin-top:9px;
    font-size:11.5px; color:var(--muted); }
.quant b { color:var(--ink); font-weight:600; display:block; }
.dens { width:100%; height:64px; display:block; }
.dens path  { fill:var(--bar); opacity:.30; }
.dens polyline { fill:none; stroke:var(--bar); stroke-width:1.6; }
.dens line { stroke:var(--muted); stroke-width:1; stroke-dasharray:2 2; }

/* download */
.meta { align-items:center; }
.dl { margin-left:auto; align-self:center; display:inline-flex;
    align-items:center; gap:8px; padding:9px 14px; border:1px solid var(--line);
    border-radius:7px; background:var(--bg); color:var(--ink);
    text-decoration:none; font-size:12.5px; font-weight:600; white-space:nowrap; }
.dl:hover { border-color:var(--bar); color:var(--bar); }
.dl svg { width:13px; height:13px; fill:none; stroke:currentColor;
    stroke-width:1.8; stroke-linecap:round; stroke-linejoin:round; }
.dl-size { color:var(--muted); font-weight:400; }
.dl + .dl { margin-left:8px; }

/* zoom */
svg.context { width:100%; display:block; cursor:ew-resize; }
.dens, svg.context, .strip { touch-action:none; }
rect.glass { fill:var(--ink); opacity:.13; pointer-events:none; }
rect.sel   { fill:var(--accent); opacity:.28; pointer-events:none; }
.zoom { font-size:11.5px; color:var(--accent); font-weight:600; }
.ctx-h { font-size:11px; text-transform:uppercase; letter-spacing:.08em;
    color:var(--muted); margin:16px 0 6px; }

/* ladder colours */
.strip rect.mortar { fill:var(--good); }
.strip rect.void   { fill:var(--line); }
"""

    SHEET_JS: ClassVar[str] = r"""
(function () {
  var FULL = 1000, MIN = 4, NS = "http://www.w3.org/2000/svg";

  function fmt(v, span) {
    var p = span >= 1000 ? 0 : (span >= 10 ? 1 : 2);
    return v.toLocaleString(undefined,
      { minimumFractionDigits: p, maximumFractionDigits: p });
  }

  document.querySelectorAll("details.card").forEach(function (card) {
    var strips = [].slice.call(card.querySelectorAll("svg.strip"));
    if (!strips.length) { return; }

    var ctx = card.querySelector("svg.context") || card.querySelector("svg.dens");
    var out = card.querySelector(".zoom");
    var kind = card.dataset.kind;
    var lo = parseFloat(card.dataset.lo || "0");
    var hi = parseFloat(card.dataset.hi || "0");
    var rows = parseInt(card.dataset.rows || "0", 10);
    var x0 = 0, x1 = FULL;

    var gl = ctx && ctx.querySelector(".glass-l");
    var gr = ctx && ctx.querySelector(".glass-r");

    function readout() {
      if (x1 - x0 >= FULL) { return ""; }
      if (kind === "range") {
        var span = hi - lo;
        return "showing " + fmt(lo + span * x0 / FULL, span) +
               " to " + fmt(lo + span * x1 / FULL, span) +
               "  \u00b7  double-click to reset";
      }
      return "showing rows " + Math.round(rows * x0 / FULL).toLocaleString() +
             " to " + Math.round(rows * x1 / FULL).toLocaleString() +
             "  \u00b7  double-click to reset";
    }

    function apply() {
      strips.forEach(function (el) {
        el.setAttribute("viewBox", x0 + " 0 " + (x1 - x0) + " 30");
      });
      if (gl) {
        gl.setAttribute("width", x0);
        gr.setAttribute("x", x1);
        gr.setAttribute("width", FULL - x1);
      }
      if (out) { out.textContent = readout(); }
    }

    // `whole` marks the context, which never zooms and so always reads 0..FULL.
    function draggable(el, whole) {
      el.addEventListener("pointerdown", function (ev) {
        if (ev.button) { return; }
        ev.preventDefault();

        var box = el.getBoundingClientRect();
        var a = whole ? 0 : x0, b = whole ? FULL : x1;
        var at = function (e) {
          var f = (e.clientX - box.left) / box.width;
          return a + Math.min(1, Math.max(0, f)) * (b - a);
        };

        var from = at(ev), to = from;
        var sel = document.createElementNS(NS, "rect");
        sel.setAttribute("class", "sel");
        sel.setAttribute("y", "0");
        sel.setAttribute("height", "100");
        el.appendChild(sel);

        var move = function (e) {
          to = at(e);
          sel.setAttribute("x", Math.min(from, to));
          sel.setAttribute("width", Math.abs(to - from));
        };
        var done = function () {
          document.removeEventListener("pointermove", move);
          document.removeEventListener("pointerup", done);
          sel.remove();
          if (Math.abs(to - from) >= MIN) {
            x0 = Math.min(from, to);
            x1 = Math.max(from, to);
            apply();
          }
        };

        document.addEventListener("pointermove", move);
        document.addEventListener("pointerup", done);
      });

      el.addEventListener("dblclick", function () {
        x0 = 0; x1 = FULL; apply();
      });
    }

    strips.forEach(function (el) { draggable(el, false); });
    if (ctx) { draggable(ctx, true); }
    apply();
  });
})();
"""

    def __init__(self, seed):
        self.seed = seed
        self.rng = random.Random(seed)
        self.engines = self._bind_engines()
        self.outputs = list(self.model["Outputs"])
        self.report = None

    def _bind_engines(self):
        """Resolve each output's "engine" name to its decorated method."""
        bound = {}
        for name, spec in self.model["Outputs"].items():
            fn = getattr(self, spec["engine"], None)
            if fn is None:
                raise ValueError(
                    f"Output {name} names engine {spec['engine']}, which does not exist.")
            if getattr(fn, "_qbmp_output", None) != name:
                raise ValueError(
                    f"Engine {spec['engine']} is not decorated with @rule({name}).")
            bound[name] = fn
        return bound

    def _selected(self, outputs):
        """
        Validate an output selection and normalise it to a list.

        Order matters: the first name drives the sampling hierarchy, so putting
        an output first is how you ask for a dataset built around it.
        """
        declared = list(self.model["Outputs"])

        if outputs is None:
            return declared
        if isinstance(outputs, str):
            outputs = [outputs]

        outputs = list(outputs)
        if not outputs:
            raise ValueError("outputs is empty; name at least one output.")

        unknown = [o for o in outputs if o not in self.model["Outputs"]]
        if unknown:
            raise ValueError(
                f"Unknown output(s) {unknown}; declared outputs are {declared}.")

        seen = dict.fromkeys(outputs)
        return list(seen)

    # ------------------------------------------------------------------
    # Column kinds. A column is CONTINUATIONAL - declared with a "range" -
    # or COMBINATIONAL - declared with "categories". Never both. Continuous
    # values are swept and solved; categories are enumerated.
    # ------------------------------------------------------------------

    def _combinational(self, name):
        """True if this input or output is declared with `categories`."""
        spec = self.model["Inputs"].get(name) or self.model["Outputs"][name]
        return "categories" in spec

    def _options(self, name):
        """The declared options of a combinational column."""
        spec = self.model["Inputs"].get(name) or self.model["Outputs"][name]
        return list(spec["categories"])

    def _continuational(self, outputs):
        """Selected outputs that carry a range, in selection order."""
        return [o for o in outputs if not self._combinational(o)]

    def _ranked(self, outputs):
        """
        Every input the selection depends on, ranked quoins -> mortar.

        The first selected output sets the order. Inputs only the other
        outputs depend on follow, ranked by the highest weight any gives them.
        """
        primary = self.model["Outputs"][outputs[0]]["weights"]
        ordered = sorted(primary, key=primary.get, reverse=True)

        extra = {}
        for name in outputs[1:]:
            for col, weight in self.model["Outputs"][name]["weights"].items():
                if col not in primary:
                    extra[col] = max(extra.get(col, 0), weight)

        return ordered + sorted(extra, key=extra.get, reverse=True)

    def _tiers(self, outputs):
        """Continuous inputs in play, ordered quoins -> bricks -> mortar."""
        return [c for c in self._ranked(outputs) if not self._combinational(c)]

    def _categoricals(self, outputs):
        """Combinational inputs in play, heaviest first."""
        return [c for c in self._ranked(outputs) if self._combinational(c)]

    def _combos(self, outputs):
        """
        Every combination of the combinational inputs, as dicts to overlay.

        Categories are finite, so they are enumerated rather than sampled -
        the full cartesian product, which guarantees every option and every
        interaction between them appears. `min_rows` budgets the continuous
        sampling *within* each combination, so the product multiplies on top
        of it rather than competing with it.

        This is the single place a cheaper covering strategy would slot in -
        pairwise rather than full product - once enough combinational inputs
        make the product expensive. With k columns the product is the size of
        their option counts multiplied; pairwise grows logarithmically.
        """
        cats = self._categoricals(outputs)
        if not cats:
            return [{}]

        return [dict(zip(cats, values))
                for values in itertools.product(*(self._options(c) for c in cats))]

    def _defaults(self):
        return {n: s["default"] for n, s in self.model["Inputs"].items()}

    def _grid(self, input_name, count):
        """
        Candidate values for an input.

        A combinational input yields its declared options - there is nothing
        between "Studio" and "Villa" to interpolate, so the whole option list
        is the grid regardless of `count`.
        """
        if self._combinational(input_name):
            return self._options(input_name)

        lo, hi = self.model["Inputs"][input_name]["range"]
        if count == 1:
            return [(lo + hi) / 2]
        step = (hi - lo) / (count - 1)
        return [lo + i * step for i in range(count)]

    def _nearest(self, engine, row, col, targets):
        """
        Values of `col` that drive this row's output closest to each target.

        A forward sweep plus nearest-match, rather than solving for the input,
        so the rule function may be non-monotonic or discontinuous without the
        sampler caring.
        """
        probed = [(engine(**{**row, col: v}), v)
                  for v in self._grid(col, self.PROBE)]
        return [min(probed, key=lambda p: abs(p[0] - t))[1] for t in targets]

    def _solve(self, engine, tiers, target, start=None, tol=None):
        """
        Drive the output to `target` by adjusting inputs in weight order.

        The heaviest input does the coarse work. Whatever residual it cannot
        close - because it has run to the end of its own range - falls through
        to the next input, and so on down to mortar. That cascade is what
        reaches the corners of the output range, which no single input can:
        the declared maximum needs several inputs at their limits at once.

        Interior targets are met by the first input alone and the rest stay at
        their defaults, so the cascade costs nothing away from the extremes.

        `tol` is how close counts as arrived, absolute. It matters more than it
        looks: the default is relative, and at a target of 360 that is 0.36 -
        wider than a 1024-bin, so the cascade would stop one bin short of the
        cavity it was aiming at. Mortar passes a fraction of the bin width.

        `start` seeds the row - during a pass it carries the combination's
        frozen categories, so the cascade only moves continuous inputs and the
        enumeration stays intact. Mortar passes a wider tier list instead, and
        may re-choose categories to reach a cavity no combination alone holds.
        """
        row = {**self._defaults(), **(start or {})}
        for col in tiers:
            probed = [(engine(**{**row, col: v}), v)
                      for v in self._grid(col, self.PROBE)]
            reached, row[col] = min(probed, key=lambda p: abs(p[0] - target))

            if not self._combinational(col):
                reached, row[col] = self._refine(engine, row, col, target,
                                                 row[col], reached)

            if abs(reached - target) <= (tol or self.TOL * max(abs(target), 1.0)):
                break
        return row

    def _refine(self, engine, row, col, target, best, reached, rounds=6):
        """
        Narrow in on a target far finer than the sweep grid allows.

        One step of the PROBE grid can move the output further than a whole bin
        is wide, which leaves mortar unable to land inside the cavity it is
        aiming at. Rather than probe the entire range more finely, re-sample a
        shrinking window around the grid's winner - each round halves it, so
        six rounds buy 64x the precision for a fraction of the cost.

        Deliberately a re-sample rather than a bisection: it assumes nothing
        about the rule function being monotonic inside the window.
        """
        lo, hi = self.model["Inputs"][col]["range"]
        step = (hi - lo) / (self.PROBE - 1)

        for _ in range(rounds):
            window = [max(lo, best - step), min(hi, best + step)]
            probed = [(engine(**{**row, col: v}), v)
                      for v in (window[0] + i * (window[1] - window[0]) / 8
                                for i in range(9))]
            reached, best = min(probed, key=lambda p: abs(p[0] - target))
            step /= 2

        return reached, best

    def _quoins(self, engine, tiers, count, declared, combo):
        """
        Pass 1. Place `count` landmarks at equidistant points across the range
        the model DECLARED, and solve each one through the full cascade.

        Anchoring to the declared range is what keeps coverage flat as density
        changes: `count` sets the interval between landmarks, never the span
        they cover. Returns the rows and the gap left between them, which is
        what the next pass has to fill.
        """
        lo, hi = declared
        gap = (hi - lo) / (count - 1)
        targets = [lo + i * gap for i in range(count)]

        return [self._solve(engine, tiers, t, combo) for t in targets], gap

    def _widen(self, engine, rows, col, count, gap, declared):
        """
        Passes 2..n. Spread every established row along the next input so its
        outputs tile the gap the previous pass left open, centred on the row's
        own output. Coverage stays contiguous because each window is exactly
        one gap wide and the windows sit one gap apart.

        Like the quoins, each value sits at the centre of its own sub-window
        rather than on the window edge, so the sub-windows tile the gap exactly
        - no doubled density where two windows meet, none lost at the ends.
        """
        lo, hi = declared
        step = gap / count
        widened = []
        for row in rows:
            start = engine(**row) - gap / 2
            targets = [min(hi, max(lo, start + (j + 0.5) * step))
                       for j in range(count)]
            widened += [{**row, col: v}
                        for v in self._nearest(engine, row, col, targets)]
        return widened

    def _plan(self, min_rows, tiers):
        """
        Split a row budget across the passes.

        Row count is the product of the per-pass counts, not a free number, so
        `min_rows` is a floor rather than a target: the planner grows the counts
        as evenly as it can and returns the smallest product that reaches it.
        More budget means finer subdivision at every level - the same output
        span, sampled denser.

        Every pass needs at least two values, so the smallest dataset a model
        can produce is 2 ** (inputs the primary output depends on).
        """
        if min_rows < 1:
            raise ValueError(
                f"min_rows={min_rows} is too small; need at least 1.")

        counts = [2] * len(tiers)

        def product_with(i):
            trial = counts.copy()
            trial[i] += 1
            return math.prod(trial)

        # Grow evenly while there is room. Keeping the counts balanced is what
        # keeps the mixed-radix tiling even.
        while True:
            best, best_product = None, math.prod(counts)
            for i in range(len(counts)):
                product = product_with(i)
                if best_product < product <= min_rows:
                    best, best_product = i, product
            if best is None:
                break
            counts[best] += 1

        # One last step over the floor, by whichever pass overshoots least.
        if math.prod(counts) < min_rows:
            counts[min(range(len(counts)), key=product_with)] += 1

        return counts

    def _generate(self, min_rows, outputs=None, max_bins=1024):
        """
        Build the dataset, topping the budget up until `min_rows` survives.

        `outputs` selects which output columns to build - a name, a list of
        them, or None for every declared output. Each selected output gets its
        own sampling pass, and only the inputs the selection depends on appear
        as columns.

        Saturated landmarks collapse onto input vectors already present and get
        dropped, so the planned product overstates what actually lands. Ask for
        more until enough distinct rows come back, and give up once extra
        budget stops buying rows - past that the model has no further distinct
        rows to give at the extremes.
        """
        self.outputs = self._selected(outputs)
        self.requested = max_bins
        max_bins = min(max_bins, self.MAX_BINS)

        budget, stalls = min_rows, 0
        df = self._build(min_rows, self.outputs, max_bins)

        # Per-pass counts are integers, so a small budget bump often replans to
        # exactly the same grid. Escalate by at least a quarter each attempt,
        # and only give up after several rounds buy nothing - past that the
        # model has no further distinct rows to give at the extremes.
        while len(df) < min_rows and stalls < 3:
            budget = max(int(budget * min_rows / len(df)) + 1,
                         budget + budget // 4 + 1)
            grown = self._build(budget, self.outputs, max_bins)
            if len(grown) > len(df):
                df, stalls = grown, 0
            else:
                stalls += 1

        return df

    def _columns(self, outputs):
        """Inputs any selected output depends on, in declaration order."""
        used = set()
        for name in outputs:
            used |= set(self.model["Outputs"][name]["weights"])
        return [n for n in self.model["Inputs"] if n in used]

    def _sample(self, min_rows, output, combo):
        """
        One output's own passes inside one categorical combination.

        Landmarks across ITS declared range, widened along ITS own hierarchy,
        with the combination's categories held fixed throughout so the
        enumeration stays intact. Returns complete input dicts.
        """
        engine = self.engines[output]
        tiers = self._tiers([output])
        counts = self._plan(min_rows, tiers)
        declared = self.model["Outputs"][output]["range"]

        _, *rest = tiers
        sampled, gap = self._quoins(engine, tiers, counts[0], declared, combo)
        for col, count in zip(rest, counts[1:]):
            sampled = self._widen(engine, sampled, col, count, gap, declared)
            gap = gap / count

        return sampled

    def _resolution(self, rows, max_bins):
        """
        The finest dyadic level this many rows can actually fill.

        The ladder is nested - a row inside a 1024-bin also sits in the 512-bin
        containing it - so filling every cavity at one level makes every
        coarser level solid too. Filling N bins therefore needs at least N
        rows, and asking for more precision than the scale supports is not
        satisfiable. Scale wins: the request is capped, never the row count.
        """
        affordable = 1 << max(0, rows.bit_length() - 1)
        return max(1, min(max_bins, affordable))

    def _cavities(self, values, lo, hi, bins):
        """Indices of the bins at this resolution that hold no rows."""
        width = (hi - lo) / bins
        filled = set()
        for value in values:
            if lo <= value <= hi:
                filled.add(min(bins - 1, int((value - lo) / width)))
        return [i for i in range(bins) if i not in filled]

    def _mortar(self, rows, outputs, bins):
        """
        The mortar course: targeted filling of the cavities bricks left behind.

        Quoins place landmarks and bricks subdivide blindly - neither looks at
        where the gaps actually are. Mortar does: it bins each continuational
        output at the applicable resolution, finds the empty bins, and solves a
        row into each one specifically.

        Unlike the passes above it may re-choose categories, because some
        cavities sit inside a range no single combination reaches - the top of
        a price range may belong to Villas alone. A cavity whose target is
        physically unreachable is reported rather than forced.
        """
        placed, voids = [], {}

        for name in self._continuational(outputs):
            engine = self.engines[name]
            lo, hi = self.model["Outputs"][name]["range"]
            tiers = self._ranked([name])
            width = (hi - lo) / bins

            seen = [engine(**row) for row in rows + placed]
            missed = set()

            for index in self._cavities(seen, lo, hi, bins):
                target = lo + (index + 0.5) * width
                row = self._solve(engine, tiers, target, tol=width / 4)
                if lo + index * width <= engine(**row) <= lo + (index + 1) * width:
                    placed.append(row)
                else:
                    missed.add(index)

            voids[name] = missed

        return placed, voids

    def _build(self, min_rows, outputs, max_bins):
        """
        Enumerate the categories, sample the continuum inside each, then point
        the mortar.

        Coverage is a union property - rows added to span one output's range
        can never cost another output its span - so every selected output gets
        its own pass and the passes are merged. Uniformity is not a union
        property; that is the trade taken here, coverage first.
        """
        combos = self._combos(outputs)
        continuational = self._continuational(outputs)

        if not continuational:
            raise ValueError(
                "Nothing to sample against: a combinational output has no range "
                "to place landmarks across. Select at least one output declared "
                "with a range.")

        # `min_rows` is the continuous budget for one combination, shared out
        # among the outputs sampled within it. The categorical product then
        # multiplies on top, so the total lands near combinations x min_rows.
        share = max(2, -(-min_rows // len(continuational)))

        sampled = []
        for combo in combos:
            for name in continuational:
                sampled += self._sample(share, name, combo)

        self.asked = max_bins
        self.bins = self._resolution(len(sampled), max_bins)
        mortared, self.voids = self._mortar(sampled, outputs, self.bins)

        cols = self._columns(outputs)
        origin = {}

        # THE COHERENCE INVARIANT. A row is only ever produced by choosing
        # inputs and running the engines. Output values are never written,
        # interpolated, or carried over from the pass that made the inputs -
        # which is what makes merging passes safe.
        records = []
        for row, laid in [(r, "bricks") for r in sampled] + \
                         [(r, "mortar") for r in mortared]:
            record = {col: row[col] for col in cols}
            for name in outputs:
                record[name] = self.engines[name](**row)
            origin[tuple(record[col] for col in cols)] = laid
            records.append(record)

        # Landmarks at the ends of a range have already run their inputs to the
        # limit, so widening them re-lands on the same input vector. Drop those.
        frame = (pd.DataFrame(records)
                   .drop_duplicates(subset=cols)
                   .sort_values(by=continuational, ignore_index=True,
                                kind="stable"))

        # Provenance rides alongside rather than in the frame - it describes
        # how a row was made, not what the model says about it.
        self.origin = [origin[tuple(r)] for r in
                       frame[cols].itertuples(index=False, name=None)]

        return frame

    def _uniformity(self, df, output_name=None, bins=10):
        """
        Row counts across `bins` equal-width windows of the declared range,
        with the max/min spread - 1.0 for a perfectly uniform dataset.
        """
        output_name = output_name or self.outputs[0]
        lo, hi = self.model["Outputs"][output_name]["range"]
        edges = [lo + i * (hi - lo) / bins for i in range(bins + 1)]
        counts = (pd.cut(df[output_name], bins=edges, include_lowest=True)
                    .value_counts().sort_index())
        spread = counts.max() / counts.min() if counts.min() else float("inf")
        return counts, round(spread, 2)

    def _ladder(self, df, output, max_bins=None):
        """
        Row counts per bin at 1, 2, 4, 8 ... bins across the DECLARED range.

        A span metric like covered% only reads the endpoints, so it can report
        100% while the interior is riddled with gaps. Doubling the resolution
        shows the scale at which the dataset actually breaks up, and that is
        where the blind spots are.

        Climbs to the resolution that was ASKED for, not the one scale could
        afford. Mortar only fills up to the affordable rung, so the rungs past
        it stay open - and that boundary, where colour gives way to gaps, is
        precisely where `min_rows` stopped being able to pay for `max_bins`.

        Without a mortar pass to lean on it stops once bins would average fewer
        than MIN_PER_BIN rows, past which empty bins are statistics not gaps.
        """
        lo, hi = self.model["Outputs"][output]["range"]
        ceiling = (max_bins or getattr(self, "asked", 0)
                   or max(1, len(df) // self.MIN_PER_BIN))

        levels, n = [], 1
        while n <= ceiling:
            edges = [lo + i * (hi - lo) / n for i in range(n + 1)]
            counts = (pd.cut(df[output], bins=edges, include_lowest=True)
                        .value_counts().sort_index().tolist())
            levels.append((n, counts))
            n *= 2

        return levels

    def _coherence(self, df, outputs=None):
        """
        Re-derive every output from its own row's inputs and report the worst
        disagreement found.

        Rows are only ever built by choosing inputs and running the engines, so
        this should come back at zero. Checking it is what certifies that rows
        merged from different passes still satisfy the model exactly.
        """
        outputs = self._selected(outputs or self.outputs)
        cols = self._columns(outputs)
        defaults = self._defaults()

        worst = 0.0
        for record in df.to_dict("records"):
            row = {**defaults, **{col: record[col] for col in cols}}
            for name in outputs:
                fresh = self.engines[name](**row)
                if self._combinational(name):
                    # A category either matches or it does not; there is no
                    # distance between "Premium" and "Luxury" to measure.
                    worst = max(worst, 0.0 if fresh == record[name] else 1.0)
                else:
                    worst = max(worst, abs(fresh - record[name]))

        return worst

    def _qualify(self, df, bins=10, outputs=None):
        """
        Acceptance report for the continuational outputs.

        `covered%` is the declared span actually reached. `solid@bins` is the
        finest dyadic resolution at which no bin is empty - the honest
        blind-spot measure, since a span can be fully covered and still be
        full of gaps.
        """
        rows = []
        for name in self._continuational(self._selected(outputs or self.outputs)):
            lo, hi = self.model["Outputs"][name]["range"]
            counts, spread = self._uniformity(df, name, bins)
            low, high = df[name].min(), df[name].max()
            levels = self._ladder(df, name)
            solid = max((n for n, c in levels if 0 not in c), default=0)

            rows.append({
                "output": name,
                "declared": f"({lo}, {hi})",
                "achieved": f"({low:.2f}, {high:.2f})",
                "covered%": round(100 * (high - low) / (hi - lo), 1),
                "solid@bins": solid,
                "thinnest": int(counts.min()),
                "fullest": int(counts.max()),
                "spread": spread,
            })

        return pd.DataFrame(rows)

    def _composition(self, df, name):
        """
        Share of each declared option of a combinational column.

        Options are listed as declared, including any that never appeared -
        a category the model can never produce is the one blind spot a
        combinational column genuinely has, and it is only visible here.
        Per-bin views omit absent options; this one names them.
        """
        counts = df[name].value_counts()
        total = len(df) or 1

        return pd.DataFrame([{
            "option": option,
            "rows": int(counts.get(option, 0)),
            "share%": round(100 * counts.get(option, 0) / total, 1),
        } for option in self._options(name)])

    def _compose(self, df, outputs=None):
        """Coverage report for the combinational outputs."""
        rows = []
        selected = self._selected(outputs or self.outputs)

        for name in [o for o in selected if self._combinational(o)]:
            table = self._composition(df, name)
            present = table[table["rows"] > 0]
            absent = table[table["rows"] == 0]["option"].tolist()

            rows.append({
                "output": name,
                "declared": len(table),
                "present": len(present),
                "absent": ", ".join(absent) or "-",
                "thinnest%": present["share%"].min() if len(present) else 0.0,
                "fullest%": present["share%"].max() if len(present) else 0.0,
            })

        return pd.DataFrame(rows)

    def _provenance(self, df, name, bins):
        """Rows per bin at this resolution, split by which course laid them."""
        lo, hi = self.model["Outputs"][name]["range"]
        width = (hi - lo) / bins
        bricks, mortar = [0] * bins, [0] * bins

        for value, laid in zip(df[name], self.origin):
            if lo <= value <= hi:
                index = min(bins - 1, int((value - lo) / width))
                (mortar if laid == "mortar" else bricks)[index] += 1

        return bricks, mortar

    def _unreachable_at(self, name, bins):
        """
        Bins at this resolution that no input vector can reach.

        Mortar records its failures at the resolution it worked at. A coarser
        bin is beyond reach only when every finer bin inside it was.
        """
        fine = getattr(self, "voids", {}).get(name, set())
        if not fine:
            return set()

        if bins > self.bins:
            # Finer than mortar worked: a bin inherits the verdict of the one
            # it sits inside, since nothing reachable lives in an empty parent.
            span = bins // self.bins
            return {i for i in range(bins) if i // span in fine}

        # Coarser: beyond reach only when every bin inside it was.
        span = self.bins // bins
        return {i for i in range(bins)
                if all(i * span + j in fine for j in range(span))}

    def _slices(self, values, bins):
        """
        Composition of a prepared column across equal row-count slices.

        A category column has no numeric axis to cut, so the ladder cuts the
        row count instead. Every slice therefore holds the same number of rows
        and the bar height carries nothing - the whole signal is the mix.
        """
        size = len(values) / bins
        out = []

        for i in range(bins):
            chunk = values[round(i * size):round((i + 1) * size)]
            counts = {}
            for value in chunk:
                counts[value] = counts.get(value, 0) + 1
            out.append(counts)

        return out

    @staticmethod
    def _tick(value, span):
        """Format a value with precision suited to how wide its range is."""
        places = 0 if span >= 1000 else (1 if span >= 10 else 2)
        return f"{value:,.{places}f}"

    def _palette(self, name):
        """Option -> colour, stable for the life of the column."""
        opts = self._options(name)
        return {o: self.CATEGORY_COLOURS[i % len(self.CATEGORY_COLOURS)]
                for i, o in enumerate(opts)}

    # ------------------------------------------------------------------
    # Ladder rungs
    # ------------------------------------------------------------------

    def _rung_range(self, name, bins, lo, hi, bricks, mortar,
                    height=30):
        """
        One rung of a continuational ladder.

        Bar height is the row count. Colour is provenance: laid by the bricks,
        filled afterwards by mortar, or never filled at all - and of those,
        which were physically out of reach rather than merely missed.
        """
        beyond = self._unreachable_at(name, bins)

        width, span = 1000.0, 1000.0 / bins
        edge = (hi - lo) / bins
        peak = max((b + m for b, m in zip(bricks, mortar)), default=1) or 1

        parts = []
        for i, (b, m) in enumerate(zip(bricks, mortar)):
            total = b + m
            low = self._tick(lo + i * edge, hi - lo)
            high = self._tick(lo + (i + 1) * edge, hi - lo)
            head = f"bin {i + 1}/{bins}  |  {low} to {high}  |  "

            if total:
                laid = ("mortar - filled cavity" if not b else
                        f"{total:,} row{'' if total == 1 else 's'}"
                        + (f" ({m:,} by mortar)" if m else ""))
                klass = "mortar" if not b else "bar"
                bar = max(1.0, height * total / peak)
                y, h = height - bar, bar
            elif i in beyond:
                laid, klass, y, h = "beyond reach of the model", "void", 0, height
            elif bins > self.bins:
                laid = "unfilled - finer than this row count supports"
                klass, y, h = "gap", 0, height
            else:
                laid, klass, y, h = "gap - nothing landed here", "gap", 0, height

            tip = f"<title>{html.escape(head + laid)}</title>"
            parts.append(
                f'<rect class="{klass}" x="{i * span:.3f}" y="{y:.3f}" '
                f'width="{max(span - 0.2, 0.35) if total else max(span, 1.2):.3f}" '
                f'height="{h:.3f}">{tip}</rect>')

        return (f'<svg class="strip" viewBox="0 0 {width:.0f} {height}" '
                f'preserveAspectRatio="none">{"".join(parts)}</svg>')

    def _rung_bands(self, name, values, bins, colours, height=30,
                    cls="strip"):
        """
        One rung of a combinational ladder.

        Slices hold equal row counts, so height says nothing and the bar runs
        full depth. The signal is the mix: each band is stacked in proportion
        and coloured by option, the same colours as the composition bar above.
        """
        span = 1000.0 / bins
        parts = []

        for i, counts in enumerate(self._slices(values, bins)):
            total = sum(counts.values()) or 1
            lines = [f"slice {i + 1}/{bins}  |  {total:,} rows"]
            y = 0.0

            for option in self._options(name):
                seen = counts.get(option)
                if not seen:
                    continue
                share = seen / total
                lines.append(f"{option}: {seen:,}  ({100 * share:.0f}%)")
                depth = height * share
                parts.append(
                    f'<rect x="{i * span:.3f}" y="{y:.3f}" '
                    f'width="{max(span, 1.2):.3f}" height="{depth:.3f}" '
                    f'fill="{colours[option]}">'
                    f'<title>{html.escape(chr(10).join(lines))}</title></rect>')
                y += depth

        if cls == "context":
            # Dims what the ladder is not showing; the ladder's own axis is row
            # position, which the composition bars above cannot carry.
            parts.append('<rect class="glass glass-l" x="0" y="0" width="0" '
                         f'height="{height}"/><rect class="glass glass-r" '
                         f'x="1000" y="0" width="0" height="{height}"/>')

        return (f'<svg class="{cls}" viewBox="0 0 1000 {height}" '
                f'preserveAspectRatio="none">{"".join(parts)}</svg>')

    # ------------------------------------------------------------------
    # Overall panels, shown above the ladder
    # ------------------------------------------------------------------

    def _panel_range(self, name):
        """
        Shape and position of a continuational column.

        A density silhouette with the five-number summary marked on it. The
        shape is the model's own, not a fitted curve - these distributions are
        rarely symmetric, and the skew is the thing worth seeing.
        """
        series = self.frame[name]
        lo, hi = self.model["Outputs"][name]["range"] if name in \
            self.model["Outputs"] else self.model["Inputs"][name]["range"]
        span = hi - lo

        shape = 64
        edge = span / shape
        counts = [0] * shape
        for value in series:
            if lo <= value <= hi:
                counts[min(shape - 1, int((value - lo) / edge))] += 1
        peak = max(counts) or 1

        points = " ".join(
            f"{i * 1000 / (shape - 1):.1f},{48 - 46 * c / peak:.1f}"
            for i, c in enumerate(counts))

        marks = [("min", series.min()), ("P25", series.quantile(.25)),
                 ("P50", series.median()), ("P75", series.quantile(.75)),
                 ("max", series.max())]
        rules = "".join(
            f'<line x1="{1000 * (v - lo) / span:.1f}" y1="0" '
            f'x2="{1000 * (v - lo) / span:.1f}" y2="48"/>'
            for _, v in marks[1:4])

        legend = "".join(
            f'<div><span>{k}</span><b class="mono">'
            f'{self._tick(v, span)}</b></div>' for k, v in marks)

        # The two panes dim whatever the ladder is not showing, so this panel
        # doubles as the context view: drag on it to pick a window.
        glass = ('<rect class="glass glass-l" x="0" y="0" width="0" '
                 'height="50"/><rect class="glass glass-r" x="1000" y="0" '
                 'width="0" height="50"/>')

        return (
            '<div class="panel"><p class="panel-h">distribution '
            '<span class="muted">- drag to zoom the ladder</span></p>'
            f'<svg class="dens" viewBox="0 0 1000 50" preserveAspectRatio="none">'
            f'<path d="M0,48 L{points} L1000,48 Z"/>'
            f'<polyline points="{points}"/>{rules}{glass}</svg>'
            f'<div class="quant">{legend}</div></div>')

    def _panel_options(self, name, colours):
        """
        Share of each declared option, one bar per line.

        Declared options that never appeared are listed too and flagged - a
        category the model cannot produce is the one blind spot a combinational
        column genuinely has, and this is the only place it shows.
        """
        table = self._composition(self.frame, name)
        rows = ""

        for _, row in table.iterrows():
            option, share = row["option"], row["share%"]
            missing = row["rows"] == 0
            rows += (
                f'<div class="comp-n"><i style="background:{colours[option]}'
                f'{";opacity:.25" if missing else ""}"></i>'
                f'{html.escape(str(option))}</div>'
                f'<div class="comp-t"><span style="width:{share}%;'
                f'background:{colours[option]}"></span></div>'
                f'<div class="comp-v mono{" absent" if missing else ""}">'
                f'{"absent" if missing else f"{share}%"}</div>')

        return ('<div class="panel"><p class="panel-h">composition</p>'
                f'<div class="comp">{rows}</div></div>')

    # ------------------------------------------------------------------
    # Tables
    # ------------------------------------------------------------------

    def _table(self, head, body):
        if not body:
            return ""
        return ("<table class=\"sum\"><thead><tr>"
                + "".join(f"<th>{html.escape(h)}</th>" for h in head)
                + f"</tr></thead><tbody>{body}</tbody></table>")

    def _cell(self, value, klass="mono"):
        return f'<td class="{klass}">{html.escape(str(value))}</td>'

    def _inputs_table(self):
        """Every input the dataset carries, with what it was asked to span."""
        body = ""
        for name in self._columns(self.outputs):
            spec = self.model["Inputs"][name]
            users = [f"{o} {self.model['Outputs'][o]['weights'][name]}"
                     for o in self.outputs
                     if name in self.model["Outputs"][o]["weights"]]

            if self._combinational(name):
                kind, domain = "combinational", " / ".join(self._options(name))
                seen = self.frame[name].nunique()
                realised = f"{seen} of {len(self._options(name))} options"
            else:
                lo, hi = spec["range"]
                kind, domain = "continuational", f"({lo}, {hi})"
                realised = (f"({self._tick(self.frame[name].min(), hi - lo)}, "
                            f"{self._tick(self.frame[name].max(), hi - lo)})")

            body += ("<tr>" + self._cell(name) + self._cell(kind, "")
                     + self._cell(domain) + self._cell(spec["default"])
                     + self._cell(realised) + self._cell(", ".join(users), "")
                     + "</tr>")

        return self._table(("input", "kind", "domain", "default", "realised",
                            "feeds"), body)

    def _outputs_tables(self):
        """Continuational and combinational outputs, reported on their own terms."""
        body = ""
        for _, row in self.report.iterrows():
            covered = row["covered%"]
            klass = "ok" if covered >= 99.5 else ("warn" if covered >= 90 else "bad")
            body += ("<tr>" + self._cell(row["output"])
                     + self._cell(row["declared"]) + self._cell(row["achieved"])
                     + self._cell(covered, f"mono {klass}")
                     + self._cell(row["solid@bins"]) + self._cell(row["thinnest"])
                     + self._cell(row["fullest"]) + self._cell(row["spread"])
                     + "</tr>")

        ranged = self._table(
            ("output", "declared", "achieved", "covered%", "solid@bins",
             "thinnest", "fullest", "spread"), body)

        body = ""
        for _, row in self.mix.iterrows():
            whole = row["present"] == row["declared"]
            body += ("<tr>" + self._cell(row["output"])
                     + self._cell(row["declared"])
                     + self._cell(row["present"],
                                  "mono " + ("ok" if whole else "bad"))
                     + self._cell(row["absent"],
                                  "mono" if whole else "mono bad")
                     + self._cell(f'{row["thinnest%"]}%')
                     + self._cell(f'{row["fullest%"]}%') + "</tr>")

        options = self._table(
            ("output", "options", "present", "absent", "thinnest%",
             "fullest%"), body)

        return ranged, options

    @staticmethod
    def _weight(size):
        """File size in the largest unit that keeps it readable."""
        for unit, step in (("MB", 1 << 20), ("KB", 1 << 10)):
            if size >= step:
                return f"{size / step:,.0f} {unit}"
        return f"{size} B"

    def _downloads(self, path):
        """
        Links to the dataset this sheet describes, for whichever formats are
        actually sitting beside it.

        A plain relative anchor: it needs no script, and resolves wherever the
        pair is served from. Move the HTML away from its dataset and the link
        goes with it - which is the honest failure, since the sheet describes
        a file it can no longer point at.
        """
        arrow = ('<svg viewBox="0 0 16 16" aria-hidden="true">'
                 '<path d="M8 1.5v9M4.5 7L8 10.5 11.5 7M2 14h12"/></svg>')

        links = ""
        for suffix, label in ((".csv", "CSV"), (".xlsx", "Excel")):
            beside = path.with_suffix(suffix)
            if not beside.exists():
                continue
            links += (
                f'<a class="dl" href="{html.escape(beside.name)}" download'
                f' title="{html.escape(beside.name)}">{arrow}Download {label}'
                f'<span class="dl-size">'
                f'{self._weight(beside.stat().st_size)}</span></a>')

        return links

    def _card(self, name):
        """One output as a collapsible card: overall panel, then its ladder."""
        combinational = self._combinational(name)
        rungs, note = "", ""

        if combinational:
            colours = self._palette(name)
            panel = self._panel_options(name, colours)
            ceiling = min(self.MAX_BANDS, 1 << max(0, len(self.frame).bit_length() - 1))
            present = self.frame[name].nunique()
            head = (f'{present} of {len(self._options(name))} options present'
                    f' &middot; slices hold equal row counts')

            values = self.frame[name].tolist()
            level = 1
            while level <= ceiling:
                rungs += (
                    f'<div class="lvl"><div class="lvl-n mono">{level} '
                    f'slice{"s" if level > 1 else ""}</div>'
                    f'{self._rung_bands(name, values, level, colours)}'
                    f'<div class="lvl-note mono">'
                    f'{len(values) // level:,} rows each</div></div>')
                level *= 2

            note = ('<div class="legend"><span>bands are stacked in proportion, '
                    'coloured as above &middot; hover a slice for its counts '
                    '&middot; drag any band to zoom, double-click to reset'
                    '</span></div>')

            band = min(self.MAX_BANDS, max(64, ceiling // 4))
            rungs = ('<p class="ctx-h">whole dataset '
                     '<span class="muted">- drag to zoom the ladder</span></p>'
                     + self._rung_bands(name, values, band, colours, 34,
                                        "context") + rungs)
            axis = f'data-kind="rows" data-rows="{len(values)}"'
        else:
            lo, hi = self.model["Outputs"][name]["range"]
            row = self.report.set_index("output").loc[name]
            panel = self._panel_range(name)
            solid = row["solid@bins"]
            head = (f'declared <b class="mono">{lo} to {hi}</b> &middot; '
                    f'reached <b class="mono">{row["achieved"]}</b> &middot; '
                    f'<b>{row["covered%"]}%</b> covered &middot; '
                    + (f'solid to <b>{solid}</b> bins' if solid
                       else '<span class="bad">gaps at every resolution</span>'))

            level = 1
            while level <= getattr(self, "asked", self.bins):
                # One scan per rung serves both the bars and the tally.
                bricks, mortar = self._provenance(self.frame, name, level)
                counts = [b + m for b, m in zip(bricks, mortar)]
                beyond = self._unreachable_at(name, level)
                empty = [i for i, c in enumerate(counts) if not c]
                blind = [i for i in empty if i not in beyond]
                tally = ('<span class="ok">no gaps</span>' if not empty else
                         (f'<span class="bad">{len(blind)} gap'
                          f'{"" if len(blind) == 1 else "s"}</span>'
                          if blind else "") +
                         (f' <span class="muted">{len(empty) - len(blind)} '
                          f'unreachable</span>' if len(empty) - len(blind) else ""))
                edge = " past reach" if level > self.bins else ""
                rungs += (
                    f'<div class="lvl{" beyond" if edge else ""}">'
                    f'<div class="lvl-n mono">{level} '
                    f'bin{"s" if level > 1 else ""}{edge}</div>'
                    f'{self._rung_range(name, level, lo, hi, bricks, mortar)}'
                    f'<div class="lvl-note mono">{tally}</div></div>')
                level *= 2

            note = (
                '<div class="legend">'
                '<span><i class="key" style="background:var(--bar)"></i>'
                'laid by quoins and bricks</span>'
                '<span><i class="key" style="background:var(--good)"></i>'
                'filled by mortar</span>'
                '<span><i class="key" style="background:var(--gap)"></i>'
                'unfilled - more rows would reach it</span>'
                '<span><i class="key" style="background:var(--line)"></i>'
                'unreachable - no input vector lands here</span>'
                '<span>drag any rung to zoom, double-click to reset</span>'
                '</div>')
            axis = f'data-kind="range" data-lo="{lo}" data-hi="{hi}"'

        kind = "combinational" if combinational else "continuational"
        return (
            f'<details class="card" open {axis}><summary>'
            f'<h2 class="mono">{html.escape(name)}'
            f'<span class="kind">{kind}</span></h2>'
            f'<div class="facts">{head} <span class="zoom"></span></div>'
            f'</summary>{panel}{rungs}{note}</details>')

    def _datasheet(self, df, path, drift, asked):
        """
        Render the dataset's datasheet: what was asked for, what was produced,
        and the ladder that shows at which resolution it breaks up.

        Self-contained HTML - inline CSS, SVG and script, no network requests
        and no external assets - so it opens from a file path on any machine,
        now or in ten years. The script carries drag-to-zoom only, and is
        purely additive: blocked, it costs the zoom and nothing else.
        """
        self.frame = df
        esc = html.escape
        cols = self._columns(self.outputs)
        laid = self.origin.count("mortar")

        meta = [
            ("model", type(self).__name__),
            ("rows", f"{len(df):,}"),
            ("laid by mortar", f"{laid:,}"),
            ("inputs", str(len(cols))),
            ("outputs", str(len(self.outputs))),
            ("resolution", f"{self.bins} of {asked}"),
            ("seed", str(self.seed)),
            ("dataset", path.name),
            ("generated", datetime.now().strftime("%Y-%m-%d %H:%M")),
        ]
        meta_html = "".join(
            f'<div><span>{esc(k)}</span><b class="mono">{esc(v)}</b></div>'
            for k, v in meta) + self._downloads(path)

        ranged, options = self._outputs_tables()
        cards = "".join(self._card(name) for name in self.outputs)

        drift_html = ('<span class="ok">exact</span> - every row re-derives '
                      'from its own inputs' if drift == 0 else
                      f'<span class="bad">{drift:.6g} worst disagreement</span>')

        clamped = ("" if self.requested <= self.MAX_BINS else
                   f" The {self.requested} bins requested were capped at "
                   f"{self.MAX_BINS}, past which the solver cannot place a "
                   f"value inside the bin it aims at and a bar falls under "
                   f"half a pixel.")
        capped = ("" if self.bins >= asked else
                  f" Mortar was pointed at {self.bins} bins, not the {asked} "
                  f"asked for: filling N bins needs at least N rows, so scale "
                  f"bounds precision. The rungs past {self.bins} are shown "
                  f"anyway and left open - that boundary is what this run's "
                  f"row count could not buy.")

        return (
            "<!doctype html><html lang=\"en\"><head>"
            '<meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            "<title>Datasheet - " + esc(path.stem) + "</title>"
            "<style>" + self.SHEET_CSS + "</style></head><body>"
            '<div class="wrap">'
            "<h1>" + esc(type(self).__name__) + "</h1>"
            '<p class="sub">Dataset datasheet &middot; generated by QBMP '
            "(Quoins, Bricks, Mortar &amp; Pointing)</p>"
            '<div class="meta">' + meta_html + "</div>"
            '<p class="panel-h">inputs</p>' + self._inputs_table()
            + ('<p class="panel-h">continuational outputs</p>' + ranged
               if ranged else "")
            + ('<p class="panel-h">combinational outputs</p>' + options
               if options else "")
            + cards +
            "<footer>"
            '<b>Coherence:</b> ' + drift_html + ".<br>"
            "<b>Reading a continuational ladder:</b> each rung splits the "
            "declared range into twice as many bins as the one above. Full "
            "coverage of a span says nothing about gaps inside it - the rung "
            "where colour breaks is the resolution at which the dataset stops "
            "being continuous." + clamped + " Red and grey are different "
            "failures: red is "
            "precision this row count did not buy and more rows would fill, "
            "grey is output the model cannot produce at any scale."
            + capped + "<br>"
            "<b>Reading a combinational ladder:</b> slices hold equal row "
            "counts, so every band is full depth and only the mix varies. A "
            "band that loses an option shows where that category stops being "
            "producible."
            "</footer></div>"
            "<script>" + self.SHEET_JS + "</script>"
            "</body></html>")

    def save(self, min_rows, dataset, format="csv", outputs=None,
             max_bins=1024, bins=10, preview=10, verbose=True, datasheet=True):
        """
        Single entrypoint: generate, qualify, check coherence, and publish.

        Publishes a folder named for the dataset, holding both halves of it:

            <dataset>/
                index.html            the datasheet
                <dataset>.<format>    the data

        Naming the sheet index.html lets a static server resolve `<dataset>/`
        straight to it, and keeping the pair in one directory means the sheet's
        download link always points at its own data - move the folder and both
        go together.

        `min_rows` is a density floor rather than an exact count: the row total
        is a product of per-pass counts, so the sampler lands on the closest
        reachable count at or above what was asked.

        `outputs` picks which output columns to build; each continuational one
        gets its own sampling pass, so every one spans its full declared range.

        `dataset` may carry a path - "out/prices" publishes out/prices/ - and
        the folder is created if it is not already there.

        `verbose` gates the row preview and the two acceptance tables; the
        lines naming what was written are always printed, since they report
        what landed on disk rather than how it scored. `preview` is how many
        rows that preview shows, and `bins` the coarse resolution `_qualify`
        measures spread at - neither touches the dataset itself. `datasheet`
        turns off publishing index.html, and with it `self.frame`; the reports
        on `self.report`, `self.mix` and `self.drift` are left either way.
        """
        started = time.perf_counter()

        suffix = str(format).lower().lstrip(".")
        if suffix not in ("csv", "xlsx"):
            raise ValueError(
                f"Cannot save as {format!r}: expected 'csv' or 'xlsx'.")

        folder = Path(dataset)
        if not folder.name:
            raise ValueError(f"dataset {dataset!r} does not name a folder.")

        df = self._generate(min_rows, outputs, max_bins)
        self.report = self._qualify(df, bins)
        self.mix = self._compose(df)
        self.drift = self._coherence(df)

        if verbose:
            if preview:
                print(df.head(preview).to_string(index=False))
            print(f"\nrows: {len(df)}   "
                  f"mortar: {self.origin.count('mortar')}   "
                  f"bins: {self.bins} of {self.asked} requested"
                  + (f" (capped from {self.requested})"
                     if self.requested > self.asked else "") + "\n")
            if len(self.report):
                print(self.report.to_string(index=False))
            if len(self.mix):
                print()
                print(self.mix.to_string(index=False))
            print()

        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{folder.name}.{suffix}"

        if suffix == "csv":
            df.to_csv(path, index=False)
        else:
            df.to_excel(path, index=False)

        elapsed = time.perf_counter() - started
        print(f"Saved {len(df)} rows to {path} in {elapsed:.2f}s")

        if datasheet:
            sheet = folder / "index.html"
            sheet.write_text(self._datasheet(df, path, self.drift, self.asked),
                             encoding="utf-8")
            status = "coherent" if self.drift == 0 else f"drift {self.drift:.3g}"
            print(f"Datasheet at {sheet} ({status})")

        return df

