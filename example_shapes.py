from laser_svg import (
    Circle,
    Point,
    Rectangle,
    RoundedRectangle,
    RoundedTriangle,
    SvgDocument,
    Triangle,
)

doc = SvgDocument(width_mm=320, height_mm=240)

rect = Rectangle(20, 20, 80, 50)
doc.add_shape(rect, layer="cut")
doc.add_holes(rect, edges="all", spacing=10.0, hole_radius=1.0, inset=5.0, layer="stitch")

rounded_rect = RoundedRectangle(120, 20, 90, 60, radius=10)
doc.add_shape(rounded_rect, layer="cut")
doc.add_stitch_pattern(
    rounded_rect,
    edges=[0, 2],
    spacing=8.0,
    stitch_length=3.5,
    stitch_angle_deg=45,
    inset=7.0,
    layer="stitch",
    stitch_thickness=0.8,
)

circle = Circle(265, 50, 30)
doc.add_shape(circle, layer="stitch")
doc.add_holes(circle, spacing=10.0, hole_radius=2.0, inset=7.0, layer="cut")

triangle = Triangle.from_box(20, 115, 80, 70)
doc.add_shape(triangle, layer="guide")
doc.add_holes(triangle, edges=[0, 1, 2], spacing=8.0, hole_radius=2.0, inset=7.0, layer="stitch")

rounded_triangle = RoundedTriangle(
    Point(180, 110),
    Point(245, 185),
    Point(115, 185),
    radius=12,
)
doc.add_shape(rounded_triangle, layer="crease")
doc.add_stitch_pattern(
    rounded_triangle,
    edges="all",
    spacing=8.0,
    stitch_length=3.5,
    stitch_angle_deg=0,
    inset=5.0,
    layer="stitch",
    stitch_thickness=0.8,
    placement="dense",
    rounded_path=True,
)
doc.add_line(10, 10, 310, 10, layer="guide")

doc.save("example_shapes.svg")
doc.save_png("example_shapes.png", background_color="white")
print("Generated: example_shapes.svg")
print("Generated: example_shapes.png")
