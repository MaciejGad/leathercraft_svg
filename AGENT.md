# leathercraft_svg — AI Agent Reference

This file is intended for AI agents generating code with the `leathercraft_svg` library. It covers every public class and method, default values, edge indices, key constraints, and annotated examples. Read this before writing any code.

---

## Setup

```python
# Standard import pattern — all public names live in leathercraft_svg
from leathercraft_svg import (
    SvgDocument, StrokeStyle,
    Point,
    Rectangle, RoundedRectangle, Stadium,
    Circle, Ellipse, Arc,
    Triangle, RoundedTriangle,
)
```

Requires Python 3.13+. `save_png` requires `cairosvg`; `save_dxf` requires the
optional `ezdxf` package; `save` (SVG only) has no dependencies.

---

## Core workflow

Every script follows this pattern:

```python
doc = SvgDocument(width_mm=..., height_mm=...)
shape = SomeShape(...)          # define geometry
doc.add_shape(shape, layer="cut")   # draw the outline
doc.add_holes(shape, ...)           # OR
doc.add_stitch_pattern(shape, ...)  # add stitching
doc.save("output.svg")
doc.save_png("output.png", background_color="white")  # optional
doc.save_dxf("output.dxf")  # optional
```

---

## SvgDocument

```python
SvgDocument(width_mm: float, height_mm: float, styles: dict[str, StrokeStyle] | None = None)
```

`styles` is optional. When omitted, default layer styles are used (see Layers below).

### Methods

| Method | Description |
|--------|-------------|
| `add_shape(shape, layer="cut")` | Add a shape outline as an SVG path |
| `add_path(d, layer="cut")` | Add a raw SVG `d` string |
| `add_line(x1, y1, x2, y2, layer="cut")` | Add a line segment |
| `add_circle(x, y, radius, layer="cut")` | Add a circle |
| `add_holes(shape, ...)` | Add stitch holes (circles) along shape edges |
| `add_stitch_holes(shape, ...)` | Alias for `add_holes` |
| `add_stitch_pattern(shape, ...)` | Add laser stitch lines along shape edges |
| `save(path)` | Write SVG file |
| `save_png(path, background_color="white")` | Write PNG via CairoSVG |
| `save_dxf(path, ...)` | Write DXF via ezdxf |
| `to_svg()` | Return SVG as a string |
| `add_stitch_on_polyline(points, ...)` | Add stitch marks along an open `(x,y)` polyline |

### `add_holes` signature

```python
doc.add_holes(
    shape,
    edges="all",              # "all" or list of int edge indices
    spacing=5.0,              # mm between hole centers
    hole_radius=1.2,          # mm hole radius
    inset=4.0,                # mm offset inward from edge
    layer="cut",
    rounded_path=False,       # follow rounded contour (RoundedTriangle only)
    distribution="fixed_spacing",  # or "fit_evenly"
    count=None,               # reserved; fixed_count is not supported yet
    path_mode="continuous",   # "continuous" | "per_edge" | "continuous_rounded"
    first_margin=None,        # mm from chain start; None = centered / half-offset
    last_margin=None,         # mm from chain end
)
```

`include_corners` has been **removed**. Use `first_margin=0, last_margin=0` to pin holes at chain endpoints.

### `add_stitch_on_polyline` signature

```python
doc.add_stitch_on_polyline(
    points,                  # list of (x, y) tuples — open polyline
    spacing=5.0,             # mm between stitch centres
    stitch_length=2.0,       # mm length of each stitch
    stitch_angle_deg=0.0,    # 0 = parallel to path, 45 = diagonal
    layer="stitch",
    stitch_thickness=None,   # overrides layer stroke width
    distribution="fixed_spacing",  # or "fit_evenly"
    count=None,
)
```

### `add_stitch_pattern` signature

```python
doc.add_stitch_pattern(
    shape,
    edges="all",
    spacing=5.0,
    stitch_length=2.0,        # mm length of each stitch line
    inset=4.0,
    layer="stitch",
    stitch_thickness=None,    # float or None; overrides layer stroke width
    stitch_angle_deg=0.0,     # 0 = along edge, 90 = perpendicular
    rounded_path=False,
    distribution="fixed_spacing",  # or "fit_evenly"
    count=None,
    path_mode="continuous",   # "continuous" | "per_edge" | "continuous_rounded"
    first_margin=None,        # mm from chain start; None = centered / half-offset
    last_margin=None,         # mm from chain end
)
```

`include_corners` has been **removed**. Use `first_margin=0, last_margin=0` to pin stitches at chain endpoints.

`fit_evenly` uses half-offset distribution: stitches are centred within their intervals (margin ≈ `actual_spacing / 2` at each open chain end). `fixed_spacing` centres the stitch run across the total chain length.

### `save_dxf` signature

```python
doc.save_dxf(
    "pattern.dxf",
    version="R2010",
    units="mm",
    preserve_curves=True,
    curve_tolerance=0.1,
    flip_y=False,
)
```

DXF export preserves layers and writes simple 2D entities such as `LINE`,
`CIRCLE`, `ARC`, and `LWPOLYLINE`. Raw SVG paths added through `add_path(...)`
raise a clear error during DXF export.

---

## Layers and StrokeStyle

Default layers:

| Layer | Color | Width | Dash |
|-------|-------|-------|------|
| `"cut"` | `#ff0000` (red) | 0.2 | — |
| `"stitch"` | `#0000ff` (blue) | 0.2 | — |
| `"crease"` | `#00aa00` (green) | 0.2 | `"3 2"` |
| `"guide"` | `#777777` (gray) | 0.2 | `"2 2"` |

To use custom styles:

```python
from leathercraft_svg import StrokeStyle, SvgDocument

doc = SvgDocument(100, 60, styles={
    "cut":    StrokeStyle("#ff0000", 0.1),
    "stitch": StrokeStyle("#0000ff", 0.3),
    "crease": StrokeStyle("#00aa00", 0.1, dasharray="3 2"),
    "guide":  StrokeStyle("#777777", 0.1, dasharray="2 2"),
})
```

---

## Shapes

### Point

```python
Point(x: float, y: float)
```

Immutable 2D point. Used as vertices for Triangle and RoundedTriangle.

---

### Rectangle

```python
Rectangle(x, y, width, height)
# x, y = top-left corner
```

**Edge indices:**
- `0` = top
- `1` = right
- `2` = bottom
- `3` = left

```python
shape = Rectangle(10, 10, 80, 40)
doc.add_shape(shape, layer="cut")
doc.add_holes(shape, edges=[0, 2], spacing=8.0, hole_radius=1.2, inset=5.0)
```

---

### RoundedRectangle

```python
RoundedRectangle(x, y, width, height, radius=5.0,
                 radius_tl=None, radius_tr=None, radius_br=None, radius_bl=None)
```

Same edge indices as Rectangle (0=top, 1=right, 2=bottom, 3=left). Corner radius is automatically clamped to `min(radius, width/2, height/2)`.

Each corner can be overridden individually with `radius_tl` / `radius_tr` / `radius_br` / `radius_bl` (top-left, top-right, bottom-right, bottom-left). `None` falls back to the uniform `radius`; `0` gives a sharp corner. If two radii on a shared edge would overlap, all four are scaled down proportionally (`corner_radii()` returns the effective values).

When `edges="all"`, the stitch pattern follows the smooth rounded contour — including asymmetric per-corner contours. For partial edge selections it falls back to straight-edge placement.

```python
# Card holder: rounded top, sharp bottom
shape = RoundedRectangle(10, 10, 100, 75, radius=0, radius_tl=18, radius_tr=18)
```

```python
shape = RoundedRectangle(20, 15, 100, 60, radius=10)
doc.add_shape(shape, layer="cut")
doc.add_stitch_pattern(
    shape,
    edges=[1, 2, 3],       # right, bottom, left — skip top
    spacing=8.0,
    stitch_length=3.5,
    stitch_angle_deg=45.0,
    inset=7.0,
    layer="stitch",
    stitch_thickness=0.8,
)
```

---

### Stadium

```python
Stadium(x, y, width, height)
```

Capsule / oblong: a rectangle whose two short ends are replaced by semicircles. The cap radius is always `min(width, height) / 2` (read-only `radius` property) — a wide box gives left/right caps, a tall box gives top/bottom caps. Same edge indices as Rectangle (0=top, 1=right, 2=bottom, 3=left).

When `edges="all"`, both `hole_points` and `stitch_segments` follow the full capsule contour, including the curved caps. For partial edge selections they fall back to straight-edge placement. If `inset` consumes the whole shape (`width - 2*inset <= 0` or `height - 2*inset <= 0`), an empty list is returned.

```python
shape = Stadium(10, 15, 120, 30)   # key-fob blank, cap radius = 15
doc.add_shape(shape, layer="cut")
doc.add_stitch_pattern(shape, spacing=5.0, stitch_length=3.0, inset=4.0)
```

---

### Circle

```python
Circle(cx, cy, radius)
# cx, cy = center
```

`hole_points` and `stitch_segments` distribute evenly around a ring at radius `radius - inset`. The `edges` parameter is accepted but ignored (circles have no discrete edges).

```python
shape = Circle(70, 45, 30)
doc.add_shape(shape, layer="cut")
doc.add_holes(shape, spacing=8.0, hole_radius=1.5, inset=7.0, layer="stitch")
```

---

### Ellipse

```python
Ellipse(cx, cy, rx, ry)
# cx, cy = center; rx = horizontal radius; ry = vertical radius
```

Oval with two independent radii — identical to `Circle` when `rx == ry`. `hole_points` and `stitch_segments` distribute evenly (by arc length) along the contour of a helper ellipse with radii `rx - inset` and `ry - inset`. The `edges` parameter is accepted but ignored. Returns an empty list when `inset >= rx` or `inset >= ry`.

```python
shape = Ellipse(65, 45, 55, 35)
doc.add_shape(shape, layer="cut")
doc.add_stitch_pattern(shape, spacing=6.0, stitch_length=3.0, inset=5.0)
```

---

### Arc

```python
Arc(cx, cy, radius, start_angle, end_angle, inner_radius=0.0)
# angles in degrees: 0 = right (3 o'clock), increasing clockwise (SVG Y-down)
```

