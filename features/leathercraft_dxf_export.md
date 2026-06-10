# DXF Export — Development Specification

This document describes how DXF export should work in `leathercraft_svg`.

The goal is to allow users to export leathercraft patterns not only as SVG/PNG/PDF, but also as DXF files suitable for CAD, laser cutting, CNC workflows, and interoperability with tools such as AutoCAD, LibreCAD, LightBurn, Inkscape, Fusion, and other CAM/CAD software.

This file is intended to guide later implementation.

---

## 1. Reference notes checked before writing this spec

The design below is based on standard DXF behavior and `ezdxf` documentation.

Important DXF facts used by this specification:

- ASCII DXF is built from group-code/value pairs.
- Graphical drawing objects are stored in the `ENTITIES` section.
- Basic DXF entities useful for this library include `LINE`, `CIRCLE`, `ARC`, `POLYLINE`, and `LWPOLYLINE`.
- `LWPOLYLINE` is a compact modern 2D polyline entity and is preferable for many 2D outlines when the target DXF version supports it.
- `LWPOLYLINE` can represent arc segments using bulge values.
- A bulge value belongs to the vertex at the start of the arc segment and applies to the segment ending at the next vertex.
- Bulge is defined as `tan(included_arc_angle / 4)`.
- A bulge value of `1` represents a semicircle.
- For compatibility, simple entities such as `LINE`, `CIRCLE`, `ARC`, and `LWPOLYLINE` should be preferred over advanced entities unless needed.
- `ezdxf` is a suitable Python library for generating DXF files and avoids manual low-level DXF serialization.

Useful references for implementation:

- Autodesk DXF Reference / AutoCAD DXF documentation.
- Autodesk documentation for common entity group codes and the `ENTITIES` section.
- `ezdxf` documentation for `LWPOLYLINE`, layers, units, entities, and bulge values.

---

## 2. Goals

Add a DXF export path to the library.

Recommended public API:

```python
doc.save_dxf("pattern.dxf")
```

Optional extended API:

```python
doc.save_dxf(
    "pattern.dxf",
    version="R2010",
    units="mm",
    preserve_curves=True,
    approximate_curves=False,
    curve_tolerance=0.1,
)
```

The DXF export should preserve:

- document dimensions
- millimeter units
- layers
- cut outlines
- stitch holes
- laser stitch marks
- crease/guide lines
- circles
- arcs where possible
- polylines for polygonal shapes

---

## 3. Why DXF export is useful

SVG is excellent for web preview and many laser tools, but DXF is more common in CAD/CAM workflows.

DXF export would make the library more useful for:

- laser cutter software
- CNC workflows
- CAD editing
- sharing patterns with workshops
- importing generated patterns into mechanical design tools
- using patterns in tools that do not handle SVG well

---

## 4. DXF background

DXF is a text-based drawing exchange format. In ASCII DXF, data is stored as repeated group-code/value pairs. A group code appears on one line and its value appears on the following line.

A simplified DXF structure looks like this:

```text
0
SECTION
2
HEADER
...
0
ENDSEC
0
SECTION
2
TABLES
...
0
ENDSEC
0
SECTION
2
ENTITIES
...
0
ENDSEC
0
EOF
```

For this project, the most important section is:

```text
ENTITIES
```

That is where graphical objects such as lines, circles, arcs, and polylines are stored.

The recommended implementation should not manually write DXF unless necessary. Use `ezdxf` if possible. It handles DXF structure, headers, tables, layers, entity serialization, and version compatibility.

Recommended dependency:

```text
ezdxf
```

---

## 5. Recommended DXF version

Recommended default:

```python
version="R2010"
```

Reason:

- supports `LWPOLYLINE`
- widely supported
- works well with modern CAD/CAM tools
- easier to write than very old DXF versions

Possible fallback/export option:

```python
version="R12"
```

R12 can be useful for compatibility with older software, but it has fewer modern entity conveniences. If R12 is supported later, it may need old-style `POLYLINE` instead of `LWPOLYLINE`.

Recommended first implementation:

```text
R2010 only
```

Later:

```text
R12 compatibility mode
```

---

## 6. Units

The library uses millimeters. DXF export must preserve that.

Recommended behavior:

```python
doc.save_dxf("pattern.dxf", units="mm")
```

The DXF should set drawing units to millimeters.

When using `ezdxf`, set:

```python
dxf_doc.units = ezdxf.units.MM
```

