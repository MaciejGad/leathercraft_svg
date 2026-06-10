"""
Unit tests for leathercraft_dsl — parser and compiler.
Run with: pytest tests/test_dsl_unit.py -v
"""

import pytest

from leathercraft_dsl import (
    DslError,
    ExportDefinition,
    HolesOperation,
    OuterPathDefinition,
    PatternDocument,
    RegularPolygonDefinition,
    RoundedRegularPolygonDefinition,
    RectangleDefinition,
    RoundedRectangleDefinition,
    SingleHoleDefinition,
    StitchesOperation,
    compile_document,
    parse,
)
from leathercraft_svg import Polygon, Rectangle, RoundedRectangle, SvgDocument


# ===========================================================================
# Helpers
# ===========================================================================


def _parse(text: str) -> PatternDocument:
    return parse(text)


# ===========================================================================
# Parser — document-level commands
# ===========================================================================


class TestParsePattern:
    def test_name_is_captured(self):
        doc = _parse("pattern my_sleeve\nsize 100 80")
        assert doc.name == "my_sleeve"

    def test_name_none_if_missing(self):
        doc = _parse("size 100 80")
        assert doc.name is None


class TestParseSize:
    def test_width_and_height(self):
        doc = _parse("size 150 112")
        assert doc.width_mm == 150.0
        assert doc.height_mm == 112.0

    def test_float_values(self):
        doc = _parse("size 99.5 60.25")
        assert doc.width_mm == pytest.approx(99.5)
        assert doc.height_mm == pytest.approx(60.25)

    def test_missing_size_raises(self):
        with pytest.raises(DslError, match="missing required command 'size'"):
            compile_document(_parse("pattern x"))

    def test_unit_suffix_raises(self):
        with pytest.raises(DslError, match="units are not allowed"):
            _parse("size 150mm 112mm")


class TestParseLayer:
    def test_named_color(self):
        doc = _parse("size 10 10\nlayer cut red 0.12")
        assert doc.layers["cut"].color == "#ff0000"
        assert doc.layers["cut"].stroke_width == pytest.approx(0.12)
        assert doc.layers["cut"].dashed is False

    def test_hex_color(self):
        doc = _parse("size 10 10\nlayer cut #aa0000 0.1")
        assert doc.layers["cut"].color == "#aa0000"

    def test_dashed_layer(self):
        doc = _parse("size 10 10\nlayer guide gray 0.12 dashed")
        assert doc.layers["guide"].dashed is True

    def test_unknown_color_raises(self):
        with pytest.raises(DslError, match="Unknown color"):
            _parse("size 10 10\nlayer cut mauve 0.1")


class TestParseSymmetry:
    def test_short_form(self):
        doc = _parse("size 10 10\nsymmetry 75")
        assert doc.symmetry_axis_x == 75.0

    def test_verbose_form(self):
        doc = _parse("size 10 10\nsymmetry vertical x=75")
        assert doc.symmetry_axis_x == 75.0

    def test_none_by_default(self):
        doc = _parse("size 10 10")
        assert doc.symmetry_axis_x is None


# ===========================================================================
# Parser — shapes
# ===========================================================================


class TestParseRectangle:
    def test_basic(self):
        doc = _parse("size 100 60\nrectangle panel\n  at 10 10\n  size 80 40\nend")
        assert len(doc.shapes) == 1
        s = doc.shapes[0]
        assert isinstance(s, RectangleDefinition)
        assert s.id == "panel"
        assert s.x == 10.0
        assert s.y == 10.0
        assert s.width == 80.0
        assert s.height == 40.0
        assert s.layer == "cut"

    def test_custom_layer(self):
        doc = _parse("size 100 60\nrectangle panel\n  at 10 10\n  size 80 40\n  layer guide\nend")
        assert doc.shapes[0].layer == "guide"

    def test_missing_at_raises(self):
        with pytest.raises(DslError, match="missing 'at'"):
            _parse("size 100 60\nrectangle panel\n  size 80 40\nend")

    def test_missing_size_raises(self):
        with pytest.raises(DslError, match="missing 'size'"):
            _parse("size 100 60\nrectangle panel\n  at 10 10\nend")


class TestParseRoundedRectangle:
    def test_basic(self):
        doc = _parse("size 100 60\nrounded_rectangle pocket\n  at 5 5\n  size 90 50\n  radius 8\nend")
        s = doc.shapes[0]
        assert isinstance(s, RoundedRectangleDefinition)
        assert s.id == "pocket"
        assert s.radius == 8.0

    def test_zero_radius_raises(self):
        with pytest.raises(DslError, match="radius must be greater than 0"):
            _parse("size 100 60\nrounded_rectangle pocket\n  at 5 5\n  size 90 50\n  radius 0\nend")

    def test_missing_radius_raises(self):
        with pytest.raises(DslError, match="missing 'radius'"):
            _parse("size 100 60\nrounded_rectangle pocket\n  at 5 5\n  size 90 50\nend")


class TestParseOuter:
    def test_smooth_mirrored(self):
        text = (
            "size 150 112\n"
            "symmetry 75\n"
            "outer smooth mirrored\n"
            "  75 10\n"
            "  40 50\n"
            "  75 90\n"
            "end\n"
        )
        doc = _parse(text)
        s = doc.shapes[0]
        assert isinstance(s, OuterPathDefinition)
        assert s.smooth is True
        assert s.mirrored is True
        assert len(s.points) == 3
        assert s.points[0] == (75.0, 10.0)

    def test_straight_not_mirrored(self):
        text = "size 100 100\nouter straight\n  10 10\n  90 90\nend"
        doc = _parse(text)
        s = doc.shapes[0]
        assert s.smooth is False
        assert s.mirrored is False

    def test_empty_points_raises(self):
        with pytest.raises(DslError, match="no points"):
            _parse("size 100 100\nouter smooth\nend")


# ===========================================================================
# Parser — operations
# ===========================================================================


class TestParseStitches:
    def _base(self) -> str:
        return (
            "size 120 80\n"
            "rectangle panel\n  at 10 10\n  size 100 60\nend\n"
        )

    def test_source_stitches(self):
        doc = _parse(self._base() + "stitches\n  source panel\n  edges all\n  margin 4\n  spacing 5\n  length 3\nend")
        op = doc.operations[0]
        assert isinstance(op, StitchesOperation)
        assert op.source == "panel"
        assert op.edges == ["top", "right", "bottom", "left"]
        assert op.margin == 4.0
        assert op.spacing == 5.0
        assert op.length == 3.0

    def test_angle_default_zero(self):
        doc = _parse(self._base() + "stitches\n  source panel\n  margin 4\n  spacing 5\n  length 3\nend")
        assert doc.operations[0].angle == 0.0

    def test_angle_explicit(self):
        doc = _parse(self._base() + "stitches\n  source panel\n  margin 4\n  spacing 5\n  length 3\n  angle 45\nend")
        assert doc.operations[0].angle == 45.0

    def test_edges_except_top(self):
        doc = _parse(self._base() + "stitches\n  source panel\n  edges except_top\n  margin 4\n  spacing 5\n  length 3\nend")
        op = doc.operations[0]
        assert set(op.edges) == {"right", "bottom", "left"}

    def test_path_stitches(self):
        text = (
            "size 150 112\n"
            "symmetry 75\n"
            "stitches\n"
            "  margin 4\n"
            "  spacing 5\n"
            "  length 3\n"
            "  mirror\n"
            "  path\n"
            "    10 10\n"
            "    20 50\n"
            "    10 90\n"
            "  end\n"
            "end\n"
        )
        doc = _parse(text)
        op = doc.operations[0]
        assert op.source is None
        assert op.mirror is True
        assert len(op.path_points) == 3

    def test_unknown_source_raises(self):
        with pytest.raises(DslError, match="unknown source"):
            _parse(self._base() + "stitches\n  source nonexistent\n  margin 4\n  spacing 5\n  length 3\nend")

    def test_invalid_edge_raises(self):
        with pytest.raises(DslError, match="unknown edge"):
            _parse(self._base() + "stitches\n  source panel\n  edges lower\n  margin 4\n  spacing 5\n  length 3\nend")


