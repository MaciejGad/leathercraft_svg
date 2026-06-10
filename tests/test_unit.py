"""
Unit tests for leathercraft_svg — geometry, SVG output, and shape API.
No PNG generation; no external dependencies beyond the stdlib.

Run:
    .venv/bin/python -m pytest tests/test_unit.py -v
    # or without pytest:
    .venv/bin/python -m unittest discover -s tests -p test_unit.py
"""

import math
import unittest

from leathercraft_svg import (
    Circle,
    Ellipse,
    Point,
    Polygon,
    Rectangle,
    RoundedRectangle,
    RoundedTriangle,
    Stadium,
    StrokeStyle,
    SvgDocument,
    Triangle,
    _offset_closed_polygon,
    _smooth_path_d,
    _straight_path_d,
    adjust_positions_near_corners,
    adjust_stitch_positions_and_lengths,
    deduplicate_points,
    distance,
    inset_triangle_vertices,
    inward_unit_normal,
    line_intersection,
    mirror_polyline,
    move_towards,
    offset_polyline,
    point_on_edge,
    points_on_closed_polyline,
    positions_on_closed_length,
    positions_on_line,
    positions_on_side_center,
    quadratic_bezier,
    rounded_rectangle_contour,
    rounded_triangle_contour,
    segment_on_edge,
    signed_double_area,
    stitch_segments_on_closed_polyline,
    stitch_segments_on_open_polyline,
)

APPROX = 1e-6


def approx_eq(a: float, b: float) -> bool:
    return abs(a - b) < APPROX


def point_approx_eq(p: Point, x: float, y: float) -> bool:
    return approx_eq(p.x, x) and approx_eq(p.y, y)


# ===========================================================================
# Geometry helpers
# ===========================================================================

class TestDistance(unittest.TestCase):
    def test_horizontal(self):
        self.assertAlmostEqual(distance(Point(0, 0), Point(3, 0)), 3.0)

    def test_vertical(self):
        self.assertAlmostEqual(distance(Point(0, 0), Point(0, 4)), 4.0)

    def test_diagonal(self):
        self.assertAlmostEqual(distance(Point(0, 0), Point(3, 4)), 5.0)

    def test_same_point(self):
        self.assertEqual(distance(Point(5, 7), Point(5, 7)), 0.0)


class TestMoveTowards(unittest.TestCase):
    def test_half_way(self):
        p = move_towards(Point(0, 0), Point(10, 0), 5)
        self.assertTrue(point_approx_eq(p, 5, 0))

    def test_overshoot_clamps(self):
        p = move_towards(Point(0, 0), Point(1, 0), 999)
        self.assertTrue(point_approx_eq(p, 1, 0))

    def test_same_point_returns_a(self):
        p = move_towards(Point(3, 3), Point(3, 3), 5)
        self.assertTrue(point_approx_eq(p, 3, 3))

    def test_diagonal(self):
        p = move_towards(Point(0, 0), Point(3, 4), 5)
        self.assertTrue(point_approx_eq(p, 3, 4))


class TestPointOnEdge(unittest.TestCase):
    def test_midpoint(self):
        p = point_on_edge(Point(0, 0), Point(10, 0), 5)
        self.assertTrue(point_approx_eq(p, 5, 0))

    def test_zero_length_edge(self):
        p = point_on_edge(Point(3, 7), Point(3, 7), 5)
        self.assertTrue(point_approx_eq(p, 3, 7))

    def test_vertical_edge(self):
        p = point_on_edge(Point(0, 0), Point(0, 10), 3)
        self.assertTrue(point_approx_eq(p, 0, 3))


class TestSegmentOnEdge(unittest.TestCase):
    def test_horizontal_0deg(self):
        a, b = segment_on_edge(Point(0, 0), Point(10, 0), 5, 2, 0)
        self.assertTrue(point_approx_eq(a, 4, 0))
        self.assertTrue(point_approx_eq(b, 6, 0))

    def test_zero_length_edge(self):
        a, b = segment_on_edge(Point(2, 2), Point(2, 2), 0, 2, 0)
        self.assertTrue(point_approx_eq(a, 2, 2))
        self.assertTrue(point_approx_eq(b, 2, 2))

    def test_90deg_rotates_perpendicular(self):
        # Edge along x-axis; 90° rotation should make stitch vertical
        a, b = segment_on_edge(Point(0, 0), Point(10, 0), 5, 2, 90)
        self.assertAlmostEqual(a.x, b.x, places=5)
        self.assertAlmostEqual(abs(b.y - a.y), 2, places=5)


class TestQuadraticBezier(unittest.TestCase):
    def test_t0_returns_a(self):
        p = quadratic_bezier(Point(0, 0), Point(5, 10), Point(10, 0), 0)
        self.assertTrue(point_approx_eq(p, 0, 0))

    def test_t1_returns_b(self):
        p = quadratic_bezier(Point(0, 0), Point(5, 10), Point(10, 0), 1)
        self.assertTrue(point_approx_eq(p, 10, 0))

    def test_t05_midpoint(self):
        p = quadratic_bezier(Point(0, 0), Point(5, 10), Point(10, 0), 0.5)
        self.assertAlmostEqual(p.x, 5.0)
        self.assertAlmostEqual(p.y, 5.0)


class TestDeduplicatePoints(unittest.TestCase):
    def test_removes_duplicates(self):
        pts = [Point(1, 2), Point(1, 2), Point(3, 4)]
        result = deduplicate_points(pts)
        self.assertEqual(len(result), 2)

    def test_preserves_order(self):
        pts = [Point(3, 4), Point(1, 2), Point(3, 4)]
        result = deduplicate_points(pts)
        self.assertEqual(result[0], Point(3, 4))
        self.assertEqual(result[1], Point(1, 2))

    def test_rounding_precision(self):
        pts = [Point(1.0001, 2.0001), Point(1.0002, 2.0002)]
        result = deduplicate_points(pts, precision=2)
        self.assertEqual(len(result), 1)


class TestSignedDoubleArea(unittest.TestCase):
    def test_ccw_positive(self):
        area = signed_double_area(Point(0, 0), Point(1, 0), Point(0, 1))
        self.assertGreater(area, 0)

    def test_cw_negative(self):
        area = signed_double_area(Point(0, 0), Point(0, 1), Point(1, 0))
        self.assertLess(area, 0)

    def test_collinear_zero(self):
        area = signed_double_area(Point(0, 0), Point(1, 1), Point(2, 2))
        self.assertAlmostEqual(area, 0)


class TestLineIntersection(unittest.TestCase):
    def test_perpendicular_lines(self):
        p = line_intersection(Point(0, 0), Point(10, 0), Point(5, -5), Point(5, 5))
        self.assertIsNotNone(p)
        self.assertAlmostEqual(p.x, 5)
        self.assertAlmostEqual(p.y, 0)

    def test_parallel_lines_return_none(self):
        p = line_intersection(Point(0, 0), Point(10, 0), Point(0, 1), Point(10, 1))
        self.assertIsNone(p)