Also consider setting `$INSUNITS` to millimeters.

In DXF, the common `$INSUNITS` value for millimeters is:

```text
4
```

Recommended implementation:

```python
dxf_doc.units = ezdxf.units.MM
dxf_doc.header["$INSUNITS"] = 4
```

The coordinate values should be written directly in millimeters. No scaling should be applied by default.

---

## 7. Coordinate system

SVG and the current library use this coordinate convention:

```text
X increases to the right.
Y increases downward.
```

Typical CAD/DXF coordinates use:

```text
X increases to the right.
Y increases upward.
```

This creates an important design decision.

### 7.1 Recommended default: keep coordinates as-is

Recommended first implementation:

```python
flip_y=False
```

Meaning:

```text
DXF coordinates match the current SVG/library coordinates.
```

So a point at:

```python
Point(10, 20)
```

is exported to DXF as:

```text
x = 10
y = 20
```

This makes geometry debugging easier and keeps coordinates consistent across SVG and DXF.

### 7.2 Optional CAD-style Y flip

Optional future parameter:

```python
doc.save_dxf("pattern.dxf", flip_y=True)
```

If enabled:

```python
dxf_y = document_height - svg_y
```

This makes the DXF visually match CAD's upward Y-axis while keeping the drawing inside the document bounds.

Recommended first version:

```text
Do not flip Y by default.
Add `flip_y` only if needed.
```

---

## 8. Layers

The current library uses default layers such as:

```text
cut
stitch
crease
guide
```

DXF export should preserve those layers.

Recommended DXF layers:

| Library layer | DXF layer | Suggested color |
|---|---|---|
| `cut` | `cut` | red |
| `stitch` | `stitch` | blue |
| `crease` | `crease` | green |
| `guide` | `guide` | gray |

DXF color can use AutoCAD Color Index values:

| Color | ACI |
|---|---:|
| red | 1 |
| yellow | 2 |
| green | 3 |
| cyan | 4 |
| blue | 5 |
| magenta | 6 |
| white/black | 7 |
| gray | 8 |

Recommended mapping:

```python
DXF_LAYER_COLORS = {
    "cut": 1,
    "stitch": 5,
    "crease": 3,
    "guide": 8,
}
```

Custom layers should also be exported. If no known color is available, use color `7`.

---

## 9. Entity mapping

The DXF export should convert internal geometry into appropriate DXF entities.

Recommended mappings:

| Library geometry | DXF entity |
|---|---|
| straight line | `LINE` |
| circle | `CIRCLE` |
| circular arc | `ARC` |
| polygon / rectangle | `LWPOLYLINE` with `close=True` |
| rounded rectangle | `LWPOLYLINE` with bulge values, or lines + arcs |
| stadium | `LWPOLYLINE` with bulge values, or lines + arcs |
| ellipse | `ELLIPSE` or approximated polyline |
| smooth polygon | approximated `LWPOLYLINE` |
| stitch laser segment | `LINE` |
| stitch hole | `CIRCLE` |

Recommended first implementation:

```text
Use simple DXF entities:
- LINE
- CIRCLE
- ARC
- LWPOLYLINE
```

Optional later:

```text
- ELLIPSE
- SPLINE
```

For maximum compatibility with laser software, it is often safer to approximate complex curves as polylines than to use advanced entities such as SPLINE.

---

## 10. Curves and arcs

### 10.1 Preserve true circles

A library `Circle` should export as DXF `CIRCLE`.

Example:

```python
shape = Circle(50, 50, 30)
doc.add_shape(shape)
doc.save_dxf("circle.dxf")
```

Expected DXF entity:

```text
CIRCLE on layer cut
center = (50, 50)
radius = 30
```

### 10.2 Preserve stitch holes as circles

Stitch holes generated by `add_holes` should export as many `CIRCLE` entities, not polygon approximations.

This preserves precision and keeps files smaller.

### 10.3 Preserve circular arcs where possible

A library `Arc` shape should export using `ARC` entities where possible.

For annular ring segments, use:

- outer `ARC`
- inner `ARC`
- connecting `LINE` entities

or use a closed `LWPOLYLINE` with bulge values.

Recommended first version:

```text
Use LINE + ARC entities for Arc shapes.
```

### 10.4 Rounded rectangles and stadiums

Rounded rectangles and stadiums can be exported in two ways.

Option A:

```text
Use LWPOLYLINE with bulge values.
```