class TestParseHoles:
    def _base(self) -> str:
        return (
            "size 120 80\n"
            "rectangle panel\n  at 10 10\n  size 100 60\nend\n"
        )

    def test_basic(self):
        doc = _parse(self._base() + "holes\n  source panel\n  edges all\n  margin 4\n  spacing 6\n  radius 1.2\nend")
        op = doc.operations[0]
        assert isinstance(op, HolesOperation)
        assert op.source == "panel"
        assert op.radius == pytest.approx(1.2)

    def test_zero_radius_raises(self):
        with pytest.raises(DslError, match="radius must be greater than 0"):
            _parse(self._base() + "holes\n  source panel\n  margin 4\n  spacing 6\n  radius 0\nend")

    def test_missing_source_raises(self):
        with pytest.raises(DslError, match="missing 'source'"):
            _parse(self._base() + "holes\n  margin 4\n  spacing 6\n  radius 1.2\nend")


class TestParseSingleHole:
    def test_absolute_position(self):
        doc = _parse("size 100 60\nhole pin\n  at 50 20\n  radius 1.5\nend")
        op = doc.operations[0]
        assert isinstance(op, SingleHoleDefinition)
        assert op.x == 50.0
        assert op.y == 20.0
        assert op.radius == pytest.approx(1.5)
        assert op.mirror is False

    def test_mirrored(self):
        doc = _parse("size 150 60\nsymmetry 75\nhole pin\n  mirror\n  x_from_center 30\n  y 20\n  radius 2\nend")
        op = doc.operations[0]
        assert op.mirror is True
        assert op.x_from_center == 30.0

    def test_mirrored_without_symmetry_still_parses(self):
        # Parser allows it; the DslError is raised during compile
        doc = _parse("size 150 60\nhole pin\n  mirror\n  x_from_center 30\n  y 20\n  radius 2\nend")
        assert doc.operations[0].mirror is True


class TestParseExport:
    def test_simple_export(self):
        doc = _parse("size 10 10\nexport my_pattern")
        assert len(doc.exports) == 1
        e = doc.exports[0]
        assert e.format is None
        assert e.filename == "my_pattern"

    def test_explicit_svg(self):
        doc = _parse("size 10 10\nexport svg output.svg")
        assert doc.exports[0].format == "svg"
        assert doc.exports[0].filename == "output.svg"

    def test_explicit_png(self):
        doc = _parse("size 10 10\nexport png output.png")
        assert doc.exports[0].format == "png"

    def test_unknown_format_raises(self):
        with pytest.raises(DslError, match="unknown export format"):
            _parse("size 10 10\nexport bmp output.bmp")


# ===========================================================================
# Parser — comments and whitespace
# ===========================================================================


class TestCommentsAndWhitespace:
    def test_hash_comment_ignored(self):
        doc = _parse("# This is a comment\nsize 100 80")
        assert doc.width_mm == 100.0

    def test_inline_comment(self):
        doc = _parse("size 100 80  # main canvas")
        assert doc.width_mm == 100.0

    def test_empty_lines_ignored(self):
        doc = _parse("\n\nsize 100 80\n\n")
        assert doc.width_mm == 100.0

    def test_indentation_optional(self):
        doc = _parse("size 100 60\nrectangle panel\nat 10 10\nsize 80 40\nend")
        assert doc.shapes[0].width == 80.0

    def test_missing_end_raises(self):
        with pytest.raises(DslError, match="missing 'end'"):
            _parse("size 100 60\nrectangle panel\n  at 10 10\n  size 80 40\n")


# ===========================================================================
# Parser — unknown keyword
# ===========================================================================


class TestUnknownKeyword:
    def test_raises(self):
        with pytest.raises(DslError, match="unknown keyword"):
            _parse("size 100 80\nfoobar something")


# ===========================================================================
# Compiler — output shape types
# ===========================================================================


class TestCompileRectangle:
    def test_creates_svg_document(self):
        doc = _parse("size 100 60\nrectangle panel\n  at 10 10\n  size 80 40\nend")
        svg = compile_document(doc)
        assert isinstance(svg, SvgDocument)

    def test_svg_contains_path(self):
        doc = _parse("size 100 60\nrectangle panel\n  at 10 10\n  size 80 40\nend")
        svg = compile_document(doc)
        output = svg.to_svg()
        assert "<path" in output

    def test_svg_dimensions(self):
        doc = _parse("size 100 60\nrectangle panel\n  at 10 10\n  size 80 40\nend")
        svg = compile_document(doc)
        output = svg.to_svg()
        assert 'width="100' in output
        assert 'height="60' in output


class TestCompileRoundedRectangle:
    def test_svg_contains_path(self):
        doc = _parse("size 100 60\nrounded_rectangle panel\n  at 10 10\n  size 80 40\n  radius 6\nend")
        svg = compile_document(doc)
        assert "<path" in svg.to_svg()


class TestCompileOuter:
    def test_mirrored_outer(self):
        text = (
            "size 150 112\n"
            "symmetry 75\n"
            "outer smooth mirrored\n"
            "  75 10\n"
            "  40 50\n"
            "  75 90\n"
            "end\n"
        )
        svg = compile_document(_parse(text))
        assert "<path" in svg.to_svg()

    def test_mirrored_without_symmetry_raises(self):
        text = (
            "size 150 112\n"
            "outer smooth mirrored\n"
            "  75 10\n"
            "  40 50\n"
            "  75 90\n"
            "end\n"
        )
        with pytest.raises(DslError, match="symmetry"):
            compile_document(_parse(text))


class TestCompileStitchesOnShape:
    def _doc(self, edges="all"):
        return _parse(
            f"size 120 80\n"
            f"rectangle panel\n  at 10 10\n  size 100 60\nend\n"
            f"stitches\n  source panel\n  edges {edges}\n  margin 4\n  spacing 5\n  length 3\nend"
        )

    def test_produces_lines(self):
        svg = compile_document(self._doc())
        output = svg.to_svg()
        assert "<line" in output

    def test_edges_subset(self):
        svg = compile_document(self._doc(edges="top bottom"))
        output = svg.to_svg()
        assert "<line" in output


class TestCompileHolesOnShape:
    def test_produces_circles(self):
        doc = _parse(
            "size 120 80\n"
            "rectangle panel\n  at 10 10\n  size 100 60\nend\n"
            "holes\n  source panel\n  edges all\n  margin 4\n  spacing 6\n  radius 1.2\nend"
        )
        svg = compile_document(doc)
        output = svg.to_svg()
        assert "<circle" in output


class TestCompileSingleHole:
    def test_absolute_hole(self):
        doc = _parse("size 100 60\nhole pin\n  at 50 30\n  radius 1.5\nend")
        svg = compile_document(doc)
        output = svg.to_svg()
        assert "<circle" in output

    def test_mirrored_hole_produces_two_circles(self):
        doc = _parse(
            "size 150 60\nsymmetry 75\n"
            "hole pin\n  mirror\n  x_from_center 30\n  y 20\n  radius 2\nend"
        )
        svg = compile_document(doc)
        output = svg.to_svg()
        assert output.count("<circle") == 2

    def test_mirrored_x_positions(self):
        doc = _parse(
            "size 150 60\nsymmetry 75\n"
            "hole pin\n  mirror\n  x_from_center 30\n  y 20\n  radius 2\nend"
        )
        svg = compile_document(doc)
        output = svg.to_svg()
        # cx=45 (75-30) and cx=105 (75+30)
        assert 'cx="45' in output
        assert 'cx="105' in output

    def test_mirrored_no_symmetry_raises(self):
        doc = _parse(
            "size 150 60\n"
            "hole pin\n  mirror\n  x_from_center 30\n  y 20\n  radius 2\nend"
        )
        with pytest.raises(DslError, match="no symmetry axis"):
            compile_document(doc)


