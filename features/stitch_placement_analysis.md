# Stitch Placement Analysis and Redesign Specification

This document analyses the current stitch and hole placement behaviour, identifies
specific visual problems, and proposes concrete improvements.  It is intended as
the source of truth for a future implementation pass.

The reference patterns used throughout are three variants of a 100×60 mm rounded
rectangle with `radius 10`, placed at (10, 10), inset 4 mm, `spacing 5`,
`stitch_length 3`, `edges left right bottom`.

The examples use `RoundedRectangle` for concreteness, but the problems and
proposed fixes apply to **all shapes that support edge selection** — see
Section 12 for the full per-shape coverage table.

---

## 1. How the current algorithm works

### 1.1 Two code paths for `RoundedRectangle`

`RoundedRectangle.stitch_segments` checks the selected edges first:

```python
all_rectangle_edges = edges == "all" or sorted(set(edges)) == [0, 1, 2, 3]
if not all_rectangle_edges:
    return super().stitch_segments(...)   # falls back to Rectangle
```

When any subset of edges is selected (e.g. `edges left right bottom`), the
rounded-corner path is **completely ignored**.  The shape is treated as a plain
rectangle from that point on.  This is the root of most visual problems.

### 1.2 Per-edge independent distribution

`Rectangle.stitch_segments` loops over the selected edges one at a time and calls
`positions_on_side_center` independently for each edge:

```python
count = max(1, int(length / spacing))
center = length / 2
first = center - spacing * (count - 1) / 2
positions = [first + i * spacing for i in range(count)]
```

Each edge is treated as if it exists in isolation, with no knowledge of adjacent
edges.

### 1.3 The margin/clearance adjustment

After the initial positions are computed, `adjust_stitch_positions_and_lengths` is
called.  It calculates a `clearance` value:

```python
target_clearance = max(stitch_length * 0.8, spacing * 0.7)
# = max(3 × 0.8, 5 × 0.7) = max(2.4, 3.5) = 3.5 mm
clearance = min(target_clearance, length / 2)
```

For the example rectangle the clearance is **3.5 mm** for all edges.  The positions
are then rescaled so the first stitch is 3.5 mm from the edge start and the last
stitch is 3.5 mm from the edge end.

### 1.4 `fit_evenly` as currently implemented

`fit_evenly` calculates an adjusted spacing per edge:

```python
interval_count = max(1, round(length / target_spacing))
actual_spacing = length / interval_count
```

Stitches are then placed at `actual_spacing, 2 × actual_spacing, ...` (without
endpoints).  This means the first stitch is **one full interval** (`actual_spacing`)
from the edge start, and the last is one full interval from the edge end.

---

## 2. Observed problems with exact measurements

All measurements are taken from the three reference SVG outputs.

### 2.1 Setup

```
Shape:   RoundedRectangle at (10,10), width=100, height=60, radius=10
Inset:   4 mm  →  inner bounds (14,14)–(106,66), inner radius = 6 mm
Edges:   left(3)  right(1)  bottom(2)
Spacing: 5 mm,  stitch_length: 3 mm
```

Edge lengths after inset:
- **Right edge** (x=106): 66−14 = **52 mm**
- **Bottom edge** (y=66): 106−14 = **92 mm**
- **Left edge** (x=14): 66−14 = **52 mm** (traversed bottom→top)

---

### 2.2 Problem A — Double margin at every corner (`fixed_spacing`)

```
rectangle_panel.lcraft  (no distribution, defaults to fixed_spacing)
```

Each 52 mm edge:
```
count = int(52 / 5) = 10
clearance = 3.5 mm
first stitch: 3.5 mm from edge start
last  stitch: 3.5 mm from edge end
```

At the **bottom-right corner** (106, 66), measured along the perimeter:
```
last right stitch → corner:   3.5 mm
corner → first bottom stitch: 3.5 mm
─────────────────────────────────────
Total gap:                     7.0 mm  (target: 5 mm, overshoot: +40 %)
```

At the **bottom-left corner** (14, 66):
```
last bottom stitch → corner:  3.5 mm
corner → first left stitch:   3.5 mm
─────────────────────────────────────
Total gap:                     7.0 mm  (+40 %)
```