Option B:

```text
Use separate LINE and ARC entities.
```

Recommended first implementation:

```text
Use separate LINE and ARC entities if easier and more reliable.
```

Recommended later improvement:

```text
Use closed LWPOLYLINE with bulge values.
```

---

## 11. LWPOLYLINE and bulge values

`LWPOLYLINE` is useful because it can represent both straight and arc segments in one entity.

Each vertex can include a bulge value. The bulge value applies to the segment from that vertex to the next vertex.

Bulge formula:

```text
bulge = tan(theta / 4)
```

Where:

```text
theta = included arc angle in radians
```

Examples:

```text
90 degree arc:  bulge = tan(90° / 4)  = tan(22.5°)  ≈ 0.41421356
180 degree arc: bulge = tan(180° / 4) = tan(45°)    = 1.0
```

The sign of the bulge controls arc direction.

Important implementation note:

```text
A bulge belongs to the start vertex of the arc segment.
```

For a rounded rectangle with quarter-circle corners, each curved corner can be represented by a bulge of approximately:

```python
0.41421356237
```

However, sign and Y-axis orientation must be tested carefully.

Because SVG coordinates use Y-down and CAD coordinates usually use Y-up, bulge signs may need to be inverted if `flip_y=True`.

Recommended first implementation:

```text
Prefer LINE + ARC entities for rounded shapes.
Use LWPOLYLINE with bulge values only after visual tests pass.
```

---

## 12. Shape export strategy

### 12.1 Rectangle

Export as closed `LWPOLYLINE`.

```python
Rectangle(x, y, width, height)
```

DXF vertices:

```text
(x, y)
(x + width, y)
(x + width, y + height)
(x, y + height)
closed = true
```

---

### 12.2 RoundedRectangle

Recommended first version:

Export as individual `LINE` and `ARC` entities.

For uniform radius:

```text
top line
top-right arc
right line
bottom-right arc
bottom line
bottom-left arc
left line
top-left arc
```

For per-corner radii, use the effective clamped radii from `corner_radii()`.

If a corner radius is `0`, use a sharp corner.

---

### 12.3 Stadium

Export as:

- two straight lines
- two semicircular arcs

For horizontal stadium:

```text
left/right semicircle caps
top and bottom straight lines
```

For vertical stadium:

```text
top/bottom semicircle caps
left and right straight lines
```

---

### 12.4 Circle

Export as `CIRCLE`.

---

### 12.5 Ellipse

Possible implementations:

Option A:

```text
Export as DXF ELLIPSE.
```

Option B:

```text
Approximate as LWPOLYLINE.
```

Recommended first implementation:

```text
Approximate as LWPOLYLINE unless ELLIPSE support is tested well.
```

Reason: many laser/CAM tools handle polylines more predictably.

Recommended default tolerance:

```python
curve_tolerance=0.1
```

or segment count:

```python
ellipse_segments=96
```

---

### 12.6 Arc

For simple sector:

```python
Arc(cx, cy, radius, start_angle, end_angle, inner_radius=0)
```

Export as:

- outer `ARC`
- two radial `LINE` entities
- if inner_radius is zero: optional line to center if represented as a closed sector
- if inner_radius > 0: inner `ARC` and two connecting lines

For leathercraft cutting, the full closed outline matters. Therefore an `Arc` shape should export all boundary parts, not only the curved arc.

---

### 12.7 Triangle

Export as closed `LWPOLYLINE`.

---

### 12.8 RoundedTriangle

Recommended first version:

```text
Approximate as LWPOLYLINE.
```

Later improvement:

```text
Use lines + arcs or LWPOLYLINE bulges if exact rounded-corner construction is available.
```

---

### 12.9 Polygon

If `smooth=False`:

```text
Export as closed LWPOLYLINE.
```

If `smooth=True`:

```text
Approximate the smoothed Bézier contour as LWPOLYLINE.
```

Recommended tolerance:

```python
curve_tolerance=0.1
```

---

### 12.10 Open polyline stitches

Laser stitch segments from `add_stitch_on_polyline` should export as `LINE` entities.

The helper path itself should not be exported unless it was explicitly added as a guide.

---

## 13. SVG path export issue

The current `SvgDocument` likely stores rendered elements as SVG primitives or SVG path strings.

DXF export should not try to parse arbitrary SVG path strings if avoidable.

Recommended architectural change:

```text
Store drawing operations internally as structured geometry objects.
```