class TestCompileCustomPathStitches:
    def test_no_path_raises(self):
        doc = _parse(
            "size 150 112\n"
            "stitches\n  margin 4\n  spacing 5\n  length 3\nend"
        )
        with pytest.raises(DslError, match="path"):
            compile_document(doc)

    def test_mirror_without_symmetry_raises(self):
        doc = _parse(
            "size 150 112\n"
            "stitches\n  margin 4\n  spacing 5\n  length 3\n  mirror\n"
            "  path\n    10 10\n    10 90\n  end\nend"
        )
        with pytest.raises(DslError, match="symmetry"):
            compile_document(doc)

    def test_produces_lines_with_mirror(self):
        doc = _parse(
            "size 150 112\n"
            "symmetry 75\n"
            "stitches\n  margin 4\n  spacing 5\n  length 3\n  mirror\n"
            "  path\n    10 10\n    10 90\n  end\nend"
        )
        svg = compile_document(doc)
        assert "<line" in svg.to_svg()


# ===========================================================================
# Compiler — default layers
# ===========================================================================


class TestDefaultLayers:
    def test_default_cut_is_red(self):
        doc = _parse("size 100 60\nrectangle panel\n  at 10 10\n  size 80 40\nend")
        svg = compile_document(doc)
        output = svg.to_svg()
        assert "#ff0000" in output

    def test_custom_layer_applied(self):
        doc = _parse(
            "size 100 60\n"
            "layer cut #aabbcc 0.2\n"
            "rectangle panel\n  at 10 10\n  size 80 40\nend"
        )
        svg = compile_document(doc)
        output = svg.to_svg()
        assert "#aabbcc" in output


# ===========================================================================
# Compiler — edge alias resolution
# ===========================================================================


class TestEdgeAliasResolution:
    def test_except_top_excludes_top(self):
        from leathercraft_dsl import _resolve_edges
        edges = _resolve_edges(["except_top"], lineno=1)
        assert "top" not in edges
        assert set(edges) == {"right", "bottom", "left"}

    def test_sides_is_left_right(self):
        from leathercraft_dsl import _resolve_edges
        edges = _resolve_edges(["sides"], lineno=1)
        assert set(edges) == {"left", "right"}

    def test_all_expands(self):
        from leathercraft_dsl import _resolve_edges
        edges = _resolve_edges(["all"], lineno=1)
        assert set(edges) == {"top", "right", "bottom", "left"}

    def test_deduplicated(self):
        from leathercraft_dsl import _resolve_edges
        edges = _resolve_edges(["top", "top", "bottom"], lineno=1)
        assert edges.count("top") == 1


# ===========================================================================
# Compiler — edge index conversion
# ===========================================================================


class TestEdgesToIndices:
    def test_all_returns_string(self):
        from leathercraft_dsl import _edges_to_indices
        result = _edges_to_indices(["top", "right", "bottom", "left"])
        assert result == "all"

    def test_partial_returns_list(self):
        from leathercraft_dsl import _edges_to_indices
        result = _edges_to_indices(["top", "bottom"])
        assert result == [0, 2]

    def test_right_only(self):
        from leathercraft_dsl import _edges_to_indices
        result = _edges_to_indices(["right"])
        assert result == [1]


# ===========================================================================
# Full round-trip integration tests
# ===========================================================================


class TestFullRoundTrip:
    def test_rectangle_panel_lcraft(self):
        text = """
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
"""
        doc = _parse(text)
        svg = compile_document(doc)
        output = svg.to_svg()
        assert "<path" in output
        assert "<line" in output

    def test_rounded_pocket_lcraft(self):
        text = """
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
"""
        doc = _parse(text)
        svg = compile_document(doc)
        output = svg.to_svg()
        assert "<path" in output
        assert "<line" in output

    def test_panel_with_holes_lcraft(self):
        text = """
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
"""
        doc = _parse(text)
        svg = compile_document(doc)
        output = svg.to_svg()
        assert "<circle" in output

    def test_lighter_sleeve_lcraft(self):
        text = """
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
  x_from_center 30
  y 21
  radius 2.2
end
"""
        doc = _parse(text)
        assert doc.name == "lighter_sleeve"
        assert doc.symmetry_axis_x == 75.0
        svg = compile_document(doc)
        output = svg.to_svg()
        # shape + stitches + 2 holes
        assert "<path" in output
        assert "<line" in output
        assert output.count("<circle") == 2


# ===========================================================================
# Parser — Circle
# ===========================================================================


class TestParseCircle:
    def test_basic(self):
        doc = _parse("size 100 100\ncircle ring\n  at 50 50\n  radius 30\nend")
        assert len(doc.shapes) == 1
        from leathercraft_dsl import CircleDefinition
        s = doc.shapes[0]
        assert isinstance(s, CircleDefinition)
        assert s.id == "ring"
        assert s.cx == 50.0
        assert s.cy == 50.0
        assert s.radius == 30.0
        assert s.layer == "cut"

    def test_custom_layer(self):
        doc = _parse("size 100 100\ncircle ring\n  at 50 50\n  radius 30\n  layer guide\nend")
        assert doc.shapes[0].layer == "guide"

    def test_missing_at_raises(self):
        with pytest.raises(DslError, match="missing 'at'"):
            _parse("size 100 100\ncircle ring\n  radius 30\nend")

    def test_missing_radius_raises(self):
        with pytest.raises(DslError, match="missing 'radius'"):
            _parse("size 100 100\ncircle ring\n  at 50 50\nend")

    def test_zero_radius_raises(self):
        with pytest.raises(DslError, match="radius must be greater than 0"):
            _parse("size 100 100\ncircle ring\n  at 50 50\n  radius 0\nend")

    def test_circle_registered_as_source(self):
        doc = _parse(
            "size 100 100\ncircle ring\n  at 50 50\n  radius 30\nend\n"
            "holes\n  source ring\n  margin 5\n  spacing 8\n  radius 1.2\nend"
        )
        assert len(doc.operations) == 1


# ===========================================================================
# Parser — Triangle
# ===========================================================================


class TestParseTriangle:
    def test_point_form(self):
        doc = _parse(
            "size 120 90\ntriangle tri\n"
            "  p1 60 10\n  p2 110 80\n  p3 10 80\nend"
        )
        from leathercraft_dsl import TriangleDefinition
        s = doc.shapes[0]
        assert isinstance(s, TriangleDefinition)
        assert s.id == "tri"
        assert s.p1 == (60.0, 10.0)
        assert s.p2 == (110.0, 80.0)
        assert s.p3 == (10.0, 80.0)

    def test_box_form(self):
        doc = _parse("size 120 90\ntriangle tri\n  at 10 10\n  size 80 60\nend")
        from leathercraft_dsl import TriangleDefinition
        s = doc.shapes[0]
        assert isinstance(s, TriangleDefinition)
        # from_box: p1=top-center, p2=bottom-right, p3=bottom-left
        assert s.p1 == pytest.approx((50.0, 10.0))
        assert s.p2 == pytest.approx((90.0, 70.0))
        assert s.p3 == pytest.approx((10.0, 70.0))

    def test_custom_layer(self):
        doc = _parse(
            "size 120 90\ntriangle tri\n"
            "  p1 60 10\n  p2 110 80\n  p3 10 80\n  layer guide\nend"
        )
        assert doc.shapes[0].layer == "guide"

    def test_missing_points_and_box_raises(self):
        with pytest.raises(DslError, match="p1/p2/p3.*at.*size"):
            _parse("size 120 90\ntriangle tri\n  p1 60 10\nend")

    def test_registered_as_source(self):
        doc = _parse(
            "size 120 90\ntriangle tri\n  at 10 10\n  size 80 60\nend\n"
            "stitches\n  source tri\n  margin 5\n  spacing 8\n  length 3\nend"
        )
        assert doc.operations[0].source == "tri"