Circular sector (pie wedge) or — with `inner_radius > 0` — a ring segment (annulus slice). If `end_angle <= start_angle`, a full turn is added, so `start=300, end=60` spans 120° across 3 o'clock. `hole_points` and `stitch_segments` follow the full closed contour (outer arc, straight edges, inner arc if present), inset using the same polygon-offset machinery as `Polygon`. The `edges` parameter is accepted but ignored.

```python
shape = Arc(65, 75, 55, start_angle=180, end_angle=360, inner_radius=30)
doc.add_shape(shape, layer="cut")
doc.add_stitch_pattern(shape, spacing=6.0, stitch_length=3.0, inset=5.0)
```

To place holes or stitches only on a portion of a circle (e.g. leaving a gap), compute the points manually and filter by angle:

```python
from math import atan2, degrees

points = shape.hole_points(spacing=8.0, inset=7.0)
for p in points:
    angle = degrees(atan2(p.y - shape.cy, p.x - shape.cx))
    if not (-135 <= angle <= -45):  # skip the gap sector
        doc.add_circle(p.x, p.y, 1.5, layer="stitch")
```

---

### Triangle

```python
Triangle(p1: Point, p2: Point, p3: Point)

# Convenience constructor from a bounding box:
Triangle.from_box(x, y, width, height)
# p1 = top-center, p2 = bottom-right, p3 = bottom-left
```

**Edge indices:**
- `0` = p1 → p2
- `1` = p2 → p3
- `2` = p3 → p1

```python
shape = Triangle(Point(20, 20), Point(100, 70), Point(20, 70))
doc.add_shape(shape, layer="cut")
doc.add_holes(shape, edges=[0, 2], spacing=10.0, hole_radius=1.0, inset=6.0)
```

---

### RoundedTriangle

```python
RoundedTriangle(p1: Point, p2: Point, p3: Point, radius=5.0)
```

Same edge indices as Triangle. Pass `rounded_path=True` to `add_holes` / `add_stitch_pattern` to follow the smooth rounded contour (only effective when `edges="all"`).

```python
shape = RoundedTriangle(
    Point(60, 10), Point(110, 80), Point(10, 80), radius=12
)
doc.add_shape(shape, layer="cut")
doc.add_holes(shape, spacing=8.0, hole_radius=1.5, inset=6.0, rounded_path=True)
```

---

### Polygon

```python
Polygon(points: list[tuple[float, float]], smooth: bool = False)
```

Shape defined by an explicit `(x, y)` list. `smooth=True` draws the outline
with quadratic Bézier curves (each point becomes a control point; midpoints
are the anchor points). `hole_points` and `stitch_segments` offset the
boundary inward by `inset` automatically — no manual offset needed.

**The `edges` parameter is ignored** — Polygon always uses the whole boundary.

```python
from leathercraft_svg import Polygon, SvgDocument

doc = SvgDocument(150, 80)
shape = Polygon(
    points=[(10,5), (75,5), (140,5), (140,75), (75,75), (10,75)],
    smooth=False,
)
doc.add_shape(shape, layer="cut")
doc.add_holes(shape, spacing=8.0, hole_radius=1.2, inset=5.0, layer="stitch")
```

#### `Polygon.from_mirror(half_points, center_x, smooth=False)`

Builds a symmetric shape from one half. `half_points` must start **and** end
on the mirror axis (`x == center_x`). The mirrored right half is appended in
reverse to form one continuous closed loop.

```python
from leathercraft_svg import Polygon, SvgDocument

doc = SvgDocument(150, 80)

left_half = [
    (75, 5),    # top-centre — on the mirror axis
    (40, 5),
    (20, 40),
    (40, 75),
    (75, 75),   # bottom-centre — on the mirror axis
]

shape = Polygon.from_mirror(left_half, center_x=75, smooth=True)
doc.add_shape(shape, layer="cut")
doc.add_holes(shape, spacing=8.0, hole_radius=1.2, inset=5.0, layer="stitch")
doc.save("polygon.svg")
```

---

### Polyline utilities

These functions work with plain `list[tuple[float, float]]` point lists and
are independent of any shape class.

#### `offset_polyline(points, distance, side="right", miter_limit=8.0)`

Offsets an **open** polyline. `side` is the **right-hand or left-hand side relative to
the direction of travel** (not the screen). In SVG (Y grows downward):
- A segment going **right** → `side="right"` offsets **upward** (−Y).
- A segment going **down** → `side="right"` offsets **rightward** (+X).

For a left-edge polyline running top→bottom, `side="right"` offsets inward (toward the centre).

```python
from leathercraft_svg import offset_polyline, mirror_polyline

left_edge = [(30, 10), (20, 50), (30, 90)]
left_seam  = offset_polyline(left_edge, distance=4.0, side="right")
right_seam = mirror_polyline(left_seam, center_x=75)
```

#### `mirror_polyline(points, center_x)`

Mirrors every point horizontally around `center_x`. Returns a new list.

#### `stitch_segments_on_open_polyline(points, spacing, stitch_length, stitch_angle_deg=0.0)`

Returns `list[tuple[Point, Point]]` — stitch segments placed every `spacing`
mm along an open polyline. First stitch at `1×spacing` from the path start.
Use `doc.add_stitch_on_polyline` to render the result directly.

---

## Key parameters — rules of thumb