class TestInwardUnitNormal(unittest.TestCase):
    def test_ccw_rightward_edge_points_up(self):
        nx, ny = inward_unit_normal(Point(0, 0), Point(1, 0), ccw=True)
        self.assertAlmostEqual(nx, 0)
        self.assertAlmostEqual(ny, 1)

    def test_cw_rightward_edge_points_down(self):
        nx, ny = inward_unit_normal(Point(0, 0), Point(1, 0), ccw=False)
        self.assertAlmostEqual(nx, 0)
        self.assertAlmostEqual(ny, -1)

    def test_zero_length_returns_zero(self):
        nx, ny = inward_unit_normal(Point(3, 3), Point(3, 3), ccw=True)
        self.assertEqual(nx, 0.0)
        self.assertEqual(ny, 0.0)


# ===========================================================================
# Position helpers
# ===========================================================================

class TestPositionsOnLine(unittest.TestCase):
    def test_zero_length(self):
        self.assertEqual(positions_on_line(0, 5, False), [])

    def test_negative_length(self):
        self.assertEqual(positions_on_line(-1, 5, False), [])

    def test_centered_single(self):
        pos = positions_on_line(10, 20, False)
        self.assertEqual(len(pos), 1)
        self.assertAlmostEqual(pos[0], 5.0)

    def test_centered_multiple(self):
        pos = positions_on_line(30, 10, False)
        self.assertEqual(len(pos), 3)
        # Should be symmetric around center
        self.assertAlmostEqual(pos[1], 15.0)

    def test_include_corners_starts_at_zero(self):
        pos = positions_on_line(20, 10, True)
        self.assertAlmostEqual(pos[0], 0.0)
        self.assertAlmostEqual(pos[-1], 20.0)

    def test_include_corners_spacing(self):
        pos = positions_on_line(20, 10, True)
        for i in range(1, len(pos)):
            self.assertAlmostEqual(pos[i] - pos[i - 1], 10.0)


class TestPositionsOnSideCenter(unittest.TestCase):
    def test_zero_length(self):
        self.assertEqual(positions_on_side_center(0, 5, False), [])

    def test_include_corners_starts_at_zero(self):
        pos = positions_on_side_center(15, 5, True)
        self.assertAlmostEqual(pos[0], 0.0)

    def test_centered(self):
        pos = positions_on_side_center(20, 10, False)
        self.assertEqual(len(pos), 2)
        self.assertAlmostEqual(pos[0] + pos[1], 20.0)  # symmetric about center


class TestPositionsOnClosedLength(unittest.TestCase):
    def test_zero_total(self):
        self.assertEqual(positions_on_closed_length(0, 5, False), [])

    def test_evenly_spaced(self):
        pos = positions_on_closed_length(40, 10, False)
        self.assertEqual(len(pos), 4)
        for i in range(1, len(pos)):
            self.assertAlmostEqual(pos[i] - pos[i - 1], 10.0)

    def test_include_corners_starts_at_zero(self):
        pos = positions_on_closed_length(40, 10, True)
        self.assertAlmostEqual(pos[0], 0.0)


class TestAdjustPositionsNearCorners(unittest.TestCase):
    def test_include_corners_unchanged(self):
        pos = [0.0, 5.0, 10.0]
        result = adjust_positions_near_corners(pos, 10, True, 5)
        self.assertEqual(result, pos)

    def test_empty_unchanged(self):
        self.assertEqual(adjust_positions_near_corners([], 10, False, 5), [])

    def test_single_position_centered(self):
        result = adjust_positions_near_corners([5.0], 20, False, 5)
        self.assertAlmostEqual(result[0], 10.0)

    def test_positions_pushed_inward(self):
        pos = [1.0, 9.0]
        result = adjust_positions_near_corners(pos, 10, False, 5)
        self.assertGreater(result[0], 1.0)
        self.assertLess(result[-1], 9.0)


class TestAdjustStitchPositionsAndLengths(unittest.TestCase):
    def test_include_corners_returns_all_same_length(self):
        pos = [0.0, 5.0, 10.0]
        result = adjust_stitch_positions_and_lengths(pos, 10, True, 5, 2.0)
        for _, length in result:
            self.assertAlmostEqual(length, 2.0)

    def test_empty(self):
        self.assertEqual(adjust_stitch_positions_and_lengths([], 10, False, 5, 2.0), [])

    def test_single_centered(self):
        result = adjust_stitch_positions_and_lengths([5.0], 20, False, 5, 2.0)
        self.assertAlmostEqual(result[0][0], 10.0)

    def test_near_corner_stitch_shortened(self):
        # A single stitch on a very short edge forces the position close to
        # both corners, so the stitch length must be clamped below the nominal.
        result = adjust_stitch_positions_and_lengths([1.5], 3.0, False, 5, 3.0)
        self.assertEqual(len(result), 1)
        _, length = result[0]
        self.assertLess(length, 3.0)


# ===========================================================================
# Contour builders
# ===========================================================================

class TestRoundedRectangleContour(unittest.TestCase):
    def test_zero_radius_returns_corners(self):
        pts = rounded_rectangle_contour(0, 0, 10, 10, 0)
        self.assertEqual(len(pts), 4)

    def test_nonzero_radius_more_points(self):
        pts = rounded_rectangle_contour(0, 0, 10, 10, 2)
        self.assertGreater(len(pts), 4)

    def test_empty_for_nonpositive_dimensions(self):
        self.assertEqual(rounded_rectangle_contour(0, 0, 0, 10, 2), [])
        self.assertEqual(rounded_rectangle_contour(0, 0, 10, 0, 2), [])

    def test_radius_clamped(self):
        # radius > width/2 — should not raise
        pts = rounded_rectangle_contour(0, 0, 4, 10, 999)
        self.assertGreater(len(pts), 0)


class TestRoundedTriangleContour(unittest.TestCase):
    def test_wrong_length_returns_empty(self):
        self.assertEqual(rounded_triangle_contour([], 5), [])
        self.assertEqual(rounded_triangle_contour([Point(0, 0), Point(1, 1)], 5), [])

    def test_zero_radius_returns_vertices(self):
        pts = [Point(0, 0), Point(10, 0), Point(5, 10)]
        result = rounded_triangle_contour(pts, 0)
        self.assertEqual(result, pts)

    def test_positive_radius_more_points(self):
        pts = [Point(0, 0), Point(10, 0), Point(5, 10)]
        result = rounded_triangle_contour(pts, 1)
        self.assertGreater(len(result), 3)


# ===========================================================================
# Shapes — path_d
# ===========================================================================

class TestRectanglePathD(unittest.TestCase):
    def test_starts_with_M(self):
        self.assertTrue(Rectangle(0, 0, 10, 5).path_d().startswith("M"))

    def test_ends_with_Z(self):
        self.assertTrue(Rectangle(0, 0, 10, 5).path_d().endswith("Z"))

    def test_contains_coordinates(self):
        d = Rectangle(2, 3, 10, 5).path_d()
        self.assertIn("2.000", d)
        self.assertIn("3.000", d)


class TestRoundedRectanglePathD(unittest.TestCase):
    def test_contains_quadratic_curves(self):
        self.assertIn("Q", RoundedRectangle(0, 0, 20, 10, radius=3).path_d())

    def test_radius_clamped_no_error(self):
        RoundedRectangle(0, 0, 4, 4, radius=999).path_d()


class TestCirclePathD(unittest.TestCase):
    def test_uses_arc_commands(self):
        self.assertIn("A", Circle(50, 50, 10).path_d())