# ===========================================================================
# Parser — RoundedTriangle
# ===========================================================================


class TestParseRoundedTriangle:
    def test_point_form(self):
        doc = _parse(
            "size 130 100\nrounded_triangle rtri\n"
            "  p1 65 10\n  p2 120 90\n  p3 10 90\n  radius 12\nend"
        )
        from leathercraft_dsl import RoundedTriangleDefinition
        s = doc.shapes[0]
        assert isinstance(s, RoundedTriangleDefinition)
        assert s.radius == 12.0

    def test_box_form(self):
        doc = _parse(
            "size 130 100\nrounded_triangle rtri\n"
            "  at 10 10\n  size 100 80\n  radius 10\nend"
        )
        from leathercraft_dsl import RoundedTriangleDefinition
        s = doc.shapes[0]
        assert isinstance(s, RoundedTriangleDefinition)
        assert s.p1 == pytest.approx((60.0, 10.0))

    def test_missing_radius_raises(self):
        with pytest.raises(DslError, match="missing 'radius'"):
            _parse(
                "size 130 100\nrounded_triangle rtri\n"
                "  p1 65 10\n  p2 120 90\n  p3 10 90\nend"
            )

    def test_zero_radius_raises(self):
        with pytest.raises(DslError, match="radius must be greater than 0"):
            _parse(
                "size 130 100\nrounded_triangle rtri\n"
                "  p1 65 10\n  p2 120 90\n  p3 10 90\n  radius 0\nend"
            )


# ===========================================================================
# Parser — numeric edge indices
# ===========================================================================


class TestNumericEdgeIndices:
    def test_numeric_indices_accepted(self):
        from leathercraft_dsl import _resolve_edges
        edges = _resolve_edges(["0", "2"], lineno=1)
        assert edges == ["0", "2"]

    def test_numeric_and_all_separately(self):
        doc = _parse(
            "size 120 90\ntriangle tri\n  at 10 10\n  size 80 60\nend\n"
            "holes\n  source tri\n  edges 0 2\n  margin 5\n  spacing 8\n  radius 1.2\nend"
        )
        from leathercraft_dsl import HolesOperation
        op = doc.operations[0]
        assert op.edges == ["0", "2"]

    def test_edges_to_indices_numeric(self):
        from leathercraft_dsl import _edges_to_indices
        assert _edges_to_indices(["0", "2"]) == [0, 2]

    def test_edges_to_indices_all_numeric(self):
        from leathercraft_dsl import _edges_to_indices
        assert _edges_to_indices(["0", "1", "2"]) == [0, 1, 2]

    def test_invalid_non_numeric_non_named_raises(self):
        with pytest.raises(DslError, match="unknown edge"):
            _parse(
                "size 120 90\ntriangle tri\n  at 10 10\n  size 80 60\nend\n"
                "holes\n  source tri\n  edges lower\n  margin 5\n  spacing 8\n  radius 1.2\nend"
            )


# ===========================================================================
# Parser — rounded_path flag
# ===========================================================================


class TestRoundedPathFlag:
    def _rtri_base(self) -> str:
        return (
            "size 130 100\n"
            "rounded_triangle rtri\n"
            "  p1 65 10\n  p2 120 90\n  p3 10 90\n  radius 12\nend\n"
        )

    def test_rounded_path_in_stitches(self):
        doc = _parse(
            self._rtri_base()
            + "stitches\n  source rtri\n  rounded_path\n  margin 6\n  spacing 8\n  length 3\nend"
        )
        assert doc.operations[0].rounded_path is True

    def test_rounded_path_default_false_stitches(self):
        doc = _parse(
            self._rtri_base()
            + "stitches\n  source rtri\n  margin 6\n  spacing 8\n  length 3\nend"
        )
        assert doc.operations[0].rounded_path is False

    def test_rounded_path_in_holes(self):
        doc = _parse(
            self._rtri_base()
            + "holes\n  source rtri\n  rounded_path\n  margin 6\n  spacing 8\n  radius 1.5\nend"
        )
        assert doc.operations[0].rounded_path is True

    def test_rounded_path_default_false_holes(self):
        doc = _parse(
            self._rtri_base()
            + "holes\n  source rtri\n  margin 6\n  spacing 8\n  radius 1.5\nend"
        )
        assert doc.operations[0].rounded_path is False


# ===========================================================================
# Compiler — new shapes produce correct SVG
# ===========================================================================


class TestCompileCircle:
    def test_produces_path(self):
        doc = _parse("size 100 100\ncircle ring\n  at 50 50\n  radius 30\nend")
        output = compile_document(doc).to_svg()
        assert "<path" in output   # Circle rendered as arc path

    def test_holes_produce_circles(self):
        doc = _parse(
            "size 100 100\ncircle ring\n  at 50 50\n  radius 30\nend\n"
            "holes\n  source ring\n  margin 7\n  spacing 8\n  radius 1.5\nend"
        )
        output = compile_document(doc).to_svg()
        assert "<circle" in output

    def test_stitches_produce_lines(self):
        doc = _parse(
            "size 100 100\ncircle ring\n  at 50 50\n  radius 30\nend\n"
            "stitches\n  source ring\n  margin 7\n  spacing 8\n  length 3.5\nend"
        )
        output = compile_document(doc).to_svg()
        assert "<line" in output


class TestCompileTriangle:
    def test_point_form_produces_path(self):
        doc = _parse(
            "size 120 90\ntriangle tri\n"
            "  p1 60 10\n  p2 110 80\n  p3 10 80\nend"
        )
        output = compile_document(doc).to_svg()
        assert "<path" in output

    def test_box_form_produces_path(self):
        doc = _parse("size 120 90\ntriangle tri\n  at 10 10\n  size 80 60\nend")
        output = compile_document(doc).to_svg()
        assert "<path" in output

    def test_holes_all_edges(self):
        doc = _parse(
            "size 120 90\ntriangle tri\n  at 10 10\n  size 80 60\nend\n"
            "holes\n  source tri\n  edges all\n  margin 6\n  spacing 8\n  radius 1.2\nend"
        )
        output = compile_document(doc).to_svg()
        assert "<circle" in output

    def test_holes_numeric_edges(self):
        doc = _parse(
            "size 120 90\ntriangle tri\n  at 10 10\n  size 80 60\nend\n"
            "holes\n  source tri\n  edges 0 2\n  margin 6\n  spacing 8\n  radius 1.2\nend"
        )
        output = compile_document(doc).to_svg()
        assert "<circle" in output

    def test_stitches_numeric_edges(self):
        doc = _parse(
            "size 120 90\ntriangle tri\n  at 10 10\n  size 80 60\nend\n"
            "stitches\n  source tri\n  edges 0 1\n  margin 6\n  spacing 8\n  length 3\nend"
        )
        output = compile_document(doc).to_svg()
        assert "<line" in output


class TestCompileRoundedTriangle:
    def test_produces_path(self):
        doc = _parse(
            "size 130 100\nrounded_triangle rtri\n"
            "  p1 65 10\n  p2 120 90\n  p3 10 90\n  radius 12\nend"
        )
        output = compile_document(doc).to_svg()
        assert "<path" in output

    def test_holes_with_rounded_path(self):
        doc = _parse(
            "size 130 100\nrounded_triangle rtri\n"
            "  p1 65 10\n  p2 120 90\n  p3 10 90\n  radius 12\nend\n"
            "holes\n  source rtri\n  rounded_path\n  margin 6\n  spacing 8\n  radius 1.5\nend"
        )
        output = compile_document(doc).to_svg()
        assert "<circle" in output

    def test_stitches_with_rounded_path(self):
        doc = _parse(
            "size 130 100\nrounded_triangle rtri\n"
            "  p1 65 10\n  p2 120 90\n  p3 10 90\n  radius 12\nend\n"
            "stitches\n  source rtri\n  rounded_path\n  margin 6\n  spacing 8\n  length 3.5\nend"
        )
        output = compile_document(doc).to_svg()
        assert "<line" in output

    def test_stitches_numeric_edges(self):
        doc = _parse(
            "size 130 100\nrounded_triangle rtri\n"
            "  p1 65 10\n  p2 120 90\n  p3 10 90\n  radius 12\nend\n"
            "stitches\n  source rtri\n  edges 0 2\n  margin 6\n  spacing 8\n  length 3\nend"
        )
        output = compile_document(doc).to_svg()
        assert "<line" in output