| Parameter | Typical range | Effect |
|-----------|--------------|--------|
| `spacing` | 5–12 mm | Distance between holes or stitches |
| `hole_radius` | 0.8–1.8 mm | Punch hole size |
| `inset` | 4–8 mm | How far holes/stitches sit from the edge |
| `stitch_length` | 2–5 mm | Line length for laser stitch pattern |
| `stitch_angle_deg` | 0 or 45 | 0 = along edge, 90 = perpendicular, 45 = diagonal |
| `stitch_thickness` | 0.1–1.0 mm | Stroke width for stitch lines (overrides layer) |
| `path_mode` | `"continuous"` | `"continuous"` = distribute along connected chain; `"per_edge"` = each edge independently; `"continuous_rounded"` = follow arc at rounded corners |
| `first_margin` | `None` | mm from chain start to first hole/stitch; `None` = auto-center |
| `last_margin` | `None` | mm from chain end to last hole/stitch; `None` = auto-center |
| `rounded_path` | False (default) | True = follow curved contour (RoundedTriangle) |
| `distribution` | `"fixed_spacing"` | Use `"fit_evenly"` to adjust spacing to the available length (half-offset margins) |

---

## Complete annotated examples

### 1. Rectangle with holes on all edges

```python
from leathercraft_svg import Rectangle, SvgDocument

doc = SvgDocument(100, 60)
shape = Rectangle(10, 10, 80, 40)

doc.add_shape(shape)                          # default layer="cut"
doc.add_holes(shape, spacing=8.0, hole_radius=1.2, inset=5.0)
doc.save("rect_holes.svg")
```

### 2. Rounded rectangle — stitch on 3 sides only

```python
from leathercraft_svg import RoundedRectangle, SvgDocument

doc = SvgDocument(140, 90)
shape = RoundedRectangle(20, 15, 100, 60, radius=10)

doc.add_shape(shape, layer="cut")
doc.add_stitch_pattern(
    shape,
    edges=[1, 2, 3],           # right, bottom, left
    spacing=8.0,
    stitch_length=3.5,
    stitch_angle_deg=45.0,
    inset=7.0,
    layer="stitch",
    stitch_thickness=0.8,
)
doc.save("rounded_rect_stitch.svg")
doc.save_png("rounded_rect_stitch.png")
```

### 3. Circle with holes

```python
from leathercraft_svg import Circle, SvgDocument

doc = SvgDocument(100, 100)
shape = Circle(50, 50, 35)

doc.add_shape(shape, layer="cut")
doc.add_holes(shape, spacing=8.0, hole_radius=1.5, inset=7.0, layer="stitch")
doc.save("circle_holes.svg")
```

### 4. Triangle with partial edge selection

```python
from leathercraft_svg import Point, Triangle, SvgDocument

doc = SvgDocument(120, 90)
shape = Triangle(Point(60, 10), Point(110, 80), Point(10, 80))

doc.add_shape(shape, layer="cut")
doc.add_holes(shape, edges=[0, 2], spacing=10.0, hole_radius=1.0, inset=6.0)
doc.save("triangle.svg")
```

### 5. RoundedTriangle with rounded contour

```python
from leathercraft_svg import Point, RoundedTriangle, SvgDocument

doc = SvgDocument(130, 100)
shape = RoundedTriangle(
    Point(65, 10), Point(120, 90), Point(10, 90), radius=12
)

doc.add_shape(shape, layer="cut")
doc.add_stitch_pattern(
    shape,
    spacing=8.0,
    stitch_length=3.5,
    stitch_angle_deg=0.0,
    inset=6.0,
    layer="stitch",
    stitch_thickness=0.8,
    rounded_path=True,   # follow curved corners
)
doc.save("rounded_triangle.svg")
```

### 6. Custom styles

```python
from leathercraft_svg import Rectangle, StrokeStyle, SvgDocument

doc = SvgDocument(100, 60, styles={
    "cut":    StrokeStyle("#ff0000", 0.1),
    "stitch": StrokeStyle("#0000ff", 0.4),
    "crease": StrokeStyle("#00aa00", 0.1, "3 2"),
    "guide":  StrokeStyle("#777777", 0.1, "2 2"),
})
shape = Rectangle(10, 10, 80, 40)
doc.add_shape(shape, layer="cut")
doc.add_holes(shape, spacing=8.0, hole_radius=1.2, inset=5.0, layer="stitch")
doc.save("custom_styles.svg")
```

### 8. Symmetric Polygon with stitch holes

```python
from leathercraft_svg import Polygon, SvgDocument

doc = SvgDocument(150, 80)

left_half = [
    (75, 5),
    (40, 5),
    (20, 40),
    (40, 75),
    (75, 75),
]

shape = Polygon.from_mirror(left_half, center_x=75, smooth=True)
doc.add_shape(shape, layer="cut")
doc.add_holes(shape, spacing=8.0, hole_radius=1.2, inset=5.0, layer="stitch")
doc.save("polygon_mirror.svg")
```

### 9. Open polyline stitch seam (e.g. sleeve side edges)