class TestTrianglePathD(unittest.TestCase):
    def test_three_vertices(self):
        d = Triangle(Point(0, 0), Point(10, 0), Point(5, 10)).path_d()
        self.assertEqual(d.count("L"), 2)

    def test_from_box(self):
        t = Triangle.from_box(0, 0, 10, 5)
        self.assertAlmostEqual(t.p1.x, 5)
        self.assertAlmostEqual(t.p1.y, 0)
        self.assertAlmostEqual(t.p2.x, 10)
        self.assertAlmostEqual(t.p2.y, 5)
        self.assertAlmostEqual(t.p3.x, 0)
        self.assertAlmostEqual(t.p3.y, 5)


class TestRoundedTrianglePathD(unittest.TestCase):
    def test_contains_quadratic_curves(self):
        s = RoundedTriangle(Point(5, 0), Point(10, 10), Point(0, 10), radius=2)
        self.assertIn("Q", s.path_d())


# ===========================================================================
# Shapes — hole_points
# ===========================================================================

class TestRectangleHolePoints(unittest.TestCase):
    def test_all_edges_nonempty(self):
        pts = Rectangle(0, 0, 60, 40).hole_points(spacing=10, inset=5)
        self.assertGreater(len(pts), 0)

    def test_partial_edge_fewer_points(self):
        full = Rectangle(0, 0, 60, 40).hole_points(spacing=10, inset=5)
        partial = Rectangle(0, 0, 60, 40).hole_points(edges=[0], spacing=10, inset=5)
        self.assertLess(len(partial), len(full))

    def test_include_corners_more_or_equal_points(self):
        without = Rectangle(0, 0, 60, 40).hole_points(spacing=10, inset=5, include_corners=False)
        with_ = Rectangle(0, 0, 60, 40).hole_points(spacing=10, inset=5, include_corners=True)
        self.assertGreaterEqual(len(with_), len(without))

    def test_no_duplicates(self):
        pts = Rectangle(0, 0, 60, 40).hole_points(spacing=10, inset=5)
        keys = [(round(p.x, 3), round(p.y, 3)) for p in pts]
        self.assertEqual(len(keys), len(set(keys)))

    def test_points_inset_from_edges(self):
        inset = 5.0
        pts = Rectangle(0, 0, 60, 40).hole_points(inset=inset, spacing=15)
        for p in pts:
            self.assertGreaterEqual(p.x, inset - APPROX)
            self.assertGreaterEqual(p.y, inset - APPROX)
            self.assertLessEqual(p.x, 60 - inset + APPROX)
            self.assertLessEqual(p.y, 40 - inset + APPROX)


class TestCircleHolePoints(unittest.TestCase):
    def test_minimum_three_points(self):
        pts = Circle(0, 0, 5).hole_points(spacing=100, inset=0)
        self.assertGreaterEqual(len(pts), 3)

    def test_points_on_ring(self):
        inset = 3.0
        c = Circle(0, 0, 10)
        pts = c.hole_points(inset=inset, spacing=5)
        r = c.radius - inset
        for p in pts:
            self.assertAlmostEqual(distance(Point(0, 0), p), r, places=5)

    def test_inset_larger_than_radius_uses_minimum(self):
        pts = Circle(0, 0, 5).hole_points(inset=99, spacing=5)
        self.assertGreater(len(pts), 0)


class TestTriangleHolePoints(unittest.TestCase):
    def test_all_edges_nonempty(self):
        t = Triangle(Point(50, 10), Point(90, 80), Point(10, 80))
        pts = t.hole_points(spacing=10, inset=5)
        self.assertGreater(len(pts), 0)

    def test_partial_edges_subset(self):
        t = Triangle(Point(50, 10), Point(90, 80), Point(10, 80))
        all_pts = t.hole_points(spacing=10, inset=5)
        edge0_pts = t.hole_points(edges=[0], spacing=10, inset=5)
        self.assertLessEqual(len(edge0_pts), len(all_pts))

    def test_zero_inset_no_crash(self):
        t = Triangle(Point(50, 10), Point(90, 80), Point(10, 80))
        t.hole_points(spacing=10, inset=0)

    def test_collinear_triangle_no_crash(self):
        # degenerate: all points on a line
        t = Triangle(Point(0, 0), Point(5, 0), Point(10, 0))
        t.hole_points(spacing=5, inset=1)


class TestRoundedTriangleHolePoints(unittest.TestCase):
    def test_rounded_path_true_nonempty(self):
        s = RoundedTriangle(Point(65, 10), Point(120, 90), Point(10, 90), radius=12)
        pts = s.hole_points(spacing=8, inset=6, rounded_path=True)
        self.assertGreater(len(pts), 0)

    def test_rounded_path_false_same_as_parent(self):
        s = RoundedTriangle(Point(65, 10), Point(120, 90), Point(10, 90), radius=12)
        straight = s.hole_points(spacing=8, inset=6, rounded_path=False)
        parent = Triangle(s.p1, s.p2, s.p3).hole_points(spacing=8, inset=6)
        self.assertEqual(len(straight), len(parent))

    def test_partial_edges_skip_rounded_path(self):
        s = RoundedTriangle(Point(65, 10), Point(120, 90), Point(10, 90), radius=12)
        # rounded_path only activates when all edges are selected
        partial = s.hole_points(edges=[0], spacing=8, inset=6, rounded_path=True)
        self.assertGreater(len(partial), 0)


# ===========================================================================
# Shapes — stitch_segments
# ===========================================================================

class TestRectangleStitchSegments(unittest.TestCase):
    def test_returns_pairs(self):
        segs = Rectangle(0, 0, 60, 40).stitch_segments(spacing=10, inset=5, stitch_length=3)
        for a, b in segs:
            self.assertIsInstance(a, Point)
            self.assertIsInstance(b, Point)

    def test_stitch_length_respected(self):
        segs = Rectangle(0, 0, 60, 40).stitch_segments(spacing=10, inset=5, stitch_length=3)
        for a, b in segs:
            self.assertLessEqual(distance(a, b), 3.0 + APPROX)

    def test_partial_edges_fewer_segments(self):
        all_segs = Rectangle(0, 0, 60, 40).stitch_segments(spacing=10, inset=5, stitch_length=3)
        partial = Rectangle(0, 0, 60, 40).stitch_segments(edges=[0], spacing=10, inset=5, stitch_length=3)
        self.assertLess(len(partial), len(all_segs))

    def test_angle_45_different_from_0(self):
        segs_0 = Rectangle(0, 0, 60, 40).stitch_segments(spacing=10, inset=5, stitch_length=3, stitch_angle_deg=0)
        segs_45 = Rectangle(0, 0, 60, 40).stitch_segments(spacing=10, inset=5, stitch_length=3, stitch_angle_deg=45)
        # Different angle → different segment endpoints
        self.assertNotEqual(
            [(round(a.x, 3), round(a.y, 3)) for a, b in segs_0],
            [(round(a.x, 3), round(a.y, 3)) for a, b in segs_45],
        )