# ===========================================================================
# Full round-trip — new shapes
# ===========================================================================


class TestFullRoundTripNewShapes:
    def test_circle_with_holes(self):
        text = """
size 100 100

circle ring
  at 50 50
  radius 35
end

holes
  source ring
  margin 7
  spacing 8
  radius 1.5
end
"""
        svg = compile_document(_parse(text))
        output = svg.to_svg()
        assert "<path" in output
        assert "<circle" in output

    def test_triangle_stitch_all_edges(self):
        text = """
size 120 90

triangle tri
  p1 60 10
  p2 110 80
  p3 10 80
end

stitches
  source tri
  edges all
  margin 6
  spacing 8
  length 3.5
  angle 45
end
"""
        svg = compile_document(_parse(text))
        output = svg.to_svg()
        assert "<path" in output
        assert "<line" in output

    def test_triangle_holes_partial_edges(self):
        text = """
size 120 90

triangle tri
  at 10 10
  size 80 60
end

holes
  source tri
  edges 0 2
  margin 6
  spacing 8
  radius 1.2
end
"""
        svg = compile_document(_parse(text))
        assert "<circle" in svg.to_svg()

    def test_rounded_triangle_rounded_path_holes(self):
        text = """
size 130 100

rounded_triangle rtri
  p1 65 10
  p2 120 90
  p3 10 90
  radius 12
end

holes
  source rtri
  rounded_path
  margin 6
  spacing 8
  radius 1.5
end
"""
        svg = compile_document(_parse(text))
        assert "<circle" in svg.to_svg()

    def test_rounded_triangle_rounded_path_stitch(self):
        text = """
size 130 100

rounded_triangle rtri
  p1 65 10
  p2 120 90
  p3 10 90
  radius 12
end

stitches
  source rtri
  rounded_path
  margin 6
  spacing 8
  length 3.5
end
"""
        svg = compile_document(_parse(text))
        assert "<line" in svg.to_svg()

    def test_multiple_shapes_in_one_document(self):
        text = """
size 300 120

rectangle rect
  at 10 10
  size 60 40
end

circle ring
  at 120 30
  radius 25
end

triangle tri
  at 170 10
  size 60 40
end

rounded_triangle rtri
  at 250 10
  size 60 40
  radius 8
end

holes
  source rect
  margin 4
  spacing 8
  radius 1.0
end

holes
  source ring
  margin 6
  spacing 8
  radius 1.5
end

holes
  source tri
  edges 0 1
  margin 5
  spacing 8
  radius 1.2
end

holes
  source rtri
  rounded_path
  margin 5
  spacing 8
  radius 1.2
end
"""
        svg = compile_document(_parse(text))
        output = svg.to_svg()
        assert "<path" in output
        assert "<circle" in output


# ===========================================================================
# Parser — Stadium
# ===========================================================================


class TestParseStadium:
    def test_basic(self):
        doc = _parse("size 140 60\nstadium fob\n  at 10 15\n  size 120 30\nend")
        from leathercraft_dsl import StadiumDefinition
        s = doc.shapes[0]
        assert isinstance(s, StadiumDefinition)
        assert s.id == "fob"
        assert s.x == 10.0
        assert s.y == 15.0
        assert s.width == 120.0
        assert s.height == 30.0
        assert s.layer == "cut"

    def test_custom_layer(self):
        doc = _parse("size 140 60\nstadium fob\n  at 10 15\n  size 120 30\n  layer guide\nend")
        assert doc.shapes[0].layer == "guide"

    def test_missing_at_raises(self):
        with pytest.raises(DslError, match="missing 'at'"):
            _parse("size 140 60\nstadium fob\n  size 120 30\nend")

    def test_missing_size_raises(self):
        with pytest.raises(DslError, match="missing 'size'"):
            _parse("size 140 60\nstadium fob\n  at 10 15\nend")

    def test_zero_size_raises(self):
        with pytest.raises(DslError, match="size must be greater than 0"):
            _parse("size 140 60\nstadium fob\n  at 10 15\n  size 0 30\nend")

    def test_missing_id_raises(self):
        with pytest.raises(DslError, match="requires an id"):
            _parse("size 140 60\nstadium\n  at 10 15\n  size 120 30\nend")

    def test_registered_as_source(self):
        doc = _parse(
            "size 140 60\nstadium fob\n  at 10 15\n  size 120 30\nend\n"
            "stitches\n  source fob\n  margin 4\n  spacing 5\n  length 3\nend"
        )
        assert len(doc.operations) == 1


# ===========================================================================
# Compiler — Stadium
# ===========================================================================


class TestCompileStadium:
    def test_produces_arc_path(self):
        doc = _parse("size 140 60\nstadium fob\n  at 10 15\n  size 120 30\nend")
        output = compile_document(doc).to_svg()
        assert "<path" in output
        assert "A 15.000 15.000" in output  # semicircular caps

    def test_stitches_produce_lines(self):
        doc = _parse(
            "size 140 60\nstadium fob\n  at 10 15\n  size 120 30\nend\n"
            "stitches\n  source fob\n  margin 4\n  spacing 5\n  length 3\nend"
        )
        output = compile_document(doc).to_svg()
        assert "<line" in output

    def test_holes_produce_circles(self):
        doc = _parse(
            "size 140 60\nstadium fob\n  at 10 15\n  size 120 30\nend\n"
            "holes\n  source fob\n  margin 8\n  spacing 10\n  radius 1.5\nend"
        )
        output = compile_document(doc).to_svg()
        assert "<circle" in output

    def test_vertical_stadium(self):
        doc = _parse(
            "size 60 140\nstadium tag\n  at 15 10\n  size 30 120\nend\n"
            "stitches\n  source tag\n  margin 4\n  spacing 5\n  length 3\nend"
        )
        output = compile_document(doc).to_svg()
        assert "A 15.000 15.000" in output
        assert "<line" in output


# ===========================================================================
# Parser — Ellipse
# ===========================================================================


class TestParseEllipse:
    def test_rx_ry_form(self):
        doc = _parse("size 130 90\nellipse oval\n  at 65 45\n  rx 55\n  ry 35\nend")
        from leathercraft_dsl import EllipseDefinition
        s = doc.shapes[0]
        assert isinstance(s, EllipseDefinition)
        assert s.id == "oval"
        assert s.cx == 65.0
        assert s.cy == 45.0
        assert s.rx == 55.0
        assert s.ry == 35.0
        assert s.layer == "cut"

    def test_size_form(self):
        doc = _parse("size 130 90\nellipse oval\n  at 65 45\n  size 110 70\nend")
        s = doc.shapes[0]
        assert s.rx == 55.0
        assert s.ry == 35.0

    def test_custom_layer(self):
        doc = _parse("size 130 90\nellipse oval\n  at 65 45\n  rx 55\n  ry 35\n  layer guide\nend")
        assert doc.shapes[0].layer == "guide"

    def test_missing_at_raises(self):
        with pytest.raises(DslError, match="missing 'at'"):
            _parse("size 130 90\nellipse oval\n  rx 55\n  ry 35\nend")

    def test_missing_radii_raises(self):
        with pytest.raises(DslError, match="needs either 'rx' \\+ 'ry' or 'size'"):
            _parse("size 130 90\nellipse oval\n  at 65 45\nend")

    def test_zero_radius_raises(self):
        with pytest.raises(DslError, match="radii must be greater than 0"):
            _parse("size 130 90\nellipse oval\n  at 65 45\n  rx 0\n  ry 35\nend")

    def test_missing_id_raises(self):
        with pytest.raises(DslError, match="requires an id"):
            _parse("size 130 90\nellipse\n  at 65 45\n  rx 55\n  ry 35\nend")

    def test_registered_as_source(self):
        doc = _parse(
            "size 130 90\nellipse oval\n  at 65 45\n  rx 55\n  ry 35\nend\n"
            "stitches\n  source oval\n  margin 5\n  spacing 6\n  length 3\nend"
        )
        assert len(doc.operations) == 1