```python
from leathercraft_svg import SvgDocument, StrokeStyle, offset_polyline, mirror_polyline

doc = SvgDocument(150, 100, styles={
    "cut":    StrokeStyle("#ff0000", 0.12),
    "stitch": StrokeStyle("#0000ff", 0.35),
})

left_edge = [(30, 10), (20, 50), (30, 90)]
left_seam  = offset_polyline(left_edge, distance=4.0, side="right")
right_seam = mirror_polyline(left_seam, center_x=75)

doc.add_stitch_on_polyline(left_seam,  spacing=6, stitch_length=2.4, layer="stitch")
doc.add_stitch_on_polyline(right_seam, spacing=6, stitch_length=2.4, layer="stitch")
doc.save("seam.svg")
```

### 7. Mix holes and raw geometry

```python
from leathercraft_svg import Rectangle, SvgDocument

doc = SvgDocument(120, 80)
shape = Rectangle(10, 10, 100, 60)

doc.add_shape(shape, layer="cut")
doc.add_holes(shape, spacing=8.0, hole_radius=1.2, inset=5.0, layer="stitch")

# Add a guide line and a crease mark
doc.add_line(10, 40, 110, 40, layer="guide")
doc.add_line(60, 10, 60, 70, layer="crease")

doc.save("mixed.svg")
```

---

## Common mistakes

| Mistake | Fix |
|---------|-----|
| `inset` too small → holes overlap the cut edge | Keep `inset >= hole_radius + 1` |
| `spacing` smaller than `stitch_length` → stitches overlap | Keep `stitch_length < spacing` |
| Using `rounded_path=True` on Rectangle/Circle | Only affects RoundedTriangle; safe to pass but has no effect |
| Forgetting `layer="stitch"` for holes | Default is `"cut"` (red); use `"stitch"` (blue) for stitching guides |
| `radius` too large on RoundedRectangle | Automatically clamped — no error, but visual result may surprise you |
| Edge index out of range | Rectangle/RoundedRectangle/Stadium: 0–3; Triangle/RoundedTriangle: 0–2 |
| `Polygon.from_mirror` half doesn't start/end on axis | Both endpoints must have `x == center_x`; otherwise the seam won't close |
| `offset_polyline` side="right" goes outward | For a left edge going top→bottom, "right" is inward. Swap to "left" if offset goes the wrong way |
| `smooth=True` on a polygon with few/collinear points | Works but may produce unexpected curves; preview the SVG before cutting |

---

## DSL Compiler — leathercraft_dsl.py

Use the DSL when you need to generate a pattern **without writing Python**. The DSL compiles `.lcraft` text files into SVG/PNG via the same `leathercraft_svg` library.

### Import surface

```python
from leathercraft_dsl import parse, compile_document, build_file, DslError
```

| Function | Description |
|----------|-------------|
| `parse(text: str) -> PatternDocument` | Tokenise and validate DSL text; returns AST |
| `compile_document(doc: PatternDocument) -> SvgDocument` | Convert AST to a ready-to-render `SvgDocument` |
| `build_file(path) -> SvgDocument` | Parse + compile + export a `.lcraft` file on disk |

### CLI — compile one file

```bash
python leathercraft_dsl.py build pattern.lcraft
# writes pattern.svg + pattern.png next to the source file
```

### CLI — watch a directory

```bash
python leathercraft_watch.py [directory]        # watch, rebuild on every save
python leathercraft_watch.py . --build-all      # also build everything at startup
python leathercraft_watch.py examples/dsl -i 1  # 1-second poll interval
```

`leathercraft_watch.py` scans recursively for `*.lcraft` files, detects mtime changes, and calls `build_file()` automatically. DSL errors are printed without stopping the watcher.

---

### DSL syntax overview

The DSL is line-based. Empty lines and `#` comments are ignored. All numeric values are **millimeters** — no unit suffixes allowed.

```text
# This is a comment
pattern my_pattern        # optional name
size 150 112              # document width height
```

Blocks start with a keyword and end with `end`:

```text
rectangle panel
  at 10 10
  size 100 60
end
```

Indentation is optional but recommended.

---

### Document commands

| Keyword | Syntax | Notes |
|---------|--------|-------|
| `pattern` | `pattern <name>` | Optional; used as default export filename |
| `size` | `size <width> <height>` | **Required.** All in mm |
| `layer` | `layer <name> <color> <stroke_width> [dashed]` | Overrides default layer styles |
| `symmetry` | `symmetry <x>` or `symmetry vertical x=<x>` | Sets vertical mirror axis for mirrored shapes/stitches/holes |

**Layer color** can be a named color (`red`, `blue`, `green`, `gray`) or a hex value (`#ff0000`).

If `layer` commands are omitted, the compiler uses the same defaults as `SvgDocument` (red cut, blue stitch, green crease, gray guide).

---

### Variables and expressions

Define document-level variables with `<name> = <expression>` and reuse them anywhere a number is expected. Evaluated in file order; define before use; no reassignment. Implemented with a safe AST whitelist (never `eval`).

```text
width = 150
height = 112
axis = width / 2
margin = 4
corner_radius = min(8, height / 4)

size width height
symmetry axis
```

| Rule | Detail |
|------|--------|
| Operators | `+`, `-`, `*`, `/`, parentheses, unary `+`/`-` |
| Functions | `min`, `max`, `abs`, `round`, `floor`, `ceil` (whitelist only) |
| Variable names | `[A-Za-z_][A-Za-z0-9_]*`; structural keywords forbidden, parameter names (`radius`, `spacing`, `margin`, `length`, `angle`, `rx`, `ry`) allowed |
| Multi-value commands | Simple form `size width height`; for complex expressions use commas: `size width - 2 * margin, height - 2 * margin` |
| `symmetry vertical x=75` | Still a command, NOT an assignment (whitespace before `=`) |

