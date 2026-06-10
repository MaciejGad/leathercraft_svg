# Leathercraft Pattern DSL — Draft Specification

## 1. Goal

The DSL describes leathercraft cutting patterns in a text format without requiring Python code.

A DSL file should allow the user to define document size, layers, outer shapes, rectangles, rounded rectangles, freeform paths, mirrored shapes, stitch patterns, holes, keyring holes, and exports.

The DSL is not meant to expose all internal geometry details. It should describe intent, while the compiler converts it to `leathercraft_svg` calls.

Example command:

```bash
leathercraft-svg build lighter_sleeve.lcraft
```

Expected outputs may include:

```text
lighter_sleeve.svg
lighter_sleeve.pdf
lighter_sleeve.png
```

## 2. Basic Syntax

The DSL is line-based.

Empty lines are ignored.

Comments start with `#`.

```text
# This is a comment
pattern lighter_sleeve
size 150 112
```

Blocks start with a keyword and end with `end`.

```text
rounded_rectangle panel
  at 10 10
  size 100 60
  radius 8
end
```

Indentation is recommended for readability but should not be required by the parser.

Values are separated by spaces.

```text
at 10 10
size 100 60
radius 8
```

All numeric dimensions are interpreted as millimeters. The DSL supports only millimeters. Do not write unit suffixes such as `mm`, `cm`, `in`, `pt`, or `px` in the pattern file.

Correct:

```text
size 150 112
radius 8
margin 4
```

Incorrect:

```text
size 150mm 112mm
radius 8mm
margin 4mm
```

## 3. Minimal File Structure

A typical file should look like this:

```text
pattern example
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

export example
```

## 4. Document Commands

### `pattern`

Defines the pattern name.

```text
pattern lighter_sleeve
```

Syntax:

```text
pattern <name>
```

The name may be used as the default export filename.

### `size`

Defines document/page size in millimeters.

```text
size 150 112
```

Syntax:

```text
size <width> <height>
```

Example:

```text
size 120 80
```

## 5. Layers

Layers define visual/export styles.

```text
layer cut red 0.12
layer stitch blue 0.35
layer guide gray 0.12 dashed
```

Syntax:

```text
layer <name> <color> <stroke_width> [style]
```

The stroke width is interpreted as millimeters.

Color may be a named color or hex value.

```text
layer cut #ff0000 0.12
layer stitch #0000ff 0.35
```

Recommended default layers:

```text
layer cut red 0.12
layer stitch blue 0.35
layer guide gray 0.12 dashed
```

If layers are not defined, the compiler should use defaults:

```text
cut: red, 0.2
stitch: blue, 0.2
crease: green, 0.2 dashed
guide: gray, 0.2 dashed
```

## 6. Symmetry

Global symmetry can be declared once.

```text
symmetry 75
```

Equivalent verbose form:

```text
symmetry vertical x=75
```

Syntax:

```text
symmetry <x>
```

or:

```text
symmetry vertical x=<x>
```

This means vertical mirror axis at `x` millimeters.

Used by:

```text
outer smooth mirrored
hole ... mirror
stitches ... mirror
```

## 7. Shapes

### 7.1 Rectangle

```text
rectangle panel
  at 10 10
  size 100 60
  layer cut
end
```

Syntax:

```text
rectangle <id>
  at <x> <y>
  size <width> <height>
  [layer <layer_name>]
end
```

Compiler mapping:

```python
Rectangle(x, y, width, height)
doc.add_shape(shape, layer="cut")
```

Default layer: `cut`.

Example with stitches:

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

### 7.2 Rounded Rectangle

```text
rounded_rectangle panel
  at 10 10
  size 100 60
  radius 8
end
```

Syntax:

```text
rounded_rectangle <id>
  at <x> <y>
  size <width> <height>
  radius <radius>             # uniform — all four corners
  [radius_tl <radius>]        # optional per-corner overrides:
  [radius_tr <radius>]        #   tl = top-left,    tr = top-right
  [radius_br <radius>]        #   br = bottom-right, bl = bottom-left
  [radius_bl <radius>]        # 0 = sharp corner
  [layer <layer_name>]
end
```