# ===========================================================================
# Compiler — Ellipse
# ===========================================================================


class TestCompileEllipse:
    def test_produces_arc_path(self):
        doc = _parse("size 130 90\nellipse oval\n  at 65 45\n  rx 55\n  ry 35\nend")
        output = compile_document(doc).to_svg()
        assert "<path" in output
        assert "A 55.000 35.000" in output

    def test_stitches_produce_lines(self):
        doc = _parse(
            "size 130 90\nellipse oval\n  at 65 45\n  rx 55\n  ry 35\nend\n"
            "stitches\n  source oval\n  margin 5\n  spacing 6\n  length 3\nend"
        )
        output = compile_document(doc).to_svg()
        assert "<line" in output

    def test_holes_produce_circles(self):
        doc = _parse(
            "size 130 90\nellipse oval\n  at 65 45\n  rx 55\n  ry 35\nend\n"
            "holes\n  source oval\n  margin 8\n  spacing 10\n  radius 1.5\nend"
        )
        output = compile_document(doc).to_svg()
        assert "<circle" in output

    def test_size_form_compiles(self):
        doc = _parse("size 130 90\nellipse oval\n  at 65 45\n  size 110 70\nend")
        output = compile_document(doc).to_svg()
        assert "A 55.000 35.000" in output


# ===========================================================================
# Parser — Per-corner rounded rectangle
# ===========================================================================


class TestParsePerCornerRoundedRectangle:
    def test_per_corner_only(self):
        doc = _parse(
            "size 120 90\nrounded_rectangle card\n  at 10 10\n  size 100 70\n"
            "  radius_tl 15\n  radius_tr 15\nend"
        )
        s = doc.shapes[0]
        assert s.radius == 0.0
        assert s.radius_tl == 15.0
        assert s.radius_tr == 15.0
        assert s.radius_br == 0.0   # unspecified per-corner defaults to sharp
        assert s.radius_bl == 0.0

    def test_uniform_plus_override(self):
        doc = _parse(
            "size 120 90\nrounded_rectangle card\n  at 10 10\n  size 100 70\n"
            "  radius 8\n  radius_bl 0\nend"
        )
        s = doc.shapes[0]
        assert s.radius == 8.0
        assert s.radius_bl == 0.0
        assert s.radius_tl is None   # falls back to uniform radius

    def test_uniform_only_unchanged(self):
        doc = _parse(
            "size 120 90\nrounded_rectangle card\n  at 10 10\n  size 100 70\n  radius 8\nend"
        )
        s = doc.shapes[0]
        assert s.radius == 8.0
        assert s.radius_tl is None

    def test_missing_radius_and_corners_raises(self):
        with pytest.raises(DslError, match="missing 'radius'"):
            _parse("size 120 90\nrounded_rectangle card\n  at 10 10\n  size 100 70\nend")

    def test_negative_corner_raises(self):
        with pytest.raises(DslError, match="radius_tl must be >= 0"):
            _parse(
                "size 120 90\nrounded_rectangle card\n  at 10 10\n  size 100 70\n"
                "  radius_tl -3\nend"
            )


class TestCompilePerCornerRoundedRectangle:
    def test_sharp_bottom_has_two_q_curves(self):
        doc = _parse(
            "size 120 90\nrounded_rectangle card\n  at 10 10\n  size 100 70\n"
            "  radius_tl 15\n  radius_tr 15\nend"
        )
        output = compile_document(doc).to_svg()
        # Only the two rounded top corners produce Q curves
        cut_path = [l for l in output.splitlines() if "<path" in l][0]
        assert cut_path.count("Q") == 2

    def test_stitches_compile(self):
        doc = _parse(
            "size 120 90\nrounded_rectangle card\n  at 10 10\n  size 100 70\n"
            "  radius_tl 15\n  radius_tr 15\nend\n"
            "stitches\n  source card\n  margin 5\n  spacing 6\n  length 3\nend"
        )
        assert "<line" in compile_document(doc).to_svg()

    def test_holes_compile(self):
        doc = _parse(
            "size 120 90\nrounded_rectangle card\n  at 10 10\n  size 100 70\n"
            "  radius 8\n  radius_br 0\nend\n"
            "holes\n  source card\n  margin 5\n  spacing 8\n  radius 1.2\nend"
        )
        assert "<circle" in compile_document(doc).to_svg()


# ===========================================================================
# Parser / Compiler — Regular polygon
# ===========================================================================


class TestParseRegularPolygon:
    def test_basic(self):
        doc = _parse(
            "size 120 120\nregular_polygon hex\n  at 60 60\n  radius 40\n  sides 6\nend"
        )
        s = doc.shapes[0]
        assert isinstance(s, RegularPolygonDefinition)
        assert s.id == "hex"
        assert s.cx == 60.0
        assert s.cy == 60.0
        assert s.radius == 40.0
        assert s.sides == 6
        assert s.rotation == -90.0

    def test_rotation_and_layer(self):
        doc = _parse(
            "size 120 120\nregular_polygon medallion\n  at 60 60\n  radius 35\n  sides 8\n"
            "  rotation 22.5\n  layer guide\nend"
        )
        s = doc.shapes[0]
        assert s.rotation == 22.5
        assert s.layer == "guide"

    def test_missing_sides_raises(self):
        with pytest.raises(DslError, match="missing 'sides'"):
            _parse("size 120 120\nregular_polygon hex\n  at 60 60\n  radius 40\nend")

    def test_non_integer_sides_raises(self):
        with pytest.raises(DslError, match="sides must be a whole number"):
            _parse("size 120 120\nregular_polygon bad\n  at 60 60\n  radius 40\n  sides 6.5\nend")

    def test_invalid_sides_raises(self):
        with pytest.raises(DslError, match="sides must be at least 3"):
            _parse("size 120 120\nregular_polygon bad\n  at 60 60\n  radius 40\n  sides 2\nend")

    def test_zero_radius_raises(self):
        with pytest.raises(DslError, match="radius must be greater than 0"):
            _parse("size 120 120\nregular_polygon bad\n  at 60 60\n  radius 0\n  sides 6\nend")

    def test_registered_as_source(self):
        doc = _parse(
            "size 120 120\nregular_polygon hex\n  at 60 60\n  radius 40\n  sides 6\nend\n"
            "holes\n  source hex\n  margin 5\n  spacing 8\n  radius 1.2\nend"
        )
        assert len(doc.operations) == 1


class TestCompileRegularPolygon:
    def test_shape_compiles_to_path(self):
        doc = _parse(
            "size 120 120\nregular_polygon hex\n  at 60 60\n  radius 40\n  sides 6\nend"
        )
        output = compile_document(doc).to_svg()
        assert "<path" in output

    def test_stitches_compile(self):
        doc = _parse(
            "size 120 120\nregular_polygon hex\n  at 60 60\n  radius 40\n  sides 6\nend\n"
            "stitches\n  source hex\n  edges 0 1 2\n  margin 5\n  spacing 8\n  length 3\nend"
        )
        assert "<line" in compile_document(doc).to_svg()

    def test_holes_compile(self):
        doc = _parse(
            "size 120 120\nregular_polygon oct\n  at 60 60\n  radius 38\n  sides 8\n  rotation 22.5\nend\n"
            "holes\n  source oct\n  edges all\n  margin 5\n  spacing 8\n  radius 1.2\nend"
        )
        assert "<circle" in compile_document(doc).to_svg()