Because every edge independently adds a clearance at **both** ends, the gap
measured across any shared corner is always 2 × clearance instead of 1 × spacing.

Visual effect: the stitches visibly pull back from every corner.  The pattern looks
like it was applied with a ruler laid along each edge separately.

```
  ┌──────────────────────────────────────╮
  │              (no stitches here)       │
  │   ┤3.5├──────────────────────┤3.5├   │
  │   │  right edge stitches     │   │   │
  │   │                          │   │   │
  │   ├ 3.5 ┤─────────── bottom ─────┤   │
  ╰──────────────────────────────────────╯
                                   ↑ 7 mm gap at corner
```

---

### 2.3 Problem B — `fit_evenly` makes corners significantly worse

```
rectangle_panel-3.lcraft  (distribution fit_evenly)
```

Each 52 mm edge with `fit_evenly`:
```
interval_count = round(52 / 5) = 10
actual_spacing = 52 / 10 = 5.2 mm
first stitch (no-endpoints): 5.2 mm from edge start
last  stitch:                5.2 mm from edge end
```

At the **bottom-right corner**:
```
last right stitch → corner:   5.2 mm
corner → first bottom stitch: 5.1 mm  (bottom actual_spacing = 92/18 = 5.11 mm)
─────────────────────────────────────
Total gap:                    10.3 mm  (target: 5 mm, overshoot: +106 %)
```

`fit_evenly` as currently implemented places the first stitch one full interval
from the edge start (not half an interval), so the corner gap is approximately
**2 × actual_spacing** — roughly double the target.

The current `fit_evenly` implementation is worse for corners than plain
`fixed_spacing`.

---

### 2.4 Problem C — Rounded corners are ignored for selected edges

When `edges` is anything other than `"all"` (or all four indices), `RoundedRectangle`
silently falls back to `Rectangle`.  The rounded corners are treated as sharp
right-angle corners.

Consequences:
- Stitches stop at the straight bounding box, not at the arc tangent point.
- There is no stitch on the rounded arc between two selected edges.
- The perimeter gap at a corner includes both edge clearances **plus** the arc
  length:

  ```
  arc at r=6 mm: π/2 × 6 = 9.4 mm
  total corner gap = 3.5 + 3.5 + 9.4 = 16.4 mm perimeter  (per-edge clearance only = 7 mm)
  ```

  (The arc length gap depends on whether the stitches are measured relative to
   the straight edge endpoints or the actual arc tangent points.)

---

### 2.5 Problem D — No control over where the stitch row starts and ends

The current algorithm always centers the stitch sequence symmetrically within each
edge.  The user cannot say:
- "I want the first stitch exactly 5 mm from the shape corner."
- "I want the stitch row to start at a fixed distance from a specific corner."
- "I want the same spacing at the top of this seam as at the bottom."

---

### 2.6 Problem E — `edges all` distributes around the full perimeter but ignores edge boundaries

```
rectangle_panel-2.lcraft  (edges all, fixed_spacing)
```

This path uses `RoundedRectangle.stitch_segments` → `stitch_segments_on_closed_polyline`.
Stitches are evenly distributed around the full inner contour.  Corner gaps are
correct (one spacing interval each), but:
- It is impossible to skip one side (e.g. "all except top").
- When `edges all` is requested, the seam starts at an arbitrary point on the
  contour determined by the polyline start point, not by any visible corner.
- The user cannot anchor the stitch row to a specific corner or edge.

---

## 3. Summary of problems

| # | Problem | File | Severity |
|---|---------|------|----------|
| A | Corner gap = 2× clearance (~7 mm vs 5 mm target) | file 1 | High |
| B | `fit_evenly` per-edge produces corner gap ~2× actual_spacing (~10 mm) | file 3 | Critical |
| C | Rounded corners are ignored when edges ≠ all | files 1, 3 | High |
| D | No user control over where stitch row starts / ends | all | Medium |
| E | `edges all` ignores edge boundaries; seam start unanchored | file 2 | Low |

---

## 4. Proposed solutions

