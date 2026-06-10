"""
Symmetric lighter sleeve pattern for leather laser cutting.

This pattern is based on / inspired by the free lighter sleeve template
published by Juchcik:

https://juchcik.pl/userdata/public/assets//etui_na_zapalcznik%C4%99.pdf

The generated SVG is a custom, symmetrical reconstruction intended for
personal leathercraft experimentation.
"""

from leathercraft_svg import (
    Polygon,
    StrokeStyle,
    SvgDocument,
    mirror_polyline,
    offset_polyline,
)

doc = SvgDocument(
    width_mm=150,
    height_mm=112,
    styles={
        "cut":   StrokeStyle("#ff0000", 0.12),
        "stitch": StrokeStyle("#0000ff", 0.35),
        "debug": StrokeStyle("#00aa00", 0.12),
    },
)

center_x = 75
top_y = 8

# Left half of the outer cut line.
# Starts and ends on the mirror axis (x == center_x).
# The right side is generated automatically by Polygon.from_mirror.
left_outline = [
    (center_x,      top_y +  6),
    (center_x - 16, top_y +  3),
    (center_x - 32, top_y +  0),
    (center_x - 47, top_y +  3),
    (center_x - 58, top_y +  3),
    (center_x - 57, top_y + 10),
    (center_x - 56, top_y + 19),
    (center_x - 57, top_y + 28),
    (center_x - 49, top_y + 30),
    (center_x - 39, top_y + 34),
    (center_x - 35, top_y + 43),
    (center_x - 35, top_y + 66),
    (center_x - 36, top_y + 80),
    (center_x - 38, top_y + 89),
    (center_x - 28, top_y + 94),
    (center_x - 14, top_y + 97),
    (center_x,      top_y + 97),
]

shape = Polygon.from_mirror(left_outline, center_x, smooth=True)
doc.add_shape(shape, layer="cut")

# Symmetric keyring attachment holes.
doc.add_circle(center_x - 45, top_y + 15, 2.2, layer="cut")
doc.add_circle(center_x + 45, top_y + 15, 2.2, layer="cut")

# Stitch lines — offset inward from the outer edge, mirrored to both sides.
# The top decorative curve is intentionally excluded from stitching.
left_outer_edge = [
    (43,            10),
    (center_x - 47, top_y +  3),
    (center_x - 58, top_y +  3),
    (center_x - 57, top_y + 10),
    (center_x - 56, top_y + 19),
    (center_x - 57, top_y + 28),
    (center_x - 49, top_y + 30),
    (center_x - 39, top_y + 34),
    (center_x - 35, top_y + 43),
    (center_x - 35, top_y + 66),
    (center_x - 36, top_y + 80),
    (center_x - 38, top_y + 89),
    (center_x - 28, top_y + 94),
    (center_x - 14, top_y + 97),
    (center_x,      top_y + 97),
]

left_seam  = offset_polyline(left_outer_edge, distance=4.0, side="right")
right_seam = mirror_polyline(left_seam, center_x)

doc.add_stitch_on_polyline(left_seam,  spacing=6, stitch_length=2.4, layer="stitch")
doc.add_stitch_on_polyline(right_seam, spacing=6, stitch_length=2.4, layer="stitch")

# Optional debug view of the computed stitch guide path:
# doc.add_path(straight_path_from_points(left_seam),  layer="debug")
# doc.add_path(straight_path_from_points(right_seam), layer="debug")

doc.save("lighter_sleeve.svg")
doc.save_png("lighter_sleeve.png", background_color="white")