class TestRoundedRectangleStitchSegments(unittest.TestCase):
    def test_all_edges_uses_contour_path(self):
        # all edges → rounded contour path is used
        segs = RoundedRectangle(0, 0, 60, 40, radius=8).stitch_segments(
            spacing=10, inset=5, stitch_length=3
        )
        self.assertGreater(len(segs), 0)

    def test_partial_edges_uses_parent(self):
        segs = RoundedRectangle(0, 0, 60, 40, radius=8).stitch_segments(
            edges=[1], spacing=10, inset=5, stitch_length=3
        )
        self.assertGreater(len(segs), 0)

    def test_degenerate_small_inset_no_crash(self):
        # inset makes w or h <= 0
        segs = RoundedRectangle(0, 0, 4, 4, radius=2).stitch_segments(spacing=5, inset=3, stitch_length=2)
        self.assertEqual(segs, [])


class TestCircleStitchSegments(unittest.TestCase):
    def test_minimum_three_segments(self):
        segs = Circle(0, 0, 10).stitch_segments(spacing=100, inset=0, stitch_length=2)
        self.assertGreaterEqual(len(segs), 3)

    def test_segments_centred_on_ring(self):
        inset = 2.0
        c = Circle(0, 0, 10)
        r = c.radius - inset
        segs = c.stitch_segments(spacing=5, inset=inset, stitch_length=2)
        for a, b in segs:
            cx = (a.x + b.x) / 2
            cy = (a.y + b.y) / 2
            self.assertAlmostEqual(distance(Point(0, 0), Point(cx, cy)), r, places=4)


class TestTriangleStitchSegments(unittest.TestCase):
    def test_nonempty(self):
        t = Triangle(Point(50, 10), Point(90, 80), Point(10, 80))
        self.assertGreater(len(t.stitch_segments(spacing=10, inset=5, stitch_length=3)), 0)

    def test_partial_edges(self):
        t = Triangle(Point(50, 10), Point(90, 80), Point(10, 80))
        all_segs = t.stitch_segments(spacing=10, inset=5, stitch_length=3)
        partial = t.stitch_segments(edges=[0], spacing=10, inset=5, stitch_length=3)
        self.assertLess(len(partial), len(all_segs))


class TestRoundedTriangleStitchSegments(unittest.TestCase):
    def test_rounded_path_true(self):
        s = RoundedTriangle(Point(65, 10), Point(120, 90), Point(10, 90), radius=12)
        segs = s.stitch_segments(spacing=8, inset=6, stitch_length=3, rounded_path=True)
        self.assertGreater(len(segs), 0)

    def test_rounded_path_false_same_as_parent(self):
        s = RoundedTriangle(Point(65, 10), Point(120, 90), Point(10, 90), radius=12)
        parent = Triangle(s.p1, s.p2, s.p3).stitch_segments(spacing=8, inset=6, stitch_length=3)
        child = s.stitch_segments(spacing=8, inset=6, stitch_length=3, rounded_path=False)
        self.assertEqual(len(child), len(parent))


# ===========================================================================
# InsetTriangleVertices
# ===========================================================================

class TestInsetTriangleVertices(unittest.TestCase):
    def test_zero_inset_unchanged(self):
        p1, p2, p3 = Point(0, 0), Point(10, 0), Point(5, 10)
        r1, r2, r3 = inset_triangle_vertices(p1, p2, p3, 0)
        self.assertEqual(r1, p1)
        self.assertEqual(r2, p2)
        self.assertEqual(r3, p3)

    def test_positive_inset_moves_inward(self):
        p1, p2, p3 = Point(0, 0), Point(100, 0), Point(50, 100)
        r1, r2, r3 = inset_triangle_vertices(p1, p2, p3, 5)
        # Inset triangle should be smaller — centroid closer
        centroid_orig = Point(50, 100 / 3)
        centroid_new = Point((r1.x + r2.x + r3.x) / 3, (r1.y + r2.y + r3.y) / 3)
        d_orig = max(distance(p, centroid_orig) for p in [p1, p2, p3])
        d_new = max(distance(p, centroid_new) for p in [r1, r2, r3])
        self.assertLess(d_new, d_orig)

    def test_collinear_no_crash(self):
        p1, p2, p3 = Point(0, 0), Point(5, 0), Point(10, 0)
        inset_triangle_vertices(p1, p2, p3, 1)


# ===========================================================================
# Polyline helpers
# ===========================================================================

class TestPointsOnClosedPolyline(unittest.TestCase):
    def test_square_evenly_spaced(self):
        poly = [Point(0, 0), Point(10, 0), Point(10, 10), Point(0, 10)]
        pts = points_on_closed_polyline(poly, spacing=10, include_corners=False)
        self.assertEqual(len(pts), 4)

    def test_single_point_polyline_empty(self):
        pts = points_on_closed_polyline([Point(0, 0)], spacing=5, include_corners=False)
        self.assertEqual(pts, [])


class TestStitchSegmentsOnClosedPolyline(unittest.TestCase):
    def test_square(self):
        poly = [Point(0, 0), Point(10, 0), Point(10, 10), Point(0, 10)]
        segs = stitch_segments_on_closed_polyline(poly, spacing=10, stitch_length=2, stitch_angle_deg=0, include_corners=False)
        self.assertEqual(len(segs), 4)

    def test_empty_polyline(self):
        segs = stitch_segments_on_closed_polyline([], spacing=5, stitch_length=2, stitch_angle_deg=0, include_corners=False)
        self.assertEqual(segs, [])


# ===========================================================================
# SvgDocument — SVG output
# ===========================================================================

