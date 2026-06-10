# Missing Shapes — Gap Analysis

Comparison of SVG primitive shapes against what is currently implemented
in `leathercraft_svg.py` (Python library) and `leathercraft_dsl.py` (DSL).

---

## Coverage summary

| SVG element | Library class | DSL keyword | Status |
|---|---|---|---|
| `<rect>` | `Rectangle` | `rectangle` | ✅ full |
| `<rect rx ry>` (uniform radius) | `RoundedRectangle` | `rounded_rectangle` | ✅ full |
| `<rect rx ry>` (per-corner radii) | — | — | ❌ missing |
| `<circle>` | `Circle` | `circle` | ✅ full |
| `<ellipse>` | — | — | ❌ missing |
| `<line>` | `add_line()` (document-level, not a Shape) | — | ⚠️ partial |
| `<polyline>` (open path) | utilities only (`offset_polyline`) | `path` inside `stitches` only | ⚠️ partial |
| `<polygon>` | `Polygon` | `polygon` (via `outer` block) | ✅ full |
| `<path>` (raw `d` string) | `add_path(d)` (document-level, not a Shape) | — | ⚠️ partial |
| Arc / circular sector | — | — | ❌ missing |
| Stadium / oblong | — | — | ❌ missing |
| Regular n-gon | — | — | ❌ missing |
| Cubic Bézier path | — | — | ❌ missing |

---

## Missing shapes — detailed descriptions

### 1. Ellipse

**SVG primitive:** `<ellipse cx="…" cy="…" rx="…" ry="…"/>`

An oval defined by two independent radii: `rx` (horizontal) and `ry` (vertical).
When `rx == ry` it is identical to a circle.

**Leathercraft use cases:**
- Oval coin purse / pouch fronts
- Oval key-fob blanks
- Watch-pocket openings
- Decorative oval appliqués

**Implementation notes:**
- `path_d` → `M cx-rx cy  A rx ry 0 1 0 cx+rx cy  A rx ry 0 1 0 cx-rx cy Z`
- `hole_points` / `stitch_segments` — approximate with N-step parametric points
  `(cx + rx·cos θ, cy + ry·sin θ)` for `θ ∈ [0, 2π)`, then apply `inset` by
  scaling both radii inward: `rx_inner = rx − inset`, `ry_inner = ry − inset`
- DSL syntax proposal:
  ```
  ellipse <id>
    at <cx> <cy>      # centre point
    rx <mm>           # horizontal radius
    ry <mm>           # vertical radius
    [layer <name>]
  end
  ```
  (or `size <w> <h>` as shorthand where `rx = w/2`, `ry = h/2`)

---

### 2. Per-corner rounded rectangle

**SVG primitive:** `<rect … rx="…" ry="…"/>` — SVG only supports one `rx` and one `ry`
value for all corners, but a common extension (used in CSS, Inkscape, Figma) is to
specify each corner independently.

Currently `RoundedRectangle` applies a **single uniform radius** to all four corners.

**Leathercraft use cases:**
- Card holders where the top corners are fully rounded (large radius) but the
  bottom corners are sharp — looks professional and avoids snagging
- Phone cases with asymmetric corner treatment
- Belt loops with one rounded and one straight end

**Implementation notes:**
- Extend `RoundedRectangle` with `radius_tl`, `radius_tr`, `radius_br`, `radius_bl`
  (top-left / top-right / bottom-right / bottom-left), defaulting to the current
  uniform `radius` for backwards compatibility.
- DSL syntax proposal:
  ```
  rounded_rectangle <id>
    at <x> <y>
    size <w> <h>
    radius <uniform>                          # existing — all corners equal
    # --- or per-corner: ---
    radius_tl <mm>  radius_tr <mm>
    radius_br <mm>  radius_bl <mm>
    [layer <name>]
  end
  ```

---

### 3. Arc / circular sector

**SVG primitive:** `<path d="M … A rx ry … Z"/>` (no dedicated element)

A shape that is a filled slice of a circle (pie/wedge), or a ring segment (annulus slice).

**Leathercraft use cases:**
- Curved strap ends ("English point" style)
- Decorative fan cutouts on flap closures
- Gusset inserts that follow a curved bag body
- Zipper pull guards with a swept arc

**Variants worth supporting:**
- **Sector** — filled wedge from centre: `(cx, cy)` + `radius` + `start_angle` + `end_angle`
- **Arc segment** — ring slice: sector with an inner radius cut out
  (`inner_radius`, `outer_radius`, `start_angle`, `end_angle`)
- **Circular cap** — a rectangle whose one short end is replaced by a semicircle
  (this is the "stadium" shape, described separately below)

**Implementation notes:**
- `path_d` uses SVG `A` (arc) commands.
- `hole_points` — parametric points along the outer arc + straight edges.
- DSL syntax proposal:
  ```
  arc <id>
    at <cx> <cy>        # centre
    radius <mm>         # outer radius
    [inner_radius <mm>] # if set: produces a ring segment instead of a wedge
    from_angle <deg>    # start angle (0 = right / 3 o'clock, clockwise)
    to_angle   <deg>    # end angle
    [layer <name>]
  end
  ```

---

### 4. Stadium / oblong (capsule)

**SVG primitive:** expressed as a `<path>` — two parallel lines capped by semicircles.
Also called a "discorectangle" or "capsule".

