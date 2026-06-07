# laser_svg

Library for generating simple SVG files for laser cutting, stitching, and scoring.
It supports shapes, edge points, stitching holes, and PNG export with a white background.

Main features:

- no CSS in the generated SVG, styles are written inline on each element,
- layers: `cut`, `stitch`, `crease`, `guide`,
- automatic hole generation along shape edges,
- optional laser stitch pattern (short line segments) as an alternative to holes,
- SVG and PNG export,
- simple API built around geometry classes.

## Installation

The project uses Python 3.13+ and requires `cairosvg` for PNG export.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install cairosvg
```

If you only want to generate SVG, the library works without any extra packages.

## Quick Start

```python
from laser_svg import Rectangle, SvgDocument

doc = SvgDocument(width_mm=100, height_mm=60)
shape = Rectangle(10, 10, 80, 40)

doc.add_shape(shape)
doc.add_holes(shape, spacing=8.0, hole_radius=1.2, inset=5.0)

doc.save("example.svg")
doc.save_png("example.png", background_color="white")
```

## Running the Example

The repository includes a ready-made example:

```bash
./.venv/bin/python example_shapes.py
```

This generates:

- `example_shapes.svg`
- `example_shapes.png`

The `test.sh` script runs the same example and opens the PNG.

## SVG Format

The generated SVG:

- does not use CSS,
- writes colors, stroke width, and dash patterns directly on the elements,
- uses a `viewBox` aligned with the document size in millimeters,
- applies `vector-effect="non-scaling-stroke"`.

This improves compatibility with renderers that handle class-based styles poorly.

## Layers and Styles

Default layers are defined as:

- `cut` - red, `#ff0000`, width `0.1`
- `stitch` - blue, `#0000ff`, width `0.1`
- `crease` - green, `#00aa00`, width `0.1`, dash pattern `3 2`
- `guide` - gray, `#777777`, width `0.1`, dash pattern `2 2`

Every element added to the document can be assigned to one of these layers.

## API

### `SvgDocument(width_mm, height_mm, styles=None)`

Creates an SVG document.

Parameters:

- `width_mm` - document width in millimeters,
- `height_mm` - document height in millimeters,
- `styles` - optional `dict[str, StrokeStyle]` with custom styles.

If you do not pass `styles`, the default styles are used.

### `doc.add_shape(shape, layer="cut")`

Adds a shape as an SVG path.

Parameters:

- `shape` - an object that inherits from `Shape`,
- `layer` - target layer: `cut`, `stitch`, `crease`, or `guide`.

### `doc.add_path(d, layer="cut")`

Adds a raw SVG path.

Parameters:

- `d` - SVG path `d` attribute,
- `layer` - style layer.

### `doc.add_line(x1, y1, x2, y2, layer="cut")`

Adds an SVG line.

Parameters:

- `x1`, `y1` - start point,
- `x2`, `y2` - end point,
- `layer` - style layer.

### `doc.add_circle(x, y, radius, layer="cut")`

Adds an SVG circle.

Parameters:

- `x`, `y` - center,
- `radius` - radius,
- `layer` - style layer.

### `doc.add_holes(shape, edges="all", spacing=5.0, hole_radius=1.2, inset=4.0, layer="cut", include_corners=False)`

Adds holes computed from the edges of a shape.

Parameters:

- `shape` - shape that implements `hole_points()`,
- `edges` - which edges to use: `"all"` or a list of indices,
- `spacing` - distance between holes,
- `hole_radius` - radius of the holes,
- `inset` - distance from the edge,
- `layer` - layer for the holes,
- `include_corners` - if `True`, hole placement starts and ends at corners; if `False`, holes are offset from edge endpoints.

### `doc.add_stitch_holes(...)`

Alias for `add_holes(...)` with the same parameters.

### `doc.add_stitch_pattern(shape, edges="all", spacing=5.0, stitch_length=2.0, inset=4.0, layer="stitch", include_corners=False, stitch_thickness=None)`

Adds a laser stitch pattern (short line segments) on selected shape edges.

Parameters:

- `shape` - shape that implements `stitch_segments()`,
- `edges` - which edges to use: `"all"` or a list of indices,
- `spacing` - distance between stitches,
- `stitch_length` - length of each stitch segment,
- `inset` - distance from the edge,
- `layer` - layer for the stitches,
- `include_corners` - whether stitches are also placed at corners,
- `stitch_thickness` - optional per-pattern stroke width override (if `None`, the layer default is used).

