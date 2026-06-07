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
    Point,
    Rectangle,
    RoundedRectangle,
    RoundedTriangle,
    StrokeStyle,
    SvgDocument,
    Triangle,
    adjust_positions_near_corners,
    adjust_stitch_positions_and_lengths,
    deduplicate_points,
    distance,
    inset_triangle_vertices,
    inward_unit_normal,
    line_intersection,
    move_towards,
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