For example:

```python
@dataclass
class DrawLine:
    x1: float
    y1: float
    x2: float
    y2: float
    layer: str

@dataclass
class DrawCircle:
    cx: float
    cy: float
    radius: float
    layer: str

@dataclass
class DrawPolyline:
    points: list[tuple[float, float]]
    closed: bool
    layer: str

@dataclass
class DrawArc:
    cx: float
    cy: float
    radius: float
    start_angle: float
    end_angle: float
    layer: str
```

Then SVG and DXF exporters can both render from the same structured drawing model.

If this is too big for the first implementation, add a parallel DXF export path from the original shape objects and stitch/hole operations.

Avoid this if possible:

```text
SVG path string -> parse path -> convert to DXF
```

That route is fragile and harder to test.

---

## 14. Proposed implementation using ezdxf

### 14.1 Dependency

Add optional dependency:

```text
ezdxf
```

If the user calls `save_dxf()` without `ezdxf` installed, raise a clear error:

```text
save_dxf requires the optional dependency 'ezdxf'. Install it with: pip install ezdxf
```

If the project supports extras:

```text
pip install leathercraft_svg[dxf]
```

---

### 14.2 Basic implementation outline

```python
def save_dxf(
    self,
    path: str,
    *,
    version: str = "R2010",
    units: str = "mm",
    preserve_curves: bool = True,
    curve_tolerance: float = 0.1,
    flip_y: bool = False,
) -> None:
    import ezdxf

    if version != "R2010":
        raise ValueError("unsupported DXF version")

    dxf_doc = ezdxf.new("R2010")
    dxf_doc.units = ezdxf.units.MM
    dxf_doc.header["$INSUNITS"] = 4

    _create_layers(dxf_doc, self.styles)

    msp = dxf_doc.modelspace()

    for entity in self._draw_entities:
        _add_entity_to_dxf(
            msp,
            entity,
            document_height=self.height_mm,
            flip_y=flip_y,
            curve_tolerance=curve_tolerance,
        )

    dxf_doc.saveas(path)
```

---

### 14.3 Layer creation

```python
def _create_layers(dxf_doc, styles):
    for name, style in styles.items():
        color = _style_to_aci_color(style)
        if name not in dxf_doc.layers:
            dxf_doc.layers.add(name, color=color)
```

---

### 14.4 Adding entities

Examples with `ezdxf`:

```python
msp.add_line((x1, y1), (x2, y2), dxfattribs={"layer": layer})
```

```python
msp.add_circle((cx, cy), radius, dxfattribs={"layer": layer})
```

```python
msp.add_arc((cx, cy), radius, start_angle, end_angle, dxfattribs={"layer": layer})
```

```python
msp.add_lwpolyline(points, close=True, dxfattribs={"layer": layer})
```

For LWPOLYLINE with bulge values, points may need to include extra tuple data depending on the chosen ezdxf format.

---

## 15. Manual ASCII DXF fallback

Manual writing is not recommended for the first implementation, but this section describes the minimum viable structure if needed.

Minimal ASCII DXF:

```text
0
SECTION
2
HEADER
9
$INSUNITS
70
4
0
ENDSEC
0
SECTION
2
TABLES
0
ENDSEC
0
SECTION
2
ENTITIES
0
LINE
8
cut
10
10
20
10
11
100
21
10
0
ENDSEC
0
EOF
```

Example `LINE` entity group codes:

```text
0    entity type: LINE
8    layer name
10   start x
20   start y
11   end x
21   end y
```

Example `CIRCLE` entity group codes:

```text
0    entity type: CIRCLE
8    layer name
10   center x
20   center y
40   radius
```

Example `ARC` entity group codes:

```text
0    entity type: ARC
8    layer name
10   center x
20   center y
40   radius
50   start angle
51   end angle
```

Manual DXF export should only be used if avoiding dependencies is more important than robust DXF generation.

---

## 16. DSL export changes

Current DSL export supports:

```text
export <name>
export svg <filename>
export png <filename>
export pdf <filename>
```

Add:

```text
export dxf <filename>
```

Example:

```text
pattern card_panel
size 120 80

rectangle panel
  at 10 10
  size 100 60
end

holes
  source panel
  spacing 6
  radius 1.2
end

export dxf card_panel.dxf
```

Optional multi-export behavior:

```text
export card_panel
```

could continue to write SVG and PNG only, or could be expanded later.

Recommended first version:

```text
Do not change existing default export behavior.
Only write DXF when explicitly requested with `export dxf`.
```

Optional later:

```text
export all card_panel
```

could write SVG, PNG, PDF, and DXF.

---

## 17. Python examples

### 17.1 Basic rectangle DXF

```python
from leathercraft_svg import Rectangle, SvgDocument

doc = SvgDocument(120, 80)
panel = Rectangle(10, 10, 100, 60)

doc.add_shape(panel, layer="cut")
doc.save_dxf("panel.dxf")
```

Expected DXF:

```text
A closed polyline on layer cut.
Units are millimeters.
Coordinates match the SVG coordinate values by default.
```

---

### 17.2 Panel with stitch holes

```python
from leathercraft_svg import Rectangle, SvgDocument

doc = SvgDocument(120, 80)
panel = Rectangle(10, 10, 100, 60)

doc.add_shape(panel, layer="cut")
doc.add_holes(
    panel,
    spacing=6,
    hole_radius=1.2,
    inset=4,
    layer="stitch",
)

doc.save_dxf("panel_with_holes.dxf")
```

Expected DXF:

```text
Panel outline: LWPOLYLINE on layer cut.
Each stitch hole: CIRCLE on layer stitch.
```

---

### 17.3 Rounded rectangle

```python
from leathercraft_svg import RoundedRectangle, SvgDocument

doc = SvgDocument(140, 90)
pocket = RoundedRectangle(20, 15, 100, 60, radius=10)

doc.add_shape(pocket, layer="cut")
doc.add_stitch_pattern(
    pocket,
    edges=[1, 2, 3],
    spacing=5,
    stitch_length=3,
    inset=5,
    layer="stitch",
)

doc.save_dxf("rounded_pocket.dxf")
```

Expected DXF:

```text
Rounded rectangle outline on layer cut.
Laser stitch marks as LINE entities on layer stitch.
Rounded corners are exported as ARC entities or approximated polylines.
```

---

## 18. DSL examples

### 18.1 DXF export only

```text
pattern card_panel_dxf
size 120 80

rectangle panel
  at 10 10
  size 100 60
end

holes
  source panel
  spacing 6
  radius 1.2
  layer stitch
end

export dxf card_panel.dxf
```

---

### 18.2 SVG and DXF export

```text
pattern card_panel_multi
size 120 80

rectangle panel
  at 10 10
  size 100 60
end

export svg card_panel.svg
export dxf card_panel.dxf
```

---

## 19. Validation rules

### 19.1 Missing dependency

If `ezdxf` is not installed:

```text
save_dxf requires the optional dependency 'ezdxf'. Install it with: pip install ezdxf
```

---

### 19.2 Unsupported version

Input:

```python
doc.save_dxf("pattern.dxf", version="R9")
```

Error:

```text
unsupported DXF version 'R9'. Use: R2010
```

If R12 is later supported:

```text
unsupported DXF version 'R9'. Use: R12, R2010
```

---

### 19.3 Unsupported units

Input:

```python
doc.save_dxf("pattern.dxf", units="inch")
```

Recommended first version:

```text
unsupported DXF units 'inch'. Use: mm
```

Later, inches can be supported with conversion.

---

### 19.4 Invalid curve tolerance

Input:

```python
doc.save_dxf("pattern.dxf", curve_tolerance=0)
```

Error:

```text
curve_tolerance must be greater than 0
```

---

### 19.5 Unsupported arbitrary raw path

If `doc.add_path(...)` has been used with a raw SVG `d` string and the implementation cannot convert it:

Recommended behavior:

```text
raise error
```

Error:

```text
DXF export does not support raw SVG paths yet. Use structured shapes or add a path-to-geometry converter.
```

Alternative behavior:

```text
skip unsupported path with warning
```

Recommended first version: fail loudly to avoid silently producing incomplete cutting files.

---

## 20. Testing strategy

DXF export should be tested with both automated tests and visual/manual import checks.

### 20.1 Automated structural tests

Use `ezdxf` to read the generated file and inspect entities.

Test:

```python
dxf = ezdxf.readfile("panel.dxf")
msp = dxf.modelspace()
entities = list(msp)
```

Verify:

- correct entity count
- correct entity types
- correct layers
- correct coordinates
- correct radii
- `$INSUNITS == 4`
- no unsupported entities are produced
- file can be opened by `ezdxf`

---

### 20.2 Rectangle test