Compiler mapping:

```python
RoundedRectangle(x, y, width, height, radius, radius_tl=…, radius_tr=…, radius_br=…, radius_bl=…)
doc.add_shape(shape, layer="cut")
```

Either `radius` (> 0) or at least one per-corner key is required:

- Only `radius` → all four corners use the uniform value (existing behaviour).
- Only per-corner keys → unspecified corners are sharp (radius 0).
- Both → per-corner keys override the uniform `radius` for those corners.

Per-corner values must be >= 0. If two radii on a shared edge would overlap, all radii are scaled down proportionally. Stitches with `edges all` follow the asymmetric rounded contour.

Example — card holder with rounded top and sharp bottom:

```text
rounded_rectangle card
  at 10 10
  size 100 75
  radius_tl 18
  radius_tr 18
end

stitches
  source card
  edges left bottom right
  margin 5
  spacing 5
  length 3
end
```

Example with stitches on three edges:

```text
pattern pocket_panel
size 120 90

rounded_rectangle pocket
  at 10 10
  size 100 70
  radius 8
end

stitches
  source pocket
  edges left bottom right
  margin 5
  spacing 5
  length 3.5
  angle 45
end

export pocket_panel
```

### 7.3 Stadium

A capsule / oblong: a rectangle whose two short ends are replaced by semicircles. The cap radius is computed automatically as `min(width, height) / 2` — there is no `radius` key. A wide bounding box gives caps on the left and right; a tall one gives caps on the top and bottom.

```text
stadium <id>
  at <x> <y>
  size <width> <height>
  [layer <layer_name>]
end
```

Compiler mapping:

```python
Stadium(x, y, width, height)
doc.add_shape(shape, layer="cut")
```

Both `width` and `height` must be > 0. Default layer: `cut`.

With `edges all` (the default), stitches and holes follow the full capsule contour, including the curved caps. With a numeric subset of edges (`0`–`3`, same indices as rectangle) they fall back to straight inset edges.

Example — key-fob blank:

```text
pattern key_fob
size 140 60

stadium fob
  at 10 15
  size 120 30
end

stitches
  source fob
  margin 4
  spacing 5
  length 3
end

export key_fob
```

### 7.4 Circle

```text
circle <id>
  at <cx> <cy>
  radius <r>
  [layer <layer_name>]
end
```

Compiler mapping:

```python
Circle(cx, cy, radius)
doc.add_shape(shape, layer="cut")
```

Default layer: `cut`.

Example with holes:

```text
circle medallion
  at 60 60
  radius 40
end

holes
  source medallion
  margin 7
  spacing 8
  radius 1.5
end
```

### 7.5 Ellipse

An oval defined by a centre point and two independent radii. Two forms are supported.

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

Compiler mapping:

```python
Ellipse(cx, cy, rx, ry)
doc.add_shape(shape, layer="cut")
```

Both radii must be > 0. Default layer: `cut`. Stitches and holes are distributed evenly along the elliptical contour; the `edges` parameter is accepted but ignored.

Example — oval coaster:

```text
pattern oval_coaster
size 130 90

ellipse rim
  at 65 45
  rx 55
  ry 35
end

stitches
  source rim
  margin 5
  spacing 6
  length 3
end

export oval_coaster
```

### 7.6 Arc / Sector