The proposals below are independent and can be implemented separately or
combined.  They are ordered from highest impact to most optional.

---

### 4.1 Proposal S1 — Continuous-path distribution

**Core idea**: treat all *selected* edges as a single connected polyline, compute
one distribution over the total length, then map stitch positions back to individual
edges.

This eliminates the double-clearance problem at interior corners.

**Example** (same rectangle, `edges left right bottom`):

```
Total path length:  52 + 92 + 52 = 196 mm
fit_evenly:         interval_count = round(196 / 5) = 39
                    actual_spacing = 196 / 39 ≈ 5.026 mm
```

With a half-offset start (see S3):
```
first stitch: 2.513 mm from path start (top of right edge)
gap at right→bottom corner: 5.026 mm  ✓
gap at bottom→left corner:  5.026 mm  ✓
last stitch:  2.513 mm from path end (top of left edge)
```

The corner gap is now **one spacing interval**, not two.

**DSL spelling (proposed)**:

```text
stitches
  source panel
  edges left right bottom
  path_mode continuous
  distribution fit_evenly
  ...
end
```

**Default for `path_mode`**: keep `per_edge` as the default so existing files
are not affected.  Future default could be changed to `continuous`.

**Implementation note**: the edge order must follow the shape's canonical winding
order so adjacent edges actually connect.  A validation error should be raised
if the selected edges do not form a connected sub-path.

---

### 4.2 Proposal S2 — Rounded corner following for selected edges

**Core idea**: when `path_mode continuous` (or a new mode `continuous_rounded`)
is used, replace the sharp corner at each interior corner with the actual arc
arc of the rounded shape.

This requires:
1. Detecting that the shape has a radius at the corner between two adjacent
   selected edges.
2. Generating arc points for that corner at the inset radius.
3. Including those arc points in the continuous path.

**Example** (right+bottom+left, inner radius 6 mm, two corners):

```
Arc per corner: π/2 × 6 = 9.42 mm
Total path with arcs: 196 + 2 × 9.42 = 214.85 mm
fit_evenly: interval_count = round(214.85 / 5) = 43
            actual_spacing = 214.85 / 43 ≈ 4.996 mm  (very close to 5 mm)
```

With half-offset:
```
Stitches on the arc at bottom-right corner: approximately 2 stitches
Stitches on the arc at bottom-left corner: approximately 2 stitches
Gap transitions smoothly across corners  ✓
```

**DSL spelling (proposed)**:

```text
stitches
  source panel
  edges left right bottom
  path_mode continuous_rounded
  distribution fit_evenly
  ...
end
```

**Notes**:
- `continuous_rounded` implies `continuous`.
- Only meaningful for shapes that have rounded corners (RoundedRectangle,
  RoundedTriangle, RoundedRegularPolygon, Stadium).  For plain Rectangle it
  is identical to `continuous`.
- For `edges all`, this is already the current behaviour via the closed contour
  path.  `continuous_rounded` on `edges all` would be a no-op.

---

### 4.3 Proposal S3 — First stitch alignment / half-offset for `fit_evenly`

The current `fit_evenly` places the first stitch one full interval from the start:

```
positions: actual_spacing, 2×actual_spacing, ..., (n-1)×actual_spacing
gap at start: actual_spacing  (≈ 5.2 mm for a 52 mm edge with target 5 mm)
```

A half-offset approach places the first stitch at half an interval:

```
positions: actual_spacing/2, 3×actual_spacing/2, ..., (2n-1)×actual_spacing/2
gap at start: actual_spacing/2  (≈ 2.6 mm)
```

This is the standard approach used by sewing machines and is more visually
balanced.  It also preserves stitch count (same number of stitches) while
reducing both the end gaps and the corner gaps when used with per-edge mode.

**Comparison for a 52 mm edge, spacing = 5 mm**:

| Mode | Count | End gap | Corner gap (per-edge) |
|---|---|---|---|
| `fixed_spacing` (current) | 10 | 3.5 mm | 7.0 mm |
| `fit_evenly` no-endpoints (current) | 9 | 5.2 mm | 10.4 mm |
| `fit_evenly` half-offset (proposed) | 10 | 2.6 mm | 5.2 mm |
| `fit_evenly` continuous (proposed) | — | 2.5 mm | 5.0 mm |