class TestSvgDocumentOutput(unittest.TestCase):
    def _doc(self):
        return SvgDocument(100, 60)

    def test_svg_header(self):
        svg = self._doc().to_svg()
        self.assertIn('<?xml version="1.0"', svg)
        self.assertIn('<svg', svg)

    def test_viewbox_matches_dimensions(self):
        svg = SvgDocument(123, 45).to_svg()
        self.assertIn('viewBox="0 0 123 45"', svg)

    def test_width_height_in_mm(self):
        svg = SvgDocument(123, 45).to_svg()
        self.assertIn('width="123mm"', svg)
        self.assertIn('height="45mm"', svg)

    def test_no_css_style_tag(self):
        doc = self._doc()
        doc.add_shape(Rectangle(10, 10, 80, 40), layer="cut")
        self.assertNotIn("<style", doc.to_svg())

    def test_inline_stroke_color(self):
        doc = self._doc()
        doc.add_shape(Rectangle(10, 10, 80, 40), layer="cut")
        self.assertIn('stroke="#ff0000"', doc.to_svg())

    def test_vector_effect_attribute(self):
        doc = self._doc()
        doc.add_circle(50, 30, 5, layer="cut")
        self.assertIn('vector-effect="non-scaling-stroke"', doc.to_svg())

    def test_no_css_in_stitch_layer(self):
        doc = self._doc()
        s = Rectangle(10, 10, 80, 40)
        doc.add_shape(s, layer="stitch")
        self.assertNotIn("<style", doc.to_svg())
        self.assertIn('stroke="#0000ff"', doc.to_svg())

    def test_crease_layer_dasharray(self):
        doc = self._doc()
        doc.add_line(0, 0, 10, 10, layer="crease")
        self.assertIn('stroke-dasharray="3 2"', doc.to_svg())

    def test_guide_layer_dasharray(self):
        doc = self._doc()
        doc.add_line(0, 0, 10, 10, layer="guide")
        self.assertIn('stroke-dasharray="2 2"', doc.to_svg())

    def test_custom_styles_applied(self):
        doc = SvgDocument(100, 60, styles={
            "cut": StrokeStyle("#123456", 0.5),
            "stitch": StrokeStyle("#654321", 0.3),
            "crease": StrokeStyle("#abcdef", 0.1, "4 2"),
            "guide": StrokeStyle("#fedcba", 0.1),
        })
        doc.add_shape(Rectangle(10, 10, 80, 40), layer="cut")
        self.assertIn('stroke="#123456"', doc.to_svg())
        self.assertIn('stroke-width="0.5"', doc.to_svg())

    def test_add_path_raw(self):
        doc = self._doc()
        doc.add_path("M 0 0 L 10 10", layer="cut")
        self.assertIn("M 0 0 L 10 10", doc.to_svg())

    def test_add_line_coordinates(self):
        doc = self._doc()
        doc.add_line(1.5, 2.5, 8.5, 9.5, layer="cut")
        svg = doc.to_svg()
        self.assertIn('x1="1.500"', svg)
        self.assertIn('y2="9.500"', svg)

    def test_add_circle_attributes(self):
        doc = self._doc()
        doc.add_circle(50, 30, 7.5, layer="stitch")
        svg = doc.to_svg()
        self.assertIn('cx="50.000"', svg)
        self.assertIn('r="7.500"', svg)

    def test_stitch_thickness_override(self):
        doc = self._doc()
        s = Rectangle(10, 10, 80, 40)
        doc.add_stitch_pattern(s, spacing=10, stitch_length=3, stitch_thickness=0.75)
        self.assertIn('stroke-width="0.75"', doc.to_svg())

    def test_add_stitch_holes_alias(self):
        doc = self._doc()
        s = Rectangle(10, 10, 80, 40)
        doc.add_stitch_holes(s, spacing=10, hole_radius=1.0, inset=5)
        self.assertGreater(len(doc.elements), 0)

    def test_multiple_shapes_all_present(self):
        # add_shape always emits <path>; add_circle emits <circle>
        doc = self._doc()
        doc.add_shape(Rectangle(10, 10, 30, 20), layer="cut")
        doc.add_circle(70, 30, 5, layer="stitch")
        svg = doc.to_svg()
        self.assertIn("<path", svg)
        self.assertIn("<circle", svg)

    def test_add_stitch_on_polyline_adds_lines(self):
        doc = self._doc()
        pts = [(10, 10), (50, 10), (90, 10)]
        doc.add_stitch_on_polyline(pts, spacing=10, stitch_length=3)
        self.assertGreater(len(doc.elements), 0)
        self.assertIn("<line", doc.to_svg())

    def test_add_stitch_on_polyline_thickness_override(self):
        doc = self._doc()
        pts = [(10, 10), (90, 10)]
        doc.add_stitch_on_polyline(pts, spacing=10, stitch_length=3, stitch_thickness=0.6)
        self.assertIn('stroke-width="0.6"', doc.to_svg())


# ===========================================================================
# Path helpers
# ===========================================================================

class TestPathHelpers(unittest.TestCase):
    def test_straight_path_d_starts_with_M(self):
        d = _straight_path_d([(0, 0), (10, 0), (10, 10)])
        self.assertTrue(d.startswith("M"))

    def test_straight_path_d_ends_with_Z(self):
        d = _straight_path_d([(0, 0), (10, 0), (10, 10)])
        self.assertTrue(d.endswith("Z"))

    def test_straight_path_d_contains_all_coords(self):
        d = _straight_path_d([(1.0, 2.0), (3.0, 4.0)])
        self.assertIn("1.000", d)
        self.assertIn("4.000", d)

    def test_smooth_path_d_contains_Q(self):
        d = _smooth_path_d([(0, 0), (5, 10), (10, 0)])
        self.assertIn("Q", d)

    def test_smooth_path_d_fallback_for_two_points(self):
        # < 3 points → falls back to straight
        d = _smooth_path_d([(0, 0), (10, 0)])
        self.assertNotIn("Q", d)
        self.assertTrue(d.endswith("Z"))

    def test_smooth_path_d_starts_with_M(self):
        d = _smooth_path_d([(0, 0), (5, 10), (10, 0)])
        self.assertTrue(d.startswith("M"))


# ===========================================================================
# offset_polyline
# ===========================================================================

class TestOffsetPolyline(unittest.TestCase):
    def test_too_short_returns_copy(self):
        pts = [(5.0, 5.0)]
        result = offset_polyline(pts, 3)
        self.assertEqual(result, pts)

    def test_horizontal_line_offset_right(self):
        # Line going right → "right" is the right-hand side of travel direction.
        # In SVG (Y down), rightward travel has right-hand = UPWARD = negative Y.
        pts = [(0.0, 0.0), (10.0, 0.0)]
        result = offset_polyline(pts, 3, side="right")
        self.assertEqual(len(result), 2)
        self.assertAlmostEqual(result[0][1], -3.0)
        self.assertAlmostEqual(result[1][1], -3.0)

    def test_horizontal_line_offset_left(self):
        # Left-hand side of rightward travel = DOWNWARD = positive Y.
        pts = [(0.0, 0.0), (10.0, 0.0)]
        result = offset_polyline(pts, 3, side="left")
        self.assertAlmostEqual(result[0][1], 3.0)
        self.assertAlmostEqual(result[1][1], 3.0)

    def test_invalid_side_raises(self):
        with self.assertRaises(ValueError):
            offset_polyline([(0, 0), (1, 0)], 1, side="up")

    def test_length_preserved(self):
        pts = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
        result = offset_polyline(pts, 2, side="right")
        self.assertEqual(len(result), len(pts))

    def test_preserves_direction(self):
        # Offset of a vertical downward line on the right should move right (+x)
        pts = [(0.0, 0.0), (0.0, 10.0)]
        result = offset_polyline(pts, 3, side="right")
        self.assertAlmostEqual(result[0][0], 3.0)
        self.assertAlmostEqual(result[1][0], 3.0)

    def test_miter_join_at_right_angle(self):
        # L-shape: right then down. side="right" offsets to the right-hand side.
        # Segment 1 right: right-hand = upward (y=-2).
        # Segment 2 down:  right-hand = rightward (x=+12).
        # Miter intersection: (12, -2).
        pts = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
        result = offset_polyline(pts, 2, side="right")
        mx, my = result[1]
        self.assertAlmostEqual(mx, 12.0, places=3)
        self.assertAlmostEqual(my, -2.0, places=3)

    def test_zero_length_segment_no_crash(self):
        pts = [(0.0, 0.0), (0.0, 0.0), (10.0, 0.0)]
        result = offset_polyline(pts, 2, side="right")
        self.assertEqual(len(result), 3)


# ===========================================================================
# mirror_polyline
# ===========================================================================