# ===========================================================================
# Parser / Compiler — Rounded regular polygon
# ===========================================================================


class TestParseRoundedRegularPolygon:
    def test_basic_uniform_radius(self):
        doc = _parse(
            "size 120 120\nrounded_regular_polygon hex\n  at 60 60\n  radius 40\n  corner_radius 6\n  sides 6\nend"
        )
        s = doc.shapes[0]
        assert isinstance(s, RoundedRegularPolygonDefinition)
        assert s.radius == 40.0
        assert s.corner_radius == 6.0
        assert s.sides == 6
        assert s.corner_overrides == {}

    def test_selected_corner_overrides(self):
        doc = _parse(
            "size 120 120\nrounded_regular_polygon oct\n  at 60 60\n  radius 36\n  sides 8\n"
            "  corner_radius_0 0\n  corner_radius_1 4\n  corner_radius_5 7\nend"
        )
        s = doc.shapes[0]
        assert s.radius == 36.0
        assert s.corner_radius == 0.0
        assert s.corner_overrides == {0: 0.0, 1: 4.0, 5: 7.0}

    def test_rotation_and_layer(self):
        doc = _parse(
            "size 120 120\nrounded_regular_polygon oct\n  at 60 60\n  radius 35\n  corner_radius 5\n  sides 8\n"
            "  rotation 22.5\n  layer guide\nend"
        )
        s = doc.shapes[0]
        assert s.rotation == 22.5
        assert s.layer == "guide"

    def test_missing_corner_radius_and_overrides_raises(self):
        with pytest.raises(DslError, match="missing 'corner_radius'"):
            _parse("size 120 120\nrounded_regular_polygon hex\n  at 60 60\n  radius 40\n  sides 6\nend")

    def test_missing_outer_radius_raises(self):
        with pytest.raises(DslError, match="missing 'radius'"):
            _parse("size 120 120\nrounded_regular_polygon hex\n  at 60 60\n  corner_radius 6\n  sides 6\nend")

    def test_negative_override_raises(self):
        with pytest.raises(DslError, match="corner_radius_2 must be >= 0"):
            _parse(
                "size 120 120\nrounded_regular_polygon hex\n  at 60 60\n  radius 40\n  sides 6\n  corner_radius_2 -1\nend"
            )

    def test_out_of_range_override_raises(self):
        with pytest.raises(DslError, match="corner_radius_6 is out of range"):
            _parse(
                "size 120 120\nrounded_regular_polygon hex\n  at 60 60\n  radius 40\n  corner_radius 5\n  sides 6\n  corner_radius_6 2\nend"
            )


class TestCompileRoundedRegularPolygon:
    def test_shape_compiles_to_curved_path(self):
        doc = _parse(
            "size 120 120\nrounded_regular_polygon hex\n  at 60 60\n  radius 40\n  corner_radius 6\n  sides 6\nend"
        )
        output = compile_document(doc).to_svg()
        assert "<path" in output
        assert "Q" in output

    def test_stitches_compile(self):
        doc = _parse(
            "size 120 120\nrounded_regular_polygon hex\n  at 60 60\n  radius 40\n  corner_radius 6\n  sides 6\nend\n"
            "stitches\n  source hex\n  margin 5\n  spacing 8\n  length 3\nend"
        )
        assert "<line" in compile_document(doc).to_svg()

    def test_holes_compile(self):
        doc = _parse(
            "size 120 120\nrounded_regular_polygon oct\n  at 60 60\n  radius 38\n  sides 8\n"
            "  corner_radius_1 5\n  corner_radius_2 5\n  corner_radius_3 5\nend\n"
            "holes\n  source oct\n  margin 5\n  spacing 8\n  radius 1.2\nend"
        )
        assert "<circle" in compile_document(doc).to_svg()


# ===========================================================================
# Parser — Arc
# ===========================================================================


class TestParseArc:
    def test_wedge(self):
        doc = _parse(
            "size 130 80\narc fan\n  at 65 70\n  radius 55\n"
            "  from_angle 180\n  to_angle 360\nend"
        )
        from leathercraft_dsl import ArcDefinition
        s = doc.shapes[0]
        assert isinstance(s, ArcDefinition)
        assert s.id == "fan"
        assert s.cx == 65.0
        assert s.cy == 70.0
        assert s.radius == 55.0
        assert s.start_angle == 180.0
        assert s.end_angle == 360.0
        assert s.inner_radius == 0.0
        assert s.layer == "cut"

    def test_ring_segment(self):
        doc = _parse(
            "size 130 80\narc ring\n  at 65 70\n  radius 55\n  inner_radius 30\n"
            "  from_angle 180\n  to_angle 360\nend"
        )
        assert doc.shapes[0].inner_radius == 30.0

    def test_custom_layer(self):
        doc = _parse(
            "size 130 80\narc fan\n  at 65 70\n  radius 55\n"
            "  from_angle 0\n  to_angle 90\n  layer guide\nend"
        )
        assert doc.shapes[0].layer == "guide"

    def test_missing_at_raises(self):
        with pytest.raises(DslError, match="missing 'at'"):
            _parse("size 130 80\narc fan\n  radius 55\n  from_angle 0\n  to_angle 90\nend")

    def test_missing_from_angle_raises(self):
        with pytest.raises(DslError, match="missing 'from_angle'"):
            _parse("size 130 80\narc fan\n  at 65 70\n  radius 55\n  to_angle 90\nend")

    def test_missing_to_angle_raises(self):
        with pytest.raises(DslError, match="missing 'to_angle'"):
            _parse("size 130 80\narc fan\n  at 65 70\n  radius 55\n  from_angle 0\nend")

    def test_zero_radius_raises(self):
        with pytest.raises(DslError, match="radius must be greater than 0"):
            _parse("size 130 80\narc fan\n  at 65 70\n  radius 0\n  from_angle 0\n  to_angle 90\nend")

    def test_inner_radius_too_large_raises(self):
        with pytest.raises(DslError, match="inner_radius must be smaller than radius"):
            _parse(
                "size 130 80\narc fan\n  at 65 70\n  radius 30\n  inner_radius 40\n"
                "  from_angle 0\n  to_angle 90\nend"
            )

    def test_missing_id_raises(self):
        with pytest.raises(DslError, match="requires an id"):
            _parse("size 130 80\narc\n  at 65 70\n  radius 55\n  from_angle 0\n  to_angle 90\nend")

    def test_registered_as_source(self):
        doc = _parse(
            "size 130 80\narc fan\n  at 65 70\n  radius 55\n  from_angle 180\n  to_angle 360\nend\n"
            "stitches\n  source fan\n  margin 5\n  spacing 6\n  length 3\nend"
        )
        assert len(doc.operations) == 1


# ===========================================================================
# Compiler — Arc
# ===========================================================================


class TestCompileArc:
    def test_wedge_produces_arc_path(self):
        doc = _parse(
            "size 130 80\narc fan\n  at 65 70\n  radius 55\n  from_angle 180\n  to_angle 360\nend"
        )
        output = compile_document(doc).to_svg()
        assert "A 55.000 55.000" in output

    def test_ring_segment_has_two_arcs(self):
        doc = _parse(
            "size 130 80\narc ring\n  at 65 70\n  radius 55\n  inner_radius 30\n"
            "  from_angle 180\n  to_angle 360\nend"
        )
        output = compile_document(doc).to_svg()
        assert "A 55.000 55.000" in output
        assert "A 30.000 30.000" in output

    def test_stitches_produce_lines(self):
        doc = _parse(
            "size 130 80\narc fan\n  at 65 70\n  radius 55\n  from_angle 180\n  to_angle 360\nend\n"
            "stitches\n  source fan\n  margin 5\n  spacing 6\n  length 3\nend"
        )
        assert "<line" in compile_document(doc).to_svg()

    def test_holes_produce_circles(self):
        doc = _parse(
            "size 130 80\narc fan\n  at 65 70\n  radius 55\n  inner_radius 30\n"
            "  from_angle 180\n  to_angle 360\nend\n"
            "holes\n  source fan\n  margin 6\n  spacing 8\n  radius 1.2\nend"
        )
        assert "<circle" in compile_document(doc).to_svg()