A `RoundedRectangle` where `radius = min(width, height) / 2` is a special case of this,
but an explicit `Stadium` shape makes the intent clear and avoids the constraint that
radius must be exactly half the short side.

**Leathercraft use cases:**
- Key-fob blanks (by far the most common shape)
- Luggage-tag blanks
- Strap blanks with rounded ends
- Watch straps (the end that goes through the buckle)
- Cable-pass-through holes in bag bases

**Implementation notes:**
- Parameterise by `width`, `height` and `orientation` (`horizontal` / `vertical`).
- `path_d` — two straight edges + two 180° arcs.
- `hole_points` / `stitch_segments` — the two arcs need proportionally more points
  than the straight edges for even stitch spacing; use arc-length parameterisation.
- DSL syntax proposal:
  ```
  stadium <id>
    at  <x> <y>          # top-left of bounding box
    size <w> <h>
    [orientation horizontal|vertical]   # which axis the semicircles cap (default: auto from w vs h)
    [layer <name>]
  end
  ```

---

### 5. Regular n-gon

**SVG primitive:** expressed as a `<polygon>` with computed vertex coordinates.

A regular polygon with N equal sides, defined by a centre point and circumscribed radius.

**Leathercraft use cases:**
- Decorative pendants and charms (hexagon, octagon)
- Structural panels for box-style bags (hexagonal panels)
- Snap or rivet guides placed in a regular pattern
- Coaster blanks

**Implementation notes:**
- Vertices: `(cx + r·cos(2π·k/N + offset), cy + r·sin(2π·k/N + offset))` for `k = 0…N-1`
- `offset` defaults to `−π/2` so the first vertex is at the top.
- Could be implemented as a factory method `Polygon.regular(n, cx, cy, radius)` or as
  a dedicated `RegularPolygon` subclass of `Polygon`.
- DSL syntax proposal:
  ```
  regular_polygon <id>
    at      <cx> <cy>   # centre
    radius  <mm>        # circumscribed radius (centre → vertex)
    sides   <n>         # number of sides (3 = equilateral triangle, 6 = hex, …)
    [rotation <deg>]    # rotate the whole polygon (default: first vertex at top)
    [layer <name>]
  end
  ```

---

### 6. Open polyline as a cut/crease shape

**SVG primitive:** `<polyline points="…"/>`

A sequence of connected line segments that is **not** closed — it has distinct start and
end points.  Currently the library exposes `add_path(d)` and utility functions such as
`offset_polyline`, but there is no `Shape` subclass, so open paths cannot participate
in `add_stitch_pattern` / `add_holes`.

**Leathercraft use cases:**
- Decorative crease lines (fold guides that are not closed shapes)
- Stitching along a flap edge that does not return to its start point
- Partial perforations — a row of holes that runs from one edge of the piece to
  another without forming a closed border
- Lacing holes along a free edge

**Implementation notes:**
- `OpenPolyline(points, smooth=False)` — analogous to `Polygon` but the path ends
  with `L` rather than `Z`.
- `hole_points` — evenly spaced points along the path with an optional `inset`
  interpreted as perpendicular offset (via `offset_polyline`).
- `stitch_segments` — stitch segments perpendicular to the path direction.
- DSL syntax proposal:
  ```
  polyline <id>
    [smooth]
    [layer <name>]
    points
      <x1> <y1>
      <x2> <y2>
      …
    end
  end
  ```

---

### 7. Raw path (DSL access to `add_path`)

**SVG primitive:** `<path d="…"/>` (full SVG path grammar)

The library already exposes `SvgDocument.add_path(d, layer)` which accepts a raw SVG
`d` string. However, this is not accessible from the DSL, so users who need cubic
Bézier curves, arc segments, or any path not expressible by the existing shapes must
fall back to Python code.

**Leathercraft use cases:**
- Organic / freehand leather piece outlines (bags, wallets with curved flaps)
- Cubic Bézier curves for smooth decorative edges
- Complex cutouts that combine arcs and lines

**Implementation notes:**
- The simplest DSL form would accept SVG path data verbatim:
  ```
  path_shape <id>
    [layer <name>]
    d
      M 10 10 C 40 5, 50 25, 30 30
      L 10 30 Z
    end
  end
  ```
- Stitching on a raw path requires approximating the path as a polyline first
  (evaluate at fixed parameter steps), which is a non-trivial but well-understood
  algorithm.
- Alternatively, add a `cubic_bezier` flag to the existing `Polygon` shape and
  accept control-point syntax inside the `outer` block.

---

## Priority recommendation

| Priority | Shape | Reason |
|---|---|---|
| 🔴 High | **Stadium / oblong** | Most common blank shape in leathercraft; currently requires a workaround with `RoundedRectangle` using exact radius = half-height |
| 🔴 High | **Ellipse** | Basic SVG primitive; oval shapes are very common |
| 🟡 Medium | **Per-corner rounded rect** | Small change to existing class; high design value |
| 🟡 Medium | **Arc / sector** | Needed for curved strap ends and fan cutouts |
| 🟡 Medium | **Regular n-gon** | Easy to implement as a `Polygon` factory |
| 🟢 Low | **Open polyline** | Niche use; partial support already exists via `path` in stitches |
| 🟢 Low | **Raw path DSL block** | Power-user feature; complex stitching support |