### `doc.save(path)`

Saves the SVG to a file.

### `doc.save_png(path, background_color="white")`

Saves a PNG through CairoSVG.

Parameters:

- `path` - output PNG path,
- `background_color` - background color, defaults to `white`.

## Geometry Classes

### `Point(x, y)`

Two-dimensional point.

Fields:

- `x`
- `y`

### `Rectangle(x, y, width, height)`

Axis-aligned rectangle.

Parameters:

- `x`, `y` - top-left corner,
- `width` - width,
- `height` - height.

Methods:

- `path_d()` - returns the SVG path,
- `hole_points(edges="all", spacing=5.0, inset=4.0, include_corners=False)` - returns hole points on selected edges.

Rectangle edge indices:

- `0` - top,
- `1` - right,
- `2` - bottom,
- `3` - left.

### `RoundedRectangle(x, y, width, height, radius=5.0)`

Rectangle with rounded corners.

Parameters:

- `x`, `y`, `width`, `height` - as above,
- `radius` - corner radius.

### `Circle(cx, cy, radius)`

Circle.

Parameters:

- `cx`, `cy` - center,
- `radius` - radius.

The `hole_points(...)` method for a circle places points around a helper circle with radius `radius - inset`.

### `Triangle(p1, p2, p3)`

Triangle defined by three points.

Parameters:

- `p1`, `p2`, `p3` - vertices as `Point` objects.

#### `Triangle.from_box(x, y, width, height)`

Creates a triangle inscribed in a rectangle.

Points:

- `p1` - midpoint of the top edge,
- `p2` - bottom-right corner,
- `p3` - bottom-left corner.

Triangle edge indices:

- `0` - `p1 -> p2`,
- `1` - `p2 -> p3`,
- `2` - `p3 -> p1`.

### `RoundedTriangle(p1, p2, p3, radius=5.0)`

Triangle with rounded corners.

Parameters:

- `p1`, `p2`, `p3` - vertices,
- `radius` - corner rounding radius.

## Shared `hole_points(...)` Parameters

All shapes implement the method:

```python
hole_points(
    edges="all",
    spacing=5.0,
    inset=4.0,
    include_corners=False,
)
```

Parameter meaning:

- `edges` - edges on which points should be generated,
- `spacing` - distance between consecutive points,
- `inset` - offset from edges or corners,
- `include_corners` - whether corners are used as start and end points.

If `edges="all"`, all edges of the shape are used.

## Examples

### Rectangle with holes on all edges

```python
from laser_svg import Rectangle, SvgDocument

doc = SvgDocument(100, 60)
shape = Rectangle(10, 10, 80, 40)

doc.add_shape(shape)
doc.add_holes(shape, edges="all", spacing=8.0, hole_radius=1.2, inset=5.0)
doc.save("rect.svg")
```

### Triangle with holes only on selected edges

```python
from laser_svg import Point, Triangle, SvgDocument

doc = SvgDocument(120, 90)
shape = Triangle(Point(20, 20), Point(100, 70), Point(20, 70))

doc.add_shape(shape)
doc.add_holes(shape, edges=[0, 2], spacing=10.0, hole_radius=1.0, inset=6.0)
doc.save("triangle.svg")
```

### PNG export with a white background

```python
doc.save_png("output.png", background_color="white")
```

### Laser stitch pattern instead of holes

```python
from laser_svg import RoundedRectangle, SvgDocument

doc = SvgDocument(140, 90)
shape = RoundedRectangle(20, 15, 100, 60, radius=10)

doc.add_shape(shape, layer="cut")
doc.add_stitch_pattern(
    shape,
    edges=[0, 2],
    spacing=8.0,
    stitch_length=3.5,
    inset=7.0,
    layer="stitch",
    stitch_thickness=0.25,
)
doc.save("stitch_pattern.svg")
```

## Compatibility

The project has been tuned for renderers that handle SVG CSS poorly.
If you use an external rasterizer, prefer tools with strong inline SVG support, such as CairoSVG or Inkscape.

## File Structure

- `laser_svg.py` - library and geometry models,
- `example_shapes.py` - example that generates several shapes,
- `test.sh` - simple script that runs the example,
- `README.md` - documentation.

## Practical Notes

- If you want to change the look of elements, the easiest approach is to pass a custom `styles` dictionary to `SvgDocument`.
- If you want different spacing, adjust `spacing` and `inset`.
- If you want denser or larger holes, change `hole_radius`.