class TestMirrorPolyline(unittest.TestCase):
    def test_mirrors_x_around_center(self):
        pts = [(10.0, 5.0), (30.0, 5.0)]
        result = mirror_polyline(pts, center_x=20.0)
        self.assertAlmostEqual(result[0][0], 30.0)
        self.assertAlmostEqual(result[1][0], 10.0)

    def test_y_unchanged(self):
        pts = [(5.0, 7.0), (15.0, 13.0)]
        result = mirror_polyline(pts, center_x=10.0)
        self.assertAlmostEqual(result[0][1], 7.0)
        self.assertAlmostEqual(result[1][1], 13.0)

    def test_point_on_axis_unchanged(self):
        pts = [(10.0, 5.0)]
        result = mirror_polyline(pts, center_x=10.0)
        self.assertAlmostEqual(result[0][0], 10.0)

    def test_double_mirror_roundtrips(self):
        pts = [(3.0, 9.0), (7.0, 2.0)]
        once = mirror_polyline(pts, 10.0)
        twice = mirror_polyline(once, 10.0)
        for (x1, y1), (x2, y2) in zip(pts, twice):
            self.assertAlmostEqual(x1, x2)
            self.assertAlmostEqual(y1, y2)


# ===========================================================================
# _offset_closed_polygon
# ===========================================================================

class TestOffsetClosedPolygon(unittest.TestCase):
    def test_square_shrinks(self):
        # A CW square (in SVG Y-down) should shrink inward
        pts = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
        result = _offset_closed_polygon(pts, 2.0)
        self.assertEqual(len(result), 4)
        xs = [p[0] for p in result]
        ys = [p[1] for p in result]
        self.assertGreater(min(xs), 0.0)
        self.assertLess(max(xs), 10.0)
        self.assertGreater(min(ys), 0.0)
        self.assertLess(max(ys), 10.0)

    def test_too_few_points_returns_copy(self):
        pts = [(0.0, 0.0), (5.0, 5.0)]
        result = _offset_closed_polygon(pts, 2.0)
        self.assertEqual(result, pts)

    def test_returns_same_count(self):
        pts = [(0.0, 0.0), (20.0, 0.0), (20.0, 15.0), (0.0, 15.0)]
        result = _offset_closed_polygon(pts, 3.0)
        self.assertEqual(len(result), len(pts))


# ===========================================================================
# stitch_segments_on_open_polyline
# ===========================================================================

class TestStitchSegmentsOnOpenPolyline(unittest.TestCase):
    def test_returns_point_pairs(self):
        pts = [(0.0, 0.0), (100.0, 0.0)]
        segs = stitch_segments_on_open_polyline(pts, spacing=10, stitch_length=3)
        for a, b in segs:
            self.assertIsInstance(a, Point)
            self.assertIsInstance(b, Point)

    def test_spacing_respected(self):
        pts = [(0.0, 0.0), (100.0, 0.0)]
        segs = stitch_segments_on_open_polyline(pts, spacing=10, stitch_length=3)
        # First stitch centre should be at x=10
        cx0 = (segs[0][0].x + segs[0][1].x) / 2
        self.assertAlmostEqual(cx0, 10.0, places=5)

    def test_stitch_length_respected(self):
        pts = [(0.0, 0.0), (100.0, 0.0)]
        segs = stitch_segments_on_open_polyline(pts, spacing=10, stitch_length=3)
        for a, b in segs:
            self.assertAlmostEqual(distance(a, b), 3.0, places=5)

    def test_angle_0_parallel_to_path(self):
        pts = [(0.0, 0.0), (100.0, 0.0)]
        segs = stitch_segments_on_open_polyline(pts, spacing=10, stitch_length=3, stitch_angle_deg=0)
        for a, b in segs:
            self.assertAlmostEqual(a.y, b.y, places=5)   # same Y → horizontal

    def test_angle_90_perpendicular_to_path(self):
        pts = [(0.0, 0.0), (100.0, 0.0)]
        segs = stitch_segments_on_open_polyline(pts, spacing=10, stitch_length=3, stitch_angle_deg=90)
        for a, b in segs:
            self.assertAlmostEqual(a.x, b.x, places=4)   # same X → vertical

    def test_empty_polyline_returns_empty(self):
        segs = stitch_segments_on_open_polyline([], spacing=10, stitch_length=3)
        self.assertEqual(segs, [])

    def test_zero_length_segment_skipped(self):
        pts = [(0.0, 0.0), (0.0, 0.0), (50.0, 0.0)]
        segs = stitch_segments_on_open_polyline(pts, spacing=10, stitch_length=3)
        self.assertGreater(len(segs), 0)

    def test_count_scales_with_path_length(self):
        short = stitch_segments_on_open_polyline([(0, 0), (30, 0)], spacing=10, stitch_length=2)
        long_ = stitch_segments_on_open_polyline([(0, 0), (60, 0)], spacing=10, stitch_length=2)
        self.assertGreater(len(long_), len(short))


# ===========================================================================
# Polygon — construction
# ===========================================================================

class TestPolygonConstruction(unittest.TestCase):
    def _diamond(self):
        return Polygon([(50, 0), (100, 50), (50, 100), (0, 50)])

    def test_stores_points(self):
        pts = [(0, 0), (10, 0), (10, 10)]
        p = Polygon(pts)
        self.assertEqual(p.points, pts)

    def test_smooth_default_false(self):
        self.assertFalse(Polygon([(0, 0), (1, 0), (1, 1)]).smooth)

    def test_from_mirror_doubles_interior_points(self):
        half = [(50, 0), (20, 50), (50, 100)]
        p = Polygon.from_mirror(half, center_x=50)
        # 3 points in left half; endpoints shared → full polygon has 3+(3-2)=4 points
        self.assertEqual(len(p.points), 4)

    def test_from_mirror_symmetry(self):
        half = [(50, 0), (20, 30), (50, 60)]
        p = Polygon.from_mirror(half, center_x=50)
        xs = [pt[0] for pt in p.points]
        # Leftmost and rightmost should be equidistant from center
        self.assertAlmostEqual(min(xs) + max(xs), 100.0, places=5)

    def test_from_mirror_smooth_flag_propagated(self):
        half = [(50, 0), (20, 50), (50, 100)]
        self.assertTrue(Polygon.from_mirror(half, 50, smooth=True).smooth)
        self.assertFalse(Polygon.from_mirror(half, 50, smooth=False).smooth)


# ===========================================================================
# Polygon — path_d
# ===========================================================================

class TestPolygonPathD(unittest.TestCase):
    def test_straight_starts_with_M_ends_with_Z(self):
        p = Polygon([(0, 0), (10, 0), (10, 10)], smooth=False)
        d = p.path_d()
        self.assertTrue(d.startswith("M"))
        self.assertTrue(d.endswith("Z"))

    def test_smooth_contains_Q(self):
        p = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)], smooth=True)
        self.assertIn("Q", p.path_d())

    def test_smooth_false_no_Q(self):
        p = Polygon([(0, 0), (10, 0), (10, 10)], smooth=False)
        self.assertNotIn("Q", p.path_d())

    def test_coordinates_present_in_path(self):
        p = Polygon([(3.0, 7.0), (13.0, 7.0), (8.0, 17.0)], smooth=False)
        d = p.path_d()
        self.assertIn("3.000", d)
        self.assertIn("17.000", d)


# ===========================================================================
# Polygon — hole_points
# ===========================================================================