Input:

```python
doc = SvgDocument(120, 80)
panel = Rectangle(10, 10, 100, 60)
doc.add_shape(panel)
doc.save_dxf("panel.dxf")
```

Expected:

```text
one closed LWPOLYLINE
layer = cut
vertices:
(10, 10)
(110, 10)
(110, 70)
(10, 70)
```

---

### 20.3 Circle test

Input:

```python
shape = Circle(50, 50, 20)
doc.add_shape(shape)
```

Expected:

```text
one CIRCLE
center = (50, 50)
radius = 20
layer = cut
```

---

### 20.4 Stitch holes test

Input:

```python
doc.add_holes(panel, spacing=10, hole_radius=1.2, layer="stitch")
```

Expected:

```text
multiple CIRCLE entities
all on layer stitch
all radius = 1.2
```

---

### 20.5 Laser stitch pattern test

Input:

```python
doc.add_stitch_pattern(panel, spacing=10, stitch_length=3, layer="stitch")
```

Expected:

```text
multiple LINE entities
all on layer stitch
```

---

### 20.6 Rounded rectangle test

Expected:

```text
DXF contains either:
- LINE and ARC entities, or
- one closed LWPOLYLINE with bulge values
```

Also verify:

```text
No missing corners.
No open gaps.
No inverted arcs.
```

---

### 20.7 DSL export test

Input:

```text
pattern panel
size 120 80

rectangle panel
  at 10 10
  size 100 60
end

export dxf panel.dxf
```

Expected:

```text
panel.dxf is created.
DXF contains the expected geometry.
```

---

### 20.8 Manual compatibility test

Open generated DXF files in at least:

- LibreCAD
- Inkscape
- LightBurn or another laser/CAM tool if available

Check:

- size is correct in millimeters
- layers are preserved
- circles import as circles
- curves do not appear inverted
- no duplicate seam points
- no missing entities
- exported pattern is suitable for laser cutting

---

## 21. Recommended implementation order

1. Add optional `ezdxf` dependency support.
2. Add `SvgDocument.save_dxf(...)`.
3. Export basic structured primitives: line, circle, closed polyline.
4. Ensure DXF units are millimeters.
5. Export layers with ACI colors.
6. Add automated tests that read the DXF back with `ezdxf`.
7. Add support for stitch holes as circles.
8. Add support for laser stitch segments as lines.
9. Add support for rectangles and triangles as closed polylines.
10. Add support for rounded rectangles and stadiums using lines + arcs or approximated polylines.
11. Add support for circles as `CIRCLE`.
12. Add support for ellipses and smooth polygons as approximated polylines.
13. Add DSL `export dxf <filename>`.
14. Add example `.lcraft` files.
15. Test import in CAD/CAM tools.
16. Update documentation and AI agent reference.

---

## 22. Open design questions

### 22.1 Should raw SVG paths be supported?

Recommended first version:

```text
No.
```

Reason: parsing arbitrary SVG paths correctly is a separate feature.

Future option:

```text
Use svgpathtools or a custom path parser.
```

---

### 22.2 Should DXF use exact arcs or approximated curves?

Recommended:

```text
Use exact entities for simple circles and arcs.
Use approximation for complex or smooth shapes.
```

This balances precision and compatibility.

---

### 22.3 Should default export include DXF?

Recommended first version:

```text
No.
```

Do not change the current default `export <name>` behavior. Add explicit DXF export.

---

### 22.4 Should DXF files include page/document border?

Recommended default:

```text
No.
```

A page border can interfere with laser cutting. If needed, it should be explicit:

```python
doc.add_page_border(layer="guide")
```

---

## 23. Final recommendation

Implement DXF export as an optional export backend using `ezdxf`.

The first version should prioritize correctness and compatibility over advanced DXF features.

Recommended scope:

- `save_dxf(path)`
- R2010 DXF
- millimeter units
- layer preservation
- LINE, CIRCLE, ARC, LWPOLYLINE
- stitch holes as circles
- laser stitch marks as lines
- rectangles/triangles/polygons as closed polylines
- rounded shapes as line+arc entities or safe approximated polylines
- DSL support: `export dxf filename.dxf`
- automated tests that read back the generated DXF

Avoid arbitrary SVG path conversion in the first version unless the internal document model already stores enough structured geometry.

The most important requirement is that generated DXF files import at the correct real-world size in millimeters and preserve all cut/stitch/guide layers reliably.