# ===========================================================================
# Variables and numeric expressions
# ===========================================================================


class TestVariableAssignment:
    def test_basic_replacement(self):
        doc = _parse("width = 120\nheight = 80\nsize width height")
        assert doc.width_mm == 120.0
        assert doc.height_mm == 80.0

    def test_float_values(self):
        doc = _parse("w = 112.5\nsize w 80")
        assert doc.width_mm == 112.5

    def test_variable_referencing_variable(self):
        doc = _parse("width = 150\naxis = width / 2\nsize width 100\nsymmetry axis")
        assert doc.symmetry_axis_x == 75.0

    def test_comment_after_assignment(self):
        doc = _parse("width = 150  # document width\nsize width 100")
        assert doc.width_mm == 150.0


class TestExpressionArithmetic:
    def test_subtraction_in_size(self):
        doc = _parse(
            "width = 120\nmargin = 10\nsize width 80\n"
            "rectangle panel\n  at margin margin\n  size width - 2 * margin, 60\nend"
        )
        assert doc.shapes[0].width == 100.0

    def test_precedence(self):
        doc = _parse("a = 10 + 5 * 2\nsize a 10")
        assert doc.width_mm == 20.0

    def test_parentheses(self):
        doc = _parse("b = (10 + 5) * 2\nsize b 10")
        assert doc.width_mm == 30.0

    def test_unary_minus(self):
        doc = _parse("a = -10\nsize 10 10\nrectangle r\n  at a, 0\n  size 5 5\nend")
        assert doc.shapes[0].x == -10.0

    def test_division_is_float(self):
        doc = _parse("a = 150 / 4\nsize a 10")
        assert doc.width_mm == 37.5


class TestExpressionFunctions:
    def test_min(self):
        doc = _parse("width = 120\nr = min(12, width / 4)\nsize 10 10\n"
                     "circle c\n  at 5 5\n  radius r\nend")
        assert doc.shapes[0].radius == 12.0

    def test_max(self):
        doc = _parse("t = 3\nm = max(4, t * 2.5)\nsize m 10")
        assert doc.width_mm == 7.5

    def test_abs(self):
        doc = _parse("a = abs(0 - 15)\nsize a 10")
        assert doc.width_mm == 15.0

    def test_round(self):
        doc = _parse("a = round(10 / 3)\nsize a 10")
        assert doc.width_mm == 3.0

    def test_unsupported_function(self):
        with pytest.raises(DslError, match="unsupported function 'sin'"):
            _parse("x = sin(45)\nsize 10 10")


class TestVariableErrors:
    def test_use_before_definition(self):
        with pytest.raises(DslError, match="unknown variable 'width'"):
            _parse("axis = width / 2\nwidth = 150\nsize 10 10")

    def test_unknown_variable_in_command(self):
        with pytest.raises(DslError, match="unknown variable 'width'"):
            _parse("size width 100")

    def test_reassignment(self):
        with pytest.raises(DslError, match="variable 'width' is already defined"):
            _parse("width = 150\nwidth = 160\nsize 10 10")

    def test_division_by_zero(self):
        with pytest.raises(DslError, match="division by zero"):
            _parse("width = 150\nx = width / 0\nsize 10 10")

    def test_invalid_variable_name(self):
        with pytest.raises(DslError, match="invalid variable name 'stitch-spacing'"):
            _parse("stitch-spacing = 5\nsize 10 10")

    def test_reserved_keyword_as_variable(self):
        with pytest.raises(DslError, match="'size' is a reserved keyword"):
            _parse("size = 100\nsize 10 10")

    def test_reserved_structural_keyword(self):
        with pytest.raises(DslError, match="reserved keyword"):
            _parse("export = 5\nsize 10 10")

    def test_invalid_expression(self):
        with pytest.raises(DslError, match="invalid expression"):
            _parse("width = 150 +\nsize 10 10")

    def test_units_rejected(self):
        with pytest.raises(DslError, match="units are not allowed"):
            _parse("width = 150mm\nsize 10 10")

    def test_unsupported_syntax_blocked(self):
        with pytest.raises(DslError, match="unsupported expression syntax"):
            _parse('x = __import__("os").system("ls")\nsize 10 10')


class TestParameterNamesAllowedAsVariables:
    def test_radius_as_variable(self):
        doc = _parse(
            "radius = 8\nsize 120 80\n"
            "rounded_rectangle panel\n  at 10 10\n  size 100 60\n  radius radius\nend"
        )
        assert doc.shapes[0].radius == 8.0

    def test_margin_spacing_as_variables(self):
        doc = _parse(
            "margin = 4\nspacing = 5\nsize 120 80\n"
            "rectangle p\n  at 10 10\n  size 100 60\nend\n"
            "stitches\n  source p\n  margin margin\n  spacing spacing\nend"
        )
        op = doc.operations[0]
        assert op.margin == 4.0
        assert op.spacing == 5.0


class TestCommaMultiValue:
    def test_comma_separated_at_and_size(self):
        doc = _parse(
            "width = 120\nheight = 80\nmargin = 10\nsize width height\n"
            "rectangle panel\n  at margin, margin\n"
            "  size width - 2 * margin, height - 2 * margin\nend"
        )
        s = doc.shapes[0]
        assert (s.x, s.y, s.width, s.height) == (10.0, 10.0, 100.0, 60.0)

    def test_ambiguous_without_comma_raises(self):
        with pytest.raises(DslError, match="expects 2 values"):
            _parse("width = 120\nmargin = 10\nsize width - margin 80")

    def test_simple_whitespace_form_still_works(self):
        doc = _parse("width = 120\nheight = 80\nsize width height")
        assert (doc.width_mm, doc.height_mm) == (120.0, 80.0)

    def test_function_comma_not_split_as_values(self):
        # min(...) has an internal comma but is a single value
        doc = _parse("width = 120\nsize 10 10\ncircle c\n  at 5 5\n  radius min(12, width)\nend")
        assert doc.shapes[0].radius == 12.0

    def test_triangle_points_with_expressions(self):
        doc = _parse(
            "w = 120\nh = 90\nsize w h\n"
            "triangle t\n  p1 w / 2, 10\n  p2 w - 10, h - 10\n  p3 10, h - 10\nend"
        )
        s = doc.shapes[0]
        assert s.p1 == (60.0, 10.0)
        assert s.p2 == (110.0, 80.0)
        assert s.p3 == (10.0, 80.0)


class TestExpressionsInPointLists:
    def test_axis_variable_in_outer_points(self):
        doc = _parse(
            "axis = 30\nsize 60 60\nsymmetry axis\n"
            "outer\n  axis 10\n  50 20\n  axis 50\nend"
        )
        outer = doc.shapes[0]
        assert outer.points[0] == (30.0, 10.0)
        assert outer.points[2] == (30.0, 50.0)


class TestBackwardCompatibility:
    def test_plain_numeric_file_unchanged(self):
        doc = _parse(
            "size 120 80\n"
            "rectangle panel\n  at 10 10\n  size 100 60\nend\n"
            "stitches\n  source panel\n  edges all\n  margin 4\n  spacing 5\n  length 3\nend"
        )
        assert doc.width_mm == 120.0
        assert doc.shapes[0].width == 100.0
        assert doc.operations[0].margin == 4.0

    def test_symmetry_vertical_x_equals_still_command(self):
        doc = _parse("size 150 100\nsymmetry vertical x=75")
        assert doc.symmetry_axis_x == 75.0

    def test_symmetry_vertical_x_equals_expression(self):
        doc = _parse("w = 150\nsize w 100\nsymmetry vertical x=w / 2")
        assert doc.symmetry_axis_x == 75.0