The half-offset `fit_evenly` combined with `path_mode continuous` gives essentially
perfect corner spacing.

**Breaking change**: changing `fit_evenly` from no-endpoints to half-offset
changes the stitch positions and count.  This is a breaking change.  Existing
files that use `distribution fit_evenly` will render differently.

**Recommendation**: adopt half-offset as the new behaviour for `fit_evenly`.

---

### 4.4 Proposal S4 — Explicit start and end margin control

Add `first_margin` and `last_margin` (or a single `seam_margin`) to allow the
user to explicitly set where the stitch row starts and ends on the selected path.

```text
stitches
  source panel
  edges left right bottom
  path_mode continuous
  distribution fit_evenly
  first_margin 5        # first stitch exactly 5 mm from path start
  last_margin  5        # last  stitch exactly 5 mm from path end
  spacing 5
  length 3
end
```

When `first_margin` and `last_margin` are given, the available length for
distribution becomes `total_length - first_margin - last_margin`.

This gives full deterministic control over where stitches begin and end,
independent of the distribution algorithm.

**Interaction with `fit_evenly`**:

```
usable_length = total_length - first_margin - last_margin
interval_count = max(1, round(usable_length / spacing))
actual_spacing = usable_length / interval_count
positions: first_margin + actual_spacing/2, ..., last_margin - actual_spacing/2
```

Or with explicit endpoint placement:

```text
  first_margin 5
  last_margin  5
  include_first_margin_stitch yes   # place stitch at exactly first_margin
```

**Default**: `first_margin` and `last_margin` default to `None`, which means
the algorithm chooses the gap (half-interval for `fit_evenly`).

---

### 4.5 Proposal S5 — `alignment` parameter for per-edge mode

For users who need per-edge distribution but want more control over where stitches
land, a new `alignment` parameter controls the starting reference:

| Value | Behaviour | End gap |
|---|---|---|
| `center` | Current behaviour — center the row on the edge | asymmetric from path ends |
| `start` | First stitch at `spacing/2` from edge start, rest at `spacing` intervals | varies |
| `fit` | Half-offset `fit_evenly` (see S3) | `actual_spacing/2` at both ends |

```text
stitches
  source panel
  edges left right bottom
  distribution fit_evenly
  alignment fit            # half-offset
  spacing 5
end
```

**Default**: `alignment center` (current behaviour).

---

### 4.6 Proposal S6 — `edges all` with a specified start corner

For the `edges all` / full-contour case, let the user anchor the stitch start
to a specific corner:

```text
stitches
  source panel
  edges all
  distribution fit_evenly
  start_at top_left        # anchor start to the top-left corner
  spacing 5
end
```

Supported values: `top_left`, `top_right`, `bottom_right`, `bottom_left`,
or a numeric index (for polygons).

This ensures the pattern is positioned relative to a visible feature of the shape,
not at an arbitrary seam point.

**Default**: current behaviour (start at the polyline's first point, which is
typically the top-left corner of the inner contour for rectangles).

---

## 5. Proposed DSL changes

### 5.1 New keys in `stitches` and `holes` blocks

| Key | Type | Default | Notes |
|---|---|---|---|
| `path_mode` | `per_edge` \| `continuous` \| `continuous_rounded` | `per_edge` | Controls whether edges are distributed independently or as a chain |
| `alignment` | `center` \| `start` \| `fit` | `center` | Per-edge placement anchor (only when `path_mode per_edge`) |
| `first_margin` | float | computed | Explicit distance from path start to first stitch |
| `last_margin` | float | computed | Explicit distance from path end to last stitch |
| `start_at` | corner name \| index | `default` | Anchor for full-contour (`edges all`) start point |

The existing `distribution` key continues to work:

| `distribution` value | Meaning |
|---|---|
| `fixed_spacing` | Place every N mm.  No adjustment. |
| `fit_evenly` | Adjust spacing to fit evenly (half-offset, new behaviour) |
| `fixed_count` | Explicit count (future) |

### 5.2 Updated `stitches` block example