Common errors (all raise `DslError` with line numbers): `unknown variable 'x'`, `variable 'x' is already defined`, `division by zero`, `invalid variable name 'x'`, `'size' is a reserved keyword...`, `unsupported function 'sin'`, `command 'size' expects 2 values. Use commas...`.

Full reference: `leathercraft_dsl_variables_expressions.md`. Example: `examples/dsl/variables_rounded_pocket.lcraft`.

---

### Shapes

#### `rectangle`

```text
rectangle <id>
  at <x> <y>
  size <width> <height>
  [layer <layer_name>]
end
```

Compiles to `Rectangle(x, y, width, height)` + `doc.add_shape(...)`. Default layer: `cut`.

#### `rounded_rectangle`

```text
rounded_rectangle <id>
  at <x> <y>
  size <width> <height>
  radius <r>                  # uniform — all four corners
  [radius_tl <r>]             # per-corner overrides (top-left, top-right,
  [radius_tr <r>]             #  bottom-right, bottom-left); 0 = sharp corner
  [radius_br <r>]
  [radius_bl <r>]
  [layer <layer_name>]
end
```

Compiles to `RoundedRectangle(x, y, width, height, radius, radius_tl=…, …)`. Either `radius` (must be > 0) or at least one per-corner key is required. When only per-corner keys are given, unspecified corners are sharp (0). When `radius` is combined with per-corner keys, the per-corner values override the uniform radius for those corners. Per-corner values must be >= 0.

#### `stadium`

```text
stadium <id>
  at <x> <y>
  size <width> <height>
  [layer <layer_name>]
end
```

Compiles to `Stadium(x, y, width, height)` — a capsule / oblong: a rectangle whose two short ends are replaced by semicircles. The cap radius is computed automatically as `min(width, height) / 2` — there is no `radius` key. Width and height must be > 0. With `edges all` (the default), stitches and holes follow the full capsule contour including the curved caps; with a numeric subset of edges (`0`–`3`) they fall back to straight inset edges like a plain rectangle.

#### `circle`

```text
circle <id>
  at <cx> <cy>
  radius <r>
  [layer <layer_name>]
end
```

Compiles to `Circle(cx, cy, radius)`. The `edges` parameter in `stitches`/`holes` is accepted but has no effect — the full circumference is always used.

#### `arc`

```text
arc <id>
  at <cx> <cy>            # centre
  radius <r>              # outer radius (> 0)
  [inner_radius <r>]      # > 0 → ring segment instead of wedge; must be < radius
  from_angle <deg>        # 0 = right (3 o'clock), increasing clockwise
  to_angle <deg>          # if <= from_angle, a full turn is added
  [layer <layer_name>]
end
```

Compiles to `Arc(cx, cy, radius, start_angle, end_angle, inner_radius)`. The `edges` parameter in `stitches`/`holes` is accepted but has no effect — the full closed contour is always used.

#### `ellipse`

Two forms are supported.

**Radii form:**

```text
ellipse <id>
  at <cx> <cy>
  rx <horizontal_radius>
  ry <vertical_radius>
  [layer <layer_name>]
end
```

**Size form** (`rx = width / 2`, `ry = height / 2`):

```text
ellipse <id>
  at <cx> <cy>
  size <width> <height>
  [layer <layer_name>]
end
```

Compiles to `Ellipse(cx, cy, rx, ry)`. Both radii must be > 0. The `edges` parameter in `stitches`/`holes` is accepted but has no effect — the full contour is always used.

#### `regular_polygon`

```text
regular_polygon <id>
  at <cx> <cy>
  radius <r>
  sides <n>
  [rotation <deg>]
  [layer <layer_name>]
end
```

Compiles to `RegularPolygon(cx, cy, radius, sides, rotation_deg=rotation)`. `radius` must be > 0. `sides` must be a whole number >= 3. The default rotation is `-90`, which places the first vertex at the top. Stitches and holes can use the full contour or selected numeric edges such as `0 1 2`.

#### `rounded_regular_polygon`

```text
rounded_regular_polygon <id>
  at <cx> <cy>
  radius <r>                # circumscribed radius (center -> vertex)
  sides <n>
  [corner_radius <r>]       # uniform rounding for all corners
  [rotation <deg>]
  [corner_radius_0 <r>]     # per-corner overrides by vertex index
  [corner_radius_1 <r>]
  ...
  [layer <layer_name>]
end
```

Compiles to `RoundedRegularPolygon(cx, cy, radius, sides, corner_radius=..., rotation_deg=rotation, corner_overrides=...)`. `radius` is the polygon size and must be > 0. `sides` must be a whole number >= 3. Use `corner_radius` for uniform rounding, or omit it and provide only `corner_radius_<index>` keys to round selected vertices while leaving the others sharp. Override values must be >= 0 and must refer to valid vertex indices for the chosen side count. With all edges selected, stitches and holes follow the rounded contour; partial edge selections use straight inset edges.

#### `triangle`

Two forms are supported.

**Three-point form:**