A circular sector (pie wedge) or — with `inner_radius` — a ring segment (annulus slice). Angles are in degrees: `0` = right (3 o'clock), increasing clockwise on screen. If `to_angle <= from_angle`, a full turn is added, so `from_angle 300` + `to_angle 60` spans 120° across 3 o'clock.

```text
arc <id>
  at <cx> <cy>            # centre
  radius <r>              # outer radius (> 0)
  [inner_radius <r>]      # > 0 → ring segment; must be < radius
  from_angle <deg>
  to_angle <deg>
  [layer <layer_name>]
end
```

Compiler mapping:

```python
Arc(cx, cy, radius, start_angle, end_angle, inner_radius)
doc.add_shape(shape, layer="cut")
```

Default layer: `cut`. Stitches and holes follow the full closed contour (outer arc, straight edges, and the inner arc for ring segments); the `edges` parameter is accepted but ignored.

Example — curved strap-end reinforcement:

```text
pattern strap_end
size 130 85

arc reinforcement
  at 65 75
  radius 55
  inner_radius 30
  from_angle 180
  to_angle 360
end

stitches
  source reinforcement
  margin 5
  spacing 6
  length 3
end

export strap_end
```

### 7.7 Triangle

Two forms are supported: explicit three-point form and box form.

**Three-point form:**

```text
triangle <id>
  p1 <x> <y>
  p2 <x> <y>
  p3 <x> <y>
  [layer <layer_name>]
end
```

**Box form** (creates `Triangle.from_box`):

```text
triangle <id>
  at <x> <y>
  size <width> <height>
  [layer <layer_name>]
end
```

In the box form `p1` is the midpoint of the top edge, `p2` is the bottom-right corner, `p3` is the bottom-left corner.

Compiler mapping:

```python
Triangle(Point(p1x, p1y), Point(p2x, p2y), Point(p3x, p3y))
doc.add_shape(shape, layer="cut")
```

Triangle edge indices (for numeric `edges` values):

- `0` = p1 → p2
- `1` = p2 → p3
- `2` = p3 → p1

Example with partial edges using numeric indices:

```text
triangle flap
  p1 60 10
  p2 110 80
  p3 10 80
end

stitches
  source flap
  edges 0 2
  margin 6
  spacing 8
  length 3.5
end
```

### 7.8 Rounded Triangle

Same as `triangle` but with an additional `radius` field.

**Three-point form:**

```text
rounded_triangle <id>
  p1 <x> <y>
  p2 <x> <y>
  p3 <x> <y>
  radius <r>
  [layer <layer_name>]
end
```

**Box form:**

```text
rounded_triangle <id>
  at <x> <y>
  size <width> <height>
  radius <r>
  [layer <layer_name>]
end
```

Compiler mapping:

```python
RoundedTriangle(Point(p1x, p1y), Point(p2x, p2y), Point(p3x, p3y), radius=r)
doc.add_shape(shape, layer="cut")
```

`radius` must be greater than 0.

The `rounded_path` flag (see section 9) applies specifically to `RoundedTriangle` and makes stitch marks or holes follow the smooth rounded corners instead of the straight inset.

### 7.9 Outer Freeform Shape

For irregular leather patterns, use `outer`.

```text
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
```

Syntax:

```text
outer [smooth|straight] [mirrored]
  <x> <y>
  <x> <y>
  ...
end
```

Behavior:

`straight` means connect points with straight line segments.

`smooth` means generate a smoother path using Bézier curves.

`mirrored` means the provided points describe one side or half of the object. The compiler mirrors them around the global symmetry axis and joins them.

Default layer: `cut`.

Equivalent verbose form:

```text
shape outer
  type smooth
  mirror true
  layer cut
  points
    75 14
    59 11
  end
end
```

Recommended MVP form is the short form:

```text
outer smooth mirrored
  ...
end
```

## 8. Edges

### Named edges (rectangle and rounded rectangle)

```text
top
right
bottom
left
all
```

Aliases:

```text
except_top = right bottom left
sides      = left right
horizontal = top bottom
vertical   = left right
```

Example:

```text
stitches
  source pocket
  edges except_top
  margin 5
  spacing 5
  length 3.5
end
```

The compiler translates aliases before validation.

### Numeric edge indices (triangle and rounded triangle)

For `triangle` and `rounded_triangle`, edges are selected by their numeric index:

- `0` = p1 → p2
- `1` = p2 → p3
- `2` = p3 → p1

```text
stitches
  source flap
  edges 0 2
  margin 6
  spacing 8
  length 3.5
end
```

Using `edges all` on a triangle selects all three edges.

### Circle

The `edges` parameter is accepted but has no effect on circles — holes and stitches are always distributed around the full circumference.

## 9. Stitches

Stitches describe short laser-cut stitch marks along a shape edge or custom path.

### 9.1 Stitches on a Shape

```text
stitches
  source panel
  edges all
  margin 4
  spacing 5
  length 3
  angle 0
end
```

Syntax:

```text
stitches
  source <shape_id>
  [edges <edge_name_or_index>...]
  [margin <distance>]
  [spacing <distance>]
  [length <distance>]
  [angle <degrees>]
  [layer <layer_name>]
  [rounded_path]
end
```

Defaults:

```text
edges all
margin 4
spacing 5
length 3
angle 0
layer stitch
rounded_path false
```

The optional `rounded_path` flag (no value) makes stitch marks follow the smooth rounded contour of a `RoundedTriangle`. It is accepted but has no visible effect on other shape types.

Compiler mapping for built-in shapes:

```python
doc.add_stitch_pattern(
    shape,
    edges=...,
    spacing=spacing,
    stitch_length=length,
    inset=margin,
    layer="stitch",
    stitch_angle_deg=angle,
)
```

Example:

```text
rounded_rectangle pocket
  at 10 10
  size 100 70
  radius 8
end

stitches
  source pocket
  edges left bottom right
  margin 5
  spacing 5
  length 3.5
end
```

### 9.2 Stitches Along Custom Path

For irregular shapes, stitches can be defined by a path.

```text
stitches
  margin 4
  spacing 5
  length 3.8
  angle 0
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
```

Syntax:

```text
stitches
  [source <shape_id>]
  [side left|right]
  [mirror]
  margin <distance>
  spacing <distance>
  length <distance>
  [angle <degrees>]

  path
    <x> <y>
    <x> <y>
    ...
  end
end
```

Behavior:

The `path` points describe the source path.

The compiler creates an offset path using `margin`.

Then it places stitch marks along that offset path.

If `mirror` is present, stitch segments are mirrored around the global symmetry axis.

`side` defines which side of the path the offset should use.

For a left edge defined top-to-bottom, `side right` usually means “inside”.

Defaults:

```text
side right
margin 4
spacing 5
length 3
angle 0
layer stitch
```

Example for lighter sleeve:

```text
stitches
  margin 4
  spacing 5
  length 3.8
  angle 0
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
```

## 10. Holes

### 10.1 Single Hole

```text
hole keyring
  at 100 20
  radius 2.2
end
```

Syntax:

```text
hole <id>
  at <x> <y>
  radius <r>
  [layer <layer_name>]
end
```

Compiler mapping:

```python
doc.add_circle(x, y, radius, layer="cut")
```

Default layer: `cut`.

### 10.2 Mirrored Hole

```text
hole keyring
  mirror
  x_from_center 52
  y 21
  radius 2.2
end
```

Syntax:

```text
hole <id>
  mirror
  x_from_center <distance>
  y <y>
  radius <r>
  [layer <layer_name>]
end
```

Requires global symmetry.

If:

```text
symmetry 75
x_from_center 52
```

then holes are generated at:

```text
x = 75 - 52
x = 75 + 52
```

Example:

```text
hole keyring
  mirror
  x_from_center 52
  y 21
  radius 2.2
end
```

Creates two holes:

```text
23 21
127 21
```

### 10.3 Holes Along Shape Edges

```text
holes
  source panel
  edges all
  margin 4
  spacing 6
  radius 1.2
end
```

Syntax:

```text
holes
  source <shape_id>
  [edges <edge_name_or_index>...]
  [margin <distance>]
  [spacing <distance>]
  [radius <r>]
  [layer <layer_name>]
  [rounded_path]
end
```

The optional `rounded_path` flag makes holes follow the smooth rounded contour of a `RoundedTriangle`.

Compiler mapping:

```python
doc.add_holes(
    shape,
    edges=...,
    spacing=spacing,
    hole_radius=radius,
    inset=margin,
    layer="cut",
)
```

Recommended default layer: `cut`.

## 11. Export

### Simple Export

```text
export lighter_sleeve
```

Should generate:

```text
lighter_sleeve.svg
lighter_sleeve.pdf
lighter_sleeve.png
```

depending on compiler defaults.

### Explicit Export

```text
export svg lighter_sleeve.svg
export pdf lighter_sleeve.pdf
export png lighter_sleeve.png
```

Syntax:

```text
export <format> <filename>
```

Supported formats:

```text
svg
png
pdf
```

PDF export should preserve vector geometry and physical dimensions in millimeters.

## 12. Full Examples

### 12.1 Rectangle

```text
pattern rectangle_panel
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

export rectangle_panel
```

### 12.2 Rounded Rectangle With Three Stitched Edges

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

### 12.3 Simple Panel With Holes

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

### 12.4 Symmetric Lighter Sleeve

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
  angle 0
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
  x_from_center 52
  y 21
  radius 2.2
end

export lighter_sleeve
```

## 13. Suggested Compiler Model

Internally, the parser should convert DSL into a model like:

```python
PatternDocument
  name: str
  width_mm: float
  height_mm: float
  layers: dict[str, LayerStyle]
  symmetry_axis_x: float | None
  shapes: list[ShapeDefinition]
  operations: list[OperationDefinition]
  exports: list[ExportDefinition]
```

Possible shape definitions:

```python
RectangleDefinition
RoundedRectangleDefinition
FreeformPathDefinition
CircleDefinition
```

Possible operations:

```python
AddStitchesOperation
AddHolesOperation
AddSingleHoleOperation
ExportOperation
```

The implementation flow:

```text
Read text
Remove comments and empty lines
Tokenize lines
Parse top-level commands and blocks
Validate references and required fields
Resolve all dimensions as millimeters
Resolve edge aliases
Build geometry
Generate SVG with leathercraft_svg
Export optional PNG/PDF
```

## 14. Validation Rules

The compiler should produce clear errors.

Examples:

Missing document size:

```text
Error: missing required command 'size'
```

Unknown shape reference:

```text
Error: stitches block references unknown source 'panel2'
```

Missing symmetry for mirrored hole:

```text
Error: hole 'keyring' uses mirror but no symmetry axis is defined
```

Invalid edge:

```text
Error: edge 'lower' is invalid for rectangle 'panel'. Use: top, right, bottom, left, all.
```

Invalid numeric value:

```text
Error: radius must be greater than 0
```

Invalid unit suffix:

```text
Error: units are not allowed in numeric values. Use 'size 150 112', not 'size 150mm 112mm'. All dimensions are millimeters.
```

Invalid block:

```text
Error: missing 'end' for block 'rounded_rectangle panel'
```

## 15. Reserved Keywords

Recommended reserved keywords:

```text
pattern
size
layer
symmetry
rectangle
rounded_rectangle
stadium
circle
ellipse
arc
triangle
rounded_triangle
outer
stitches
holes
hole
path
points
source
edges
margin
spacing
length
angle
radius
inner_radius
from_angle
to_angle
radius_tl
radius_tr
radius_br
radius_bl
rx
ry
rounded_path
mirror
at
from
to
p1
p2
p3
x
y
x_from_center
export
end
```

Shape IDs should not use reserved keywords.

## 16. MVP Scope

The current implementation supports:

```text
pattern
size
layer
symmetry
rectangle
rounded_rectangle
stadium
circle
ellipse (rx/ry form and size form)
arc (wedge and ring segment)
triangle (point form and box form)
rounded_triangle (point form and box form)
outer smooth/straight mirrored
stitches from shape edges (with optional rounded_path)
stitches from custom path
holes from shape edges (with optional rounded_path)
single hole
mirrored hole
export
```

Do not implement yet:

```text
variables
expressions
includes
loops
conditionals
text labels
notches
slots
fold lines
complex boolean operations
multiple units
```

This keeps the language easy to implement and still useful for current leathercraft patterns.