```text
stitches
  source panel
  edges left right bottom
  path_mode  continuous_rounded
  distribution  fit_evenly
  margin  4
  spacing  5
  length  3
  angle   45
end
```

### 5.3 Updated `holes` block example

```text
holes
  source panel
  edges left right bottom
  path_mode  continuous_rounded
  distribution  fit_evenly
  margin  4
  spacing  6
  radius  1.2
end
```

---

## 6. Proposed Python API changes

### 6.1 `Shape.hole_points` and `Shape.stitch_segments`

New optional parameters on all shape methods:

```python
def hole_points(
    self,
    edges="all",
    spacing=5.0,
    inset=4.0,
    include_corners=False,
    rounded_path=False,
    distribution="fixed_spacing",    # NEW
    path_mode="per_edge",            # NEW
    alignment="center",              # NEW
    first_margin=None,               # NEW
    last_margin=None,                # NEW
) -> list[Point]: ...

def stitch_segments(
    self,
    edges="all",
    spacing=5.0,
    inset=4.0,
    include_corners=False,
    stitch_length=2.0,
    stitch_angle_deg=0.0,
    rounded_path=False,
    distribution="fixed_spacing",    # NEW
    path_mode="per_edge",            # NEW
    alignment="center",              # NEW
    first_margin=None,               # NEW
    last_margin=None,                # NEW
) -> list[tuple[Point, Point]]: ...
```

### 6.2 `SvgDocument` methods

Same new parameters passed through:

```python
def add_holes(
    self,
    shape,
    edges="all",
    spacing=5.0,
    hole_radius=1.2,
    inset=4.0,
    layer="cut",
    include_corners=False,
    rounded_path=False,
    distribution="fixed_spacing",
    path_mode="per_edge",
    alignment="center",
    first_margin=None,
    last_margin=None,
) -> None: ...

def add_stitch_pattern(
    self,
    shape,
    edges="all",
    spacing=5.0,
    stitch_length=2.0,
    inset=4.0,
    layer="stitch",
    include_corners=False,
    stitch_thickness=None,
    stitch_angle_deg=0.0,
    rounded_path=False,
    distribution="fixed_spacing",
    path_mode="per_edge",
    alignment="center",
    first_margin=None,
    last_margin=None,
) -> None: ...
```

### 6.3 Internal helper `distribute_distances`

A shared internal helper should centralise all placement logic.  The existing
`leathercraft_stitch_distribution_modes.md` already specifies this helper; the
proposed extension:

```python
def distribute_distances(
    length: float,
    spacing: float,
    *,
    distribution: str = "fixed_spacing",
    alignment: str = "center",        # NEW: "center" | "start" | "fit"
    count: int | None = None,
    include_start: bool = False,
    include_end: bool = False,
    min_count: int = 1,
) -> list[float]:
    """
    Return arc-lengths from 0 at which to place stitches or holes.

    distribution="fixed_spacing", alignment="center":
        Current behaviour.  Center the row, no spacing adjustment.

    distribution="fit_evenly", alignment="fit" (recommended new default):
        interval_count = max(1, round(length / spacing))
        actual = length / interval_count
        first = actual / 2        <- half-offset
        positions = first, first+actual, ..., last

    distribution="fit_evenly", alignment="center":
        Same interval_count / actual_spacing but center-balanced.
    """
```

---

## 7. Breaking changes

The following changes would affect existing `.lcraft` files or Python code.  Each
is listed with a migration path.

### BC-1  `fit_evenly` stitch count and positions change

**Current**: first stitch at `actual_spacing` from edge start (no-endpoints mode).
**Proposed**: first stitch at `actual_spacing / 2` from edge start (half-offset).

Effect: existing files using `distribution fit_evenly` will render with a
different stitch count and different first/last positions.

Migration: none needed unless exact stitch positions are required.  The visual
result will be more balanced.

**Severity**: Medium.  Only affects files that explicitly use `distribution fit_evenly`.

---

### BC-2  `path_mode continuous` changes gap behaviour at corners

**Current**: per-edge mode is the only mode.  Corner gaps are 2× clearance.
**Proposed**: if `path_mode continuous` becomes the new default in a future release,
all files with multiple selected edges will render differently.