class TestPolygonHolePoints(unittest.TestCase):
    def _square(self):
        # CW square in SVG (Y-down)
        return Polygon([(0, 0), (60, 0), (60, 60), (0, 60)])

    def test_returns_points(self):
        pts = self._square().hole_points(spacing=10, inset=5)
        self.assertGreater(len(pts), 0)
        for p in pts:
            self.assertIsInstance(p, Point)

    def test_inset_moves_points_inward(self):
        pts = self._square().hole_points(spacing=10, inset=5)
        for p in pts:
            self.assertGreater(p.x, -0.1)
            self.assertGreater(p.y, -0.1)
            self.assertLess(p.x, 60.1)
            self.assertLess(p.y, 60.1)

    def test_zero_inset_still_works(self):
        pts = self._square().hole_points(spacing=10, inset=0)
        self.assertGreater(len(pts), 0)

    def test_no_duplicates(self):
        pts = self._square().hole_points(spacing=10, inset=5)
        keys = [(round(p.x, 3), round(p.y, 3)) for p in pts]
        self.assertEqual(len(keys), len(set(keys)))

    def test_from_mirror_shape_has_holes(self):
        half = [(50, 5), (20, 40), (50, 75)]
        shape = Polygon.from_mirror(half, center_x=50)
        pts = shape.hole_points(spacing=8, inset=4)
        self.assertGreater(len(pts), 0)


# ===========================================================================
# Polygon — stitch_segments
# ===========================================================================

class TestPolygonStitchSegments(unittest.TestCase):
    def _square(self):
        return Polygon([(0, 0), (60, 0), (60, 60), (0, 60)])

    def test_returns_point_pairs(self):
        segs = self._square().stitch_segments(spacing=10, inset=5, stitch_length=3)
        for a, b in segs:
            self.assertIsInstance(a, Point)
            self.assertIsInstance(b, Point)

    def test_nonempty(self):
        segs = self._square().stitch_segments(spacing=10, inset=5, stitch_length=3)
        self.assertGreater(len(segs), 0)

    def test_stitch_length_respected(self):
        segs = self._square().stitch_segments(spacing=10, inset=5, stitch_length=3)
        for a, b in segs:
            self.assertLessEqual(distance(a, b), 3.0 + APPROX)

    def test_angle_changes_orientation(self):
        segs_0  = self._square().stitch_segments(spacing=10, inset=5, stitch_length=3, stitch_angle_deg=0)
        segs_45 = self._square().stitch_segments(spacing=10, inset=5, stitch_length=3, stitch_angle_deg=45)
        coords_0  = [(round(a.x,2), round(a.y,2)) for a,b in segs_0]
        coords_45 = [(round(a.x,2), round(a.y,2)) for a,b in segs_45]
        self.assertNotEqual(coords_0, coords_45)

    def test_smooth_polygon_same_count_as_straight(self):
        pts = [(0, 0), (60, 0), (60, 60), (0, 60)]
        straight = Polygon(pts, smooth=False).stitch_segments(spacing=10, inset=5, stitch_length=3)
        smooth   = Polygon(pts, smooth=True ).stitch_segments(spacing=10, inset=5, stitch_length=3)
        # Both use the same inset polygon → same count
        self.assertEqual(len(straight), len(smooth))

    def test_from_mirror_stitch_segments(self):
        half = [(50, 5), (20, 40), (50, 75)]
        shape = Polygon.from_mirror(half, center_x=50)
        segs = shape.stitch_segments(spacing=8, inset=4, stitch_length=3)
        self.assertGreater(len(segs), 0)


class TestStadiumPathD(unittest.TestCase):
    def test_horizontal_radius_is_half_height(self):
        s = Stadium(10, 10, 100, 30)
        self.assertEqual(s.radius, 15.0)

    def test_vertical_radius_is_half_width(self):
        s = Stadium(10, 10, 30, 100)
        self.assertEqual(s.radius, 15.0)

    def test_path_uses_arcs(self):
        d = Stadium(10, 10, 100, 30).path_d()
        self.assertIn("A 15.000 15.000", d)
        self.assertTrue(d.startswith("M "))
        self.assertTrue(d.rstrip().endswith("Z"))

    def test_square_box_is_circle_like(self):
        # width == height → both caps meet, straight segments degenerate
        d = Stadium(0, 0, 40, 40).path_d()
        self.assertIn("A 20.000 20.000", d)


class TestStadiumHolePoints(unittest.TestCase):
    def test_all_edges_follow_contour(self):
        s = Stadium(10, 10, 100, 30)
        pts = s.hole_points(spacing=6, inset=4)
        self.assertGreater(len(pts), 0)
        # Points on the caps must extend beyond the straight-edge x range
        xs = [p.x for p in pts]
        self.assertLess(min(xs), 25.0)   # inside the left cap
        self.assertGreater(max(xs), 95.0)  # inside the right cap

    def test_holes_inside_shape(self):
        s = Stadium(10, 10, 100, 30)
        for p in s.hole_points(spacing=6, inset=4):
            self.assertGreaterEqual(p.x, 10.0)
            self.assertLessEqual(p.x, 110.0)
            self.assertGreaterEqual(p.y, 10.0)
            self.assertLessEqual(p.y, 40.0)

    def test_partial_edges_use_straight_fallback(self):
        s = Stadium(10, 10, 100, 30)
        pts = s.hole_points(edges=[0], spacing=6, inset=4)
        # Top edge only → all points share the same y
        self.assertTrue(all(abs(p.y - 14.0) < 0.001 for p in pts))

    def test_excessive_inset_returns_empty(self):
        s = Stadium(10, 10, 100, 30)
        self.assertEqual(s.hole_points(spacing=6, inset=20), [])

    def test_smaller_spacing_gives_more_holes(self):
        s = Stadium(10, 10, 100, 30)
        few = s.hole_points(spacing=10, inset=4)
        many = s.hole_points(spacing=4, inset=4)
        self.assertGreater(len(many), len(few))


class TestStadiumStitchSegments(unittest.TestCase):
    def test_all_edges_follow_contour(self):
        s = Stadium(10, 10, 100, 30)
        segs = s.stitch_segments(spacing=6, inset=4, stitch_length=3)
        self.assertGreater(len(segs), 0)
        xs = [a.x for a, b in segs] + [b.x for a, b in segs]
        self.assertLess(min(xs), 25.0)
        self.assertGreater(max(xs), 95.0)

    def test_stitch_length_respected(self):
        s = Stadium(10, 10, 100, 30)
        for a, b in s.stitch_segments(spacing=8, inset=4, stitch_length=3):
            self.assertAlmostEqual(distance(a, b), 3.0, places=1)

    def test_partial_edges_use_straight_fallback(self):
        s = Stadium(10, 10, 100, 30)
        segs = s.stitch_segments(edges=[0], spacing=6, inset=4, stitch_length=3)
        self.assertGreater(len(segs), 0)
        for a, b in segs:
            self.assertAlmostEqual(a.y, 14.0, places=3)
            self.assertAlmostEqual(b.y, 14.0, places=3)

    def test_excessive_inset_returns_empty(self):
        s = Stadium(10, 10, 100, 30)
        self.assertEqual(s.stitch_segments(spacing=6, inset=20, stitch_length=3), [])

    def test_document_integration(self):
        doc = SvgDocument(width_mm=140, height_mm=60)
        s = Stadium(10, 15, 120, 30)
        doc.add_shape(s, layer="cut")
        doc.add_stitch_pattern(s, spacing=5, stitch_length=3, inset=4)
        doc.add_holes(s, spacing=10, hole_radius=1.5, inset=8)
        out = doc.to_svg()
        self.assertIn("<path", out)
        self.assertIn("<line", out)
        self.assertIn("<circle", out)


