# leathercraft_svg — AI Agent Reference

This file is intended for AI agents generating code with the `leathercraft_svg` library. It covers every public class and method, default values, edge indices, key constraints, and annotated examples. Read this before writing any code.

---

## Setup

```python
# Standard import pattern — all public names live in leathercraft_svg
from leathercraft_svg import (
    SvgDocument, StrokeStyle,
    Point,
    Rectangle, RoundedRectangle,
    Circle,
    Triangle, RoundedTriangle,
)
```

Requires Python 3.13+. `save_png` requires `cairosvg`; `save` (SVG only) has no dependencies.

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
| `to_svg()` | Return SVG as a string |
| `add_stitch_on_polyline(points, ...)` | Add stitch marks along an open `(x,y)` polyline |

### `add_holes` signature

```python
doc.add_holes(
    shape,
    edges="all",          # "all" or list of int edge indices
    spacing=5.0,          # mm between hole centers
    hole_radius=1.2,      # mm hole radius
    inset=4.0,            # mm offset inward from edge
    layer="cut",
    include_corners=False,
    rounded_path=False,   # follow rounded contour (RoundedTriangle only)
)
```

### `add_stitch_on_polyline` signature

```python
doc.add_stitch_on_polyline(
    points,                  # list of (x, y) tuples — open polyline
    spacing=5.0,             # mm between stitch centres
    stitch_length=2.0,       # mm length of each stitch
    stitch_angle_deg=0.0,    # 0 = parallel to path, 45 = diagonal
    layer="stitch",
    stitch_thickness=None,   # overrides layer stroke width
)
```

### `add_stitch_pattern` signature

```python
doc.add_stitch_pattern(
    shape,
    edges="all",
    spacing=5.0,
    stitch_length=2.0,    # mm length of each stitch line
    inset=4.0,
    layer="stitch",
    include_corners=False,
    stitch_thickness=None,  # float or None; overrides layer stroke width
    stitch_angle_deg=0.0,   # 0 = parallel to edge, 45 = diagonal
    rounded_path=False,
)
```

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
RoundedRectangle(x, y, width, height, radius=5.0)
```

Same edge indices as Rectangle (0=top, 1=right, 2=bottom, 3=left). Corner radius is automatically clamped to `min(radius, width/2, height/2)`.

When `edges="all"`, the stitch pattern follows the smooth rounded contour. For partial edge selections it falls back to straight-edge placement.

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
| `stitch_angle_deg` | 0 or 45 | 0 = parallel to edge, 45 = diagonal cross |
| `stitch_thickness` | 0.1–1.0 mm | Stroke width for stitch lines (overrides layer) |
| `include_corners` | False (default) | True = holes extend to corners |
| `rounded_path` | False (default) | True = follow curved contour (RoundedTriangle) |

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
| Edge index out of range | Rectangle/RoundedRectangle: 0–3; Triangle/RoundedTriangle: 0–2 |
| `Polygon.from_mirror` half doesn't start/end on axis | Both endpoints must have `x == center_x`; otherwise the seam won't close |
| `offset_polyline` side="right" goes outward | For a left edge going top→bottom, "right" is inward. Swap to "left" if offset goes the wrong way |
| `smooth=True` on a polygon with few/collinear points | Works but may produce unexpected curves; preview the SVG before cutting |

---

## SVG output characteristics

- No CSS; all styles are inline attributes.
- `viewBox` matches document size in millimeters.
- `vector-effect="non-scaling-stroke"` on every element.
- Compatible with CairoSVG and Inkscape.