For the first implementation, keep `path_mode per_edge` as the default.  Users
opt in to the new behaviour explicitly.

**Severity**: None in the first release (opt-in only).

---

### BC-3  `continuous_rounded` changes `RoundedRectangle` subset-edge behaviour

**Current**: subset-edge selection falls back to `Rectangle` (sharp corners).
**Proposed**: `path_mode continuous_rounded` follows the rounded arc.

This means more stitches will appear (those on the arc), and existing stitch
counts will change.

Migration: explicit `path_mode per_edge` restores current behaviour.

**Severity**: Medium (opt-in only in first release).

---

### BC-4  `adjustment_stitch_positions_and_lengths` semantics change

If S3 is adopted (half-offset for `fit_evenly`), the existing
`positions_on_side_center` / `adjust_stitch_positions_and_lengths` functions
should not be changed directly.  Instead, `distribute_distances` replaces them
as the single source of truth, and the old functions delegate to it.

Callers that directly import `positions_on_side_center` from `leathercraft_svg`
will not be broken, but the meaning of `fit_evenly` will change.

**Severity**: Low.  Internal functions; only affects direct importers.

---

## 8. Interaction matrix

| `path_mode` | `distribution` | `alignment` | Behaviour |
|---|---|---|---|
| `per_edge` | `fixed_spacing` | `center` | Current default.  Each edge independently, center-balanced, fixed 3.5 mm clearance. |
| `per_edge` | `fit_evenly` | `center` | Per-edge, center-balanced, adjusted spacing. Corner gap = 2× end-gap. |
| `per_edge` | `fit_evenly` | `fit` | Per-edge, half-offset.  Corner gap ≈ actual_spacing (not doubled). |
| `continuous` | `fixed_spacing` | `center` | Chain of edges, fixed spacing, center-balanced over full path. |
| `continuous` | `fit_evenly` | `fit` | **Recommended new approach.**  Chain, half-offset.  Corner gap = one spacing interval. |
| `continuous_rounded` | `fit_evenly` | `fit` | **Best quality.**  Chain follows arcs.  Stitches distribute across corners smoothly. |

---

## 9. Worked example: desired result

**Pattern**: rounded_rectangle 100×60, radius 10, inset 4, `edges left right bottom`,
`spacing 5`, target `fit_evenly`, `path_mode continuous_rounded`.

```
Inner straight lengths:
  right:  52 mm
  bottom: 92 mm
  left:   52 mm
  sub-total: 196 mm

Inner arc at r=6, at each of 2 corners:
  arc = π/2 × 6 ≈ 9.42 mm
  2 arcs = 18.85 mm

Total path: 214.85 mm

fit_evenly half-offset:
  interval_count = round(214.85 / 5) = 43
  actual_spacing = 214.85 / 43 ≈ 4.996 mm  ≈ 5 mm
  first stitch: 4.996/2 ≈ 2.498 mm from path start (top of right edge)
  count: 43 stitches

Corner transitions:
  Each corner arc ≈ 9.42 mm = ~1.9 spacing intervals → ~2 stitches on arc
  No gap artifact at corners  ✓

Top corners (unselected top edge):
  Right edge starts at 2.5 mm from top-right corner  ✓ clean end
  Left  edge ends   at 2.5 mm from top-left corner   ✓ clean end
```

Compared to current `fit_evenly`:
```
Current:   10.3 mm gap at each corner  (106 % over-target)
Proposed:   4.996 mm at each corner    (0.1 % from target)
```

---

## 10. Implementation order recommendation

1. Add `distribute_distances` helper with `fixed_spacing`, `fit_evenly`
   (half-offset), and `alignment` parameter.
2. Fix `fit_evenly` to use half-offset (BC-1).
3. Add `path_mode continuous` to `Rectangle`-family shapes.
4. Add `path_mode continuous_rounded` to `RoundedRectangle`
   (extends the rounded-contour path to respect edge selection).
