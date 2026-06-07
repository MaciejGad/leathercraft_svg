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
doc.add_shape(rect)
doc.add_holes(rect, edges="all", spacing=5.0, hole_radius=1.0, inset=5.0)

rounded_rect = RoundedRectangle(120, 20, 90, 60, radius=10)
doc.add_shape(rounded_rect)
doc.add_holes(rounded_rect, edges=[0, 2], spacing=8.0, hole_radius=2.0, inset=7.0)

circle = Circle(265, 50, 30)
doc.add_shape(circle)
doc.add_holes(circle, spacing=10.0, hole_radius=2.0, inset=7.0)

triangle = Triangle.from_box(20, 115, 80, 70)
doc.add_shape(triangle)
doc.add_holes(triangle, edges=[0, 1, 2], spacing=8.0, hole_radius=2.0, inset=7.0)

rounded_triangle = RoundedTriangle(
    Point(180, 110),
    Point(245, 185),
    Point(115, 185),
    radius=12,
)
doc.add_shape(rounded_triangle)
doc.add_holes(rounded_triangle, edges="all", spacing=8.0, hole_radius=2.0, inset=7.0)

doc.save("example_shapes.svg")
doc.save_png("example_shapes.png", background_color="white")
print("Wygenerowano: example_shapes.svg")
print("Wygenerowano: example_shapes.png")