class TestEllipsePathD(unittest.TestCase):
    def test_uses_two_arcs(self):
        d = Ellipse(60, 40, 50, 25).path_d()
        self.assertEqual(d.count("A 50.000 25.000"), 2)
        self.assertTrue(d.startswith("M 10.000 40.000"))
        self.assertTrue(d.rstrip().endswith("Z"))

    def test_equal_radii_match_circle_extents(self):
        d = Ellipse(50, 50, 30, 30).path_d()
        self.assertIn("A 30.000 30.000", d)


class TestEllipseHolePoints(unittest.TestCase):
    def test_holes_on_inset_ellipse(self):
        e = Ellipse(60, 40, 50, 25)
        pts = e.hole_points(spacing=6, inset=4)
        self.assertGreater(len(pts), 0)
        # Every point must lie on the inset ellipse: ((x-cx)/rx')² + ((y-cy)/ry')² ≈ 1
        for p in pts:
            v = ((p.x - 60) / 46) ** 2 + ((p.y - 40) / 21) ** 2
            self.assertAlmostEqual(v, 1.0, places=2)

    def test_excessive_inset_returns_empty(self):
        self.assertEqual(Ellipse(60, 40, 50, 25).hole_points(inset=25), [])
        self.assertEqual(Ellipse(60, 40, 50, 25).hole_points(inset=50), [])

    def test_smaller_spacing_gives_more_holes(self):
        e = Ellipse(60, 40, 50, 25)
        self.assertGreater(len(e.hole_points(spacing=4, inset=4)),
                           len(e.hole_points(spacing=10, inset=4)))

    def test_edges_parameter_ignored(self):
        e = Ellipse(60, 40, 50, 25)
        self.assertEqual(len(e.hole_points(edges=[0], spacing=6, inset=4)),
                         len(e.hole_points(edges="all", spacing=6, inset=4)))


class TestEllipseStitchSegments(unittest.TestCase):
    def test_segments_generated(self):
        segs = Ellipse(60, 40, 50, 25).stitch_segments(spacing=6, inset=4, stitch_length=3)
        self.assertGreater(len(segs), 0)

    def test_stitch_length_respected(self):
        for a, b in Ellipse(60, 40, 50, 25).stitch_segments(spacing=8, inset=4, stitch_length=3):
            self.assertAlmostEqual(distance(a, b), 3.0, places=1)

    def test_excessive_inset_returns_empty(self):
        self.assertEqual(Ellipse(60, 40, 50, 25).stitch_segments(inset=25, stitch_length=3), [])

    def test_document_integration(self):
        doc = SvgDocument(width_mm=130, height_mm=90)
        e = Ellipse(65, 45, 55, 35)
        doc.add_shape(e, layer="cut")
        doc.add_stitch_pattern(e, spacing=6, stitch_length=3, inset=5)
        doc.add_holes(e, spacing=8, hole_radius=1.5, inset=8)
        out = doc.to_svg()
        self.assertIn("<path", out)
        self.assertIn("<line", out)
        self.assertIn("<circle", out)


class TestPerCornerRoundedRectangle(unittest.TestCase):
    def test_uniform_default_unchanged(self):
        s = RoundedRectangle(10, 10, 100, 60, radius=8)
        self.assertEqual(s.corner_radii(), (8.0, 8.0, 8.0, 8.0))

    def test_per_corner_override(self):
        s = RoundedRectangle(10, 10, 100, 60, radius=8, radius_bl=0, radius_br=0)
        self.assertEqual(s.corner_radii(), (8.0, 8.0, 0.0, 0.0))

    def test_sharp_corners_skip_q_curves(self):
        s = RoundedRectangle(10, 10, 100, 60, radius=8, radius_bl=0, radius_br=0)
        self.assertEqual(s.path_d().count("Q"), 2)

    def test_all_sharp_equals_rectangle_outline(self):
        s = RoundedRectangle(10, 10, 100, 60, radius=0,
                             radius_tl=0, radius_tr=0, radius_br=0, radius_bl=0)
        self.assertEqual(s.path_d().count("Q"), 0)

    def test_overlapping_radii_scaled_down(self):
        # Two 30mm corners on a 40mm edge → scaled to 20mm each
        s = RoundedRectangle(0, 0, 40, 100, radius=0,
                             radius_tl=30, radius_tr=30, radius_br=0, radius_bl=0)
        tl, tr, br, bl = s.corner_radii()
        self.assertAlmostEqual(tl, 20.0)
        self.assertAlmostEqual(tr, 20.0)
        self.assertEqual((br, bl), (0.0, 0.0))

    def test_negative_radius_clamped_to_zero(self):
        s = RoundedRectangle(10, 10, 100, 60, radius=8, radius_tl=-5)
        self.assertEqual(s.corner_radii()[0], 0.0)

    def test_stitches_follow_asymmetric_contour(self):
        s = RoundedRectangle(10, 10, 100, 60, radius=20, radius_bl=0, radius_br=0)
        segs = s.stitch_segments(spacing=6, inset=4, stitch_length=3)
        self.assertGreater(len(segs), 0)
        ys = [a.y for a, b in segs] + [b.y for a, b in segs]
        # Bottom edge is straight at y = 66 (10 + 60 - 4); points reach it
        self.assertAlmostEqual(max(ys), 66.0, delta=2.0)

    def test_uniform_stitches_match_old_behavior(self):
        uniform = RoundedRectangle(20, 15, 100, 60, radius=10)
        explicit = RoundedRectangle(20, 15, 100, 60, radius=0,
                                    radius_tl=10, radius_tr=10, radius_br=10, radius_bl=10)
        a = uniform.stitch_segments(spacing=8, inset=7, stitch_length=3.5)
        b = explicit.stitch_segments(spacing=8, inset=7, stitch_length=3.5)
        self.assertEqual(len(a), len(b))

    def test_contour_helper_per_corner(self):
        c = rounded_rectangle_contour(0, 0, 100, 60, 0.0, radii=(10, 10, 0, 0))
        self.assertGreater(len(c), 4)
        # Bottom-right corner is sharp → contour contains the exact corner point
        self.assertTrue(any(abs(p.x - 100) < 0.01 and abs(p.y - 60) < 0.01 for p in c))

    def test_document_integration(self):
        doc = SvgDocument(width_mm=120, height_mm=90)
        s = RoundedRectangle(10, 10, 100, 70, radius=0, radius_tl=15, radius_tr=15,
                             radius_br=0, radius_bl=0)
        doc.add_shape(s, layer="cut")
        doc.add_stitch_pattern(s, spacing=6, stitch_length=3, inset=5)
        doc.add_holes(s, spacing=10, hole_radius=1.2, inset=5)
        out = doc.to_svg()
        self.assertIn("<path", out)
        self.assertIn("<line", out)
        self.assertIn("<circle", out)