```text
triangle <id>
  p1 <x> <y>
  p2 <x> <y>
  p3 <x> <y>
  [layer <layer_name>]
end
```

**Box form** (equivalent to `Triangle.from_box`):

```text
triangle <id>
  at <x> <y>
  size <width> <height>
  [layer <layer_name>]
end
```

Box form sets p1 = top-center, p2 = bottom-right, p3 = bottom-left.

Compiles to `Triangle(Point(p1x, p1y), Point(p2x, p2y), Point(p3x, p3y))`.

Triangle edge indices for the `edges` field: `0` = p1→p2, `1` = p2→p3, `2` = p3→p1.

#### `rounded_triangle`

Same as `triangle`, with an additional required `radius` field (same two forms supported).

```text
rounded_triangle <id>
  p1 <x> <y>
  p2 <x> <y>
  p3 <x> <y>
  radius <r>
  [layer <layer_name>]
end
```

Compiles to `RoundedTriangle(Point(p1x, p1y), Point(p2x, p2y), Point(p3x, p3y), radius=r)`.

Supports the `rounded_path` flag in `stitches`/`holes` (see below).

#### `outer` — freeform shape

```text
outer [smooth|straight] [mirrored]
  <x> <y>
  <x> <y>
  ...
end
```

Compiles to `Polygon(points)` or `Polygon.from_mirror(points, center_x)`.

There is no separate DSL `polygon` block at the moment. Use `outer` for custom closed outlines.

- `smooth` → quadratic Bézier contour; `straight` → straight segments (default).
- `mirrored` → requires a global `symmetry` axis; the listed points describe **one half** of the shape (must start and end on the axis).
- Default layer: `cut`. Shape is registered as id `"outer"`.

---

### Operations

#### `stitches` — on a named shape

```text
stitches
  source <shape_id>
  [edges <edge_name_or_index>...]
  [margin <mm>]
  [spacing <mm>]
  [length <mm>]
  [angle <degrees>]
  [layer <layer_name>]
  [rounded_path]
  [distribution fixed_spacing|fit_evenly]
  [path_mode per_edge|continuous|continuous_rounded]
  [first_margin <mm>]
  [last_margin <mm>]
end
```

Compiles to `doc.add_stitch_pattern(shape, edges=..., inset=margin, rounded_path=..., ...)`.

Default values: `edges all`, `margin 4`, `spacing 5`, `length 3`, `angle 0`, `layer stitch`, `rounded_path false`, `distribution fixed_spacing`, `path_mode continuous`.

- `path_mode continuous` (default) distributes stitches along connected edge chains, eliminating the double gap at shared corners.
- `path_mode per_edge` distributes each selected edge independently (old behaviour).
- `path_mode continuous_rounded` like `continuous` but follows arc curves at rounded corners (`RoundedRectangle`).
- `first_margin` / `last_margin`: explicit margin in mm from each open chain end. Omit for auto-centering.
- `include_corners` has been **removed** — use `first_margin 0` / `last_margin 0` instead.

The `rounded_path` flag (no value) makes stitches follow the smooth curved contour of a `RoundedTriangle`. It is safe to use on other shapes but has no visible effect.

#### `stitches` — along a custom path

```text
stitches
  [side left|right]
  [mirror]
  margin <mm>
  spacing <mm>
  length <mm>
  [angle <degrees>]
  [layer <layer_name>]
  [distribution fixed_spacing|fit_evenly]

  path
    <x> <y>
    <x> <y>
    ...
  end
end
```

Compiles to `offset_polyline(path_points, distance=margin, side=side)` then `doc.add_stitch_on_polyline(seam, ...)`.

- `side` defaults to `"right"`.
- If `mirror` is present, a mirrored copy is also rendered using `mirror_polyline(seam, symmetry_axis_x)`. Requires `symmetry`.

#### `holes` — on a named shape

```text
holes
  source <shape_id>
  [edges <edge_name_or_index>...]
  [margin <mm>]
  [spacing <mm>]
  [radius <mm>]
  [layer <layer_name>]
  [rounded_path]
  [distribution fixed_spacing|fit_evenly]
  [path_mode per_edge|continuous|continuous_rounded]
  [first_margin <mm>]
  [last_margin <mm>]
end
```

Compiles to `doc.add_holes(shape, edges=..., inset=margin, hole_radius=radius, rounded_path=..., ...)`.

Default values: `edges all`, `margin 4`, `spacing 6`, `radius 1.2`, `layer cut`, `rounded_path false`, `distribution fixed_spacing`, `path_mode continuous`.

- `path_mode continuous` (default) distributes holes along connected edge chains without double corner gaps.
- `first_margin` / `last_margin`: explicit margin in mm at each open chain end. Omit for auto-centering.
- `include_corners` has been **removed** — use `first_margin 0` / `last_margin 0` instead.

The `rounded_path` flag applies to `RoundedTriangle` (follows smooth corners); safe but no-op on other shapes.

#### `hole` — single or mirrored circle

Single hole:

```text
hole <id>
  at <x> <y>
  radius <r>
  [layer <layer_name>]
end
```

Compiles to `doc.add_circle(x, y, radius)`.

Mirrored pair (requires `symmetry`):

```text
hole <id>
  mirror
  x_from_center <distance>
  y <y>
  radius <r>
  [layer <layer_name>]
end
```