5. Add `first_margin` / `last_margin` support inside `distribute_distances`.
6. Add all new parameters to the DSL parser.
7. Update `AGENT.md` and `README.md`.
8. Add unit tests for each mode combination.
9. Add visual regression tests.
10. Update `leathercraft_stitch_distribution_modes.md` to reflect the settled
    design (that document describes an earlier, incomplete picture of the problem).

---

## 11. Open questions

### Q1  Should `path_mode continuous` become the new default?

Continuous distribution is almost always the right choice for professional
leathercraft.  Making it the default would be a breaking change (BC-2).

**Recommendation**: make it the default in the next major version.  Provide a
deprecation warning for one release if backward compatibility matters.

### Q2  Should `alignment fit` become the default for `fit_evenly`?

Yes.  The current no-endpoints behaviour is objectively worse for corner spacing
and has no advantage over half-offset.

**Recommendation**: adopt immediately as part of BC-1.

### Q3  How should `start_at` (S6) interact with `path_mode continuous`?

When both are set, `start_at` specifies the corner where the continuous chain
begins.  The chain should then traverse the selected edges in winding order from
that corner.

### Q4  What happens when selected edges are not adjacent?

For example `edges top bottom` on a rectangle — these are not connected.

**Recommendation**: treat each connected component independently (two separate
chains, each distributed separately).  Document this clearly.

### Q5  Should `include_corners` be deprecated?

`include_corners` was designed to decide whether the very start/end of an edge
gets a stitch.  With the new `first_margin` / `last_margin` model, it is
redundant and potentially confusing.

**Recommendation**: keep `include_corners` for backward compatibility but document
that `first_margin 0` + `last_margin 0` is the preferred replacement.

---

## 12. Per-shape coverage

This table covers every shape in the library and shows which problems affect it
and which proposed fixes apply.

The two code paths that cause problems are:
- **per-edge**: calls `positions_on_side_center` independently for each selected
  edge.  Every shape that falls into this path has problems A and B.
- **closed contour**: distributes along the full perimeter as a single polyline.
  These shapes have no per-edge corner issues.

| Shape | `edges all` path | Partial-edge path | Problem A/B | Problem C | Fix S1/S2 needed |
|---|---|---|---|---|---|
| `Rectangle` | per-edge | per-edge | **Yes** | No (no rounding) | S1 |
| `RoundedRectangle` | closed contour | falls back to `Rectangle` | **Yes** | **Yes** | S1 + S2 |
| `Stadium` | closed contour | falls back to `Rectangle` | **Yes** | **Yes** | S1 + S2 |
| `Triangle` | `closed_edges` | `selected_edges` | **Yes** | No (sharp corners) | S1 |
| `RoundedTriangle` | closed contour (if `rounded_path`) | falls back to `Triangle` | **Yes** | **Yes** | S1 + S2 |
| `RegularPolygon` | `closed_edges` | `selected_edges` | **Yes** | No (sharp corners) | S1 |
| `RoundedRegularPolygon` | closed contour (if rounded) | falls back to `RegularPolygon` | **Yes** | **Yes** | S1 + S2 |
| `Circle` | circumference count | no edge selection | No | No | — |
| `Ellipse` | closed contour | no edge selection | No | No | — |
| `Arc` | closed contour | no edge selection | No | No | — |
| `Polygon` | closed contour | no edge selection | No | No | — |

**Summary**:
- `Circle`, `Ellipse`, `Arc`, and `Polygon` are **not affected** by any of the
  corner-gap problems.  They always distribute along a single continuous path.
- All other shapes (`Rectangle`, `RoundedRectangle`, `Stadium`, `Triangle`,
  `RoundedTriangle`, `RegularPolygon`, `RoundedRegularPolygon`) are affected
  whenever partial edges are selected.
- The proposed fixes operate on the shared helper functions
  (`positions_on_side_center`, `distribute_distances`, `points_on_selected_edges`,
  `segments_on_selected_edges`), so implementing S1 and S3 once fixes all seven
  affected shapes simultaneously.
- S2 (rounded corner following) additionally requires per-shape logic to generate
  the corner arc points; it applies only to the four shapes that have actual
  rounded corners: `RoundedRectangle`, `Stadium`, `RoundedTriangle`,
  `RoundedRegularPolygon`.