Places circles at `(axis_x − distance, y)` and `(axis_x + distance, y)`.

---

### Edges

**Rectangle / RoundedRectangle** — named tokens:

| Token | Equivalent indices |
|-------|--------------------|
| `top` | `[0]` |
| `right` | `[1]` |
| `bottom` | `[2]` |
| `left` | `[3]` |
| `all` | `[0, 1, 2, 3]` |
| `except_top` | `[1, 2, 3]` |
| `sides` | `[1, 3]` |
| `horizontal` | `[0, 2]` |
| `vertical` | `[1, 3]` |

Multiple names can be combined: `edges left bottom right`.

**Triangle / RoundedTriangle / RegularPolygon / RoundedRegularPolygon** — numeric indices:

| Index | Edge |
|-------|------|
| `0` | p1 → p2 |
| `1` | p2 → p3 |
| `2` | p3 → p1 |

Example: `edges 0 2` selects the first and third edge. `edges all` selects all three.

**Circle** — `edges` is accepted but ignored; holes/stitches always use the full circumference.

---

### Export

```text
export <name>               # writes <name>.svg + <name>.png
export svg <filename>       # SVG only
export png <filename>       # PNG only
export pdf <filename>       # PDF via cairosvg
export dxf <filename>       # DXF via ezdxf
```

If no `export` command is present, the compiler writes `<pattern_name>.svg` and `<pattern_name>.png` using the `pattern` name or the source filename stem.

---

### Validation errors

The compiler raises `DslError` with clear messages:

| Situation | Error message |
|-----------|---------------|
| `size` missing | `missing required command 'size'` |
| Unknown shape reference | `stitches block references unknown source 'panel2'` |
| `mirror` without `symmetry` | `hole 'keyring' uses mirror but no symmetry axis is defined` |
| Invalid edge name | `unknown edge 'lower'. Use: top, right, bottom, left, ...` |
| Zero or negative radius | `radius must be greater than 0` |
| Unit suffix in value | `units are not allowed in numeric values. Use 'size 150 112', not 'size 150mm 112mm'` |
| Block without `end` | `missing 'end' for block 'rounded_rectangle panel'` |

---

### Complete DSL examples

#### Rectangle with stitches on all edges

```text
pattern card_panel
size 120 80

rectangle panel
  at 10 10
  size 100 60
end

stitches
  source panel
  edges all
  margin 4
  spacing 5
  length 3
end

export card_panel
```

#### Rounded rectangle — stitches except top

```text
pattern rounded_pocket
size 120 90

rounded_rectangle pocket
  at 10 10
  size 100 70
  radius 8
end

stitches
  source pocket
  edges except_top
  margin 5
  spacing 5
  length 3.5
  angle 45
end

export rounded_pocket
```

#### Panel with punch holes

```text
pattern panel_with_holes
size 120 80

rectangle panel
  at 10 10
  size 100 60
end

holes
  source panel
  edges all
  margin 4
  spacing 6
  radius 1.2
end

export panel_with_holes
```

#### Symmetric lighter sleeve

```text
pattern lighter_sleeve
size 150 112

layer cut red 0.12
layer stitch blue 0.35

symmetry 75

outer smooth mirrored
  75 14
  59 11
  43 8
  28 11
  17 11
  18 27
  18 36
  36 42
  40 51
  40 74
  37 97
  47 102
  61 105
  75 105
end

stitches
  margin 4
  spacing 5
  length 3.8
  mirror

  path
    43 15
    28 11
    17 11
    18 27
    18 36
    36 42
    40 51
    40 74
    37 97
    47 102
    61 105
    75 105
  end
end

hole keyring
  mirror
  x_from_center 30
  y 21
  radius 2.2
end

export lighter_sleeve
```

---

### DSL common mistakes

| Mistake | Fix |
|---------|-----|
| Writing `size 150mm 112mm` | Remove unit suffixes: `size 150 112` |
| `stitches` with `mirror` but no `symmetry` | Add `symmetry <x>` at document level |
| `outer mirrored` without `symmetry` | Same as above |
| Referencing a shape before it is declared | Shape blocks must appear before the `stitches`/`holes` that reference them |
| `hole` with `mirror` but missing `x_from_center` or `y` | Both fields are required for mirrored holes |
| `outer` half-points don't start/end on the axis | First and last point must have `x == symmetry_axis_x` |
| Using a reserved keyword as a shape id | Avoid names like `path`, `end`, `source`, `layer`, `p1`, etc. |
| Using named edge tokens (`top`, `left`) for a `triangle` | Triangles use numeric indices: `edges 0 1 2` or `edges all` |
| Using numeric edge indices for a `rectangle` | Rectangles use named tokens: `top`, `right`, `bottom`, `left`, or aliases |
| `rounded_path` on a `rectangle` or `circle` | Safe to write but has no visible effect; only meaningful for `rounded_triangle` |
| `triangle` block with neither `p1/p2/p3` nor `at + size` | Provide all three points, or use box form with both `at` and `size` |
| `rounded_triangle` without `radius` | `radius` is required and must be > 0 |

---

## SVG output characteristics

- No CSS; all styles are inline attributes.
- `viewBox` matches document size in millimeters.
- `vector-effect="non-scaling-stroke"` on every element.
- Compatible with CairoSVG and Inkscape.
