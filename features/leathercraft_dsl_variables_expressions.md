# DSL Variables and Expressions — Development Specification

This document describes how variables and expressions should work in `leathercraft_dsl.py`.

The goal is to make `.lcraft` files easier to maintain, especially when a pattern contains repeated dimensions such as document size, symmetry axis, margins, stitch spacing, hole radius, leather thickness, or hardware positions.

This feature should remain simple, predictable, and safe. The DSL should not become a general-purpose programming language.

---

## 1. Goals

Variables and expressions should allow users to write patterns like this:

```text
pattern lighter_sleeve

width = 150
height = 112
axis = width / 2

seam_margin = 4
stitch_spacing = 5
stitch_length = 3.8
keyring_distance = 30
keyring_y = 21
keyring_radius = 2.2

size width height
symmetry axis

outer smooth mirrored
  axis 14
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
  axis 105
end

stitches
  margin seam_margin
  spacing stitch_spacing
  length stitch_length
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
    axis 105
  end
end

hole keyring
  mirror
  x_from_center keyring_distance
  y keyring_y
  radius keyring_radius
end

export lighter_sleeve
```

This should compile exactly like the same file with all numbers written directly.

The DSL should use assignment syntax instead of a `let` keyword because this reads more like a pattern/configuration language:

```text
width = 150
height = 112
axis = width / 2
```

instead of:

```text
let width = 150
let height = 112
let axis = width / 2
```

The old `let` form is not recommended for the new design.

---

## 2. Non-goals

This feature should not add:

- loops
- conditions
- functions
- string interpolation
- user-defined macros
- access to Python
- arbitrary code execution

Those can be considered later, but variables and numeric expressions should be implemented first.

---

## 3. New syntax

### 3.1 assignment command

A variable is declared with:

```text
<name> = <expression>
```

Examples:

```text
width = 150
height = 112
axis = width / 2
seam = 4
hole_radius = 1.2
pocket_width = width - 20
corner_radius = min(12, pocket_width / 4)
```

Recommended first version: support assignments only at document level, before or between blocks.

Allowed:

```text
width = 120
size width 80

rectangle panel
  at 10 10
  size width - 20, 60
end
```

Not recommended for the first implementation:

```text
rectangle panel
  local_width = 100
  at 10 10
  size local_width 60
end
```

Block-local variables may be added later, but the first version should use one global variable scope for the whole file.

Important parser rule: an assignment is recognized only when the whole line starts with a single identifier followed by `=`:

```text
width = 150
axis = width / 2
```

This is not an assignment:

```text
symmetry vertical x=75
```

The parser should treat that as a normal `symmetry` command because the line does not match `<identifier> = <expression>`.

---

## 4. Variable names

Variable names should use a simple identifier format:

```text
[a-zA-Z_][a-zA-Z0-9_]*
```

Valid examples:

```text
width
height
axis
stitch_spacing
holeRadius
pocket2_width
```

Invalid examples:

```text
2width
stitch-spacing
hole radius
width.mm
```

Recommended style for examples and documentation: `snake_case`.

---

## 5. Reserved words

Variable names should not be allowed to use structural DSL keywords or block keywords.

Recommended reserved names:

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
source
edges
at
p1
p2
p3
from_angle
to_angle
inner_radius
mirror
mirrored
smooth
straight
export
end
```

Parameter-like names such as `radius`, `spacing`, `margin`, `length`, `angle`, `rx`, and `ry` may be allowed because they are natural variable names in pattern files.

Allowed example:

```text
radius = 8
spacing = 5
margin = 4

rounded_rectangle panel
  at 10 10
  size 100 60
  radius radius
end
```

If a user tries to use a structural reserved word:

```text
size = 100
```

The compiler should raise:

```text
line 4: 'size' is a reserved keyword and cannot be used as a variable name
```

---

## 6. Expressions

Expressions should be numeric only.

### 6.1 Supported values

The expression evaluator should support:

```text
150
112.5
-10
width
height
axis
```

### 6.2 Supported operators

The first version should support:

```text
+
-
*
/
()
```

Examples:

```text
axis = width / 2
panel_width = width - 20
center_y = (top + bottom) / 2
hole_y = height - 15
usable_width = width - 2 * margin
```

### 6.3 Operator precedence

Use normal mathematical precedence:

1. Parentheses
2. Unary `+` and unary `-`
3. Multiplication and division
4. Addition and subtraction

Example:

```text
a = 10 + 5 * 2      # 20
b = (10 + 5) * 2    # 30
```

### 6.4 Division

Division should always produce a floating-point value.

```text
axis = 150 / 2      # 75.0
```

Division by zero should be a validation error:

```text
line 7: division by zero in expression 'width / count'
```

---

## 7. Optional built-in functions

The first implementation can skip functions entirely. However, adding a tiny whitelist of safe numeric functions would be useful.

Recommended functions:

```text
min(a, b, ...)
max(a, b, ...)
abs(x)
round(x)
floor(x)
ceil(x)
```

Useful examples:

```text
radius = min(12, width / 4)
safe_margin = max(4, leather_thickness * 2.5)
centered_x = round(width / 2)
```

Important: only explicitly whitelisted functions should be allowed. Never use `eval`.

---

## 8. Where expressions are allowed

Expressions should be allowed everywhere the current DSL expects a numeric value.

Examples:

```text
size width height

symmetry width / 2
symmetry vertical x=width / 2

rectangle panel
  at margin margin
  size width - 2 * margin height - 2 * margin
end

rounded_rectangle pocket
  at 10 10
  size pocket_width pocket_height
  radius min(10, pocket_height / 2)
end

circle snap
  at width / 2 height - 15
  radius snap_radius
end

ellipse oval
  at width / 2 height / 2
  rx width / 3
  ry height / 4
end

arc half_ring
  at width / 2 height / 2
  radius outer_radius
  inner_radius inner_radius
  from_angle 180
  to_angle 360
end

stitches
  source panel
  margin seam_margin
  spacing stitch_spacing
  length stitch_spacing / 2
  angle 45
end

holes
  source panel
  margin seam_margin
  spacing hole_spacing
  radius hole_radius
end

hole snap_left
  at width / 2 - 20 height - 15
  radius snap_radius
end
```

---

## 9. Expression parsing in line commands

The current DSL uses whitespace-separated commands such as:

```text
size 150 112
at 10 10
radius 8
```

Expressions introduce ambiguity because they may contain spaces:

```text
size width - 20 height - 20
```

This is hard to parse because the compiler does not know where the first expression ends and the second begins.

To avoid ambiguity, the DSL should support two forms.

---

## 10. Recommended syntax rule for multi-value commands

### 10.1 Simple form

When values are simple numbers or variable names, whitespace syntax remains valid:

```text
size width height
at margin margin
radius corner_radius
```

### 10.2 Expression form with commas

When a command expects multiple numeric values and at least one value is a complex expression, use commas between expressions:

```text
size width - 2 * margin, height - 2 * margin
at width / 2 - 20, height - 15
p1 axis, 10
p2 width - 10, height - 10
p3 10, height - 10
```

This keeps the parser simple and readable.

Recommended examples:

```text
rectangle panel
  at margin, margin
  size width - 2 * margin, height - 2 * margin
end
```

For one-value commands, no comma is needed:

```text
radius width / 10
spacing stitch_spacing + 1
```

---

## 11. Alternative syntax: `${...}` expressions

If comma parsing becomes inconvenient, the DSL may additionally support explicit expression wrappers:

```text
size ${width - 2 * margin} ${height - 2 * margin}
at ${width / 2 - 20} ${height - 15}
```

This is more verbose but completely unambiguous.

Recommendation: start with comma support and optionally add `${...}` later if needed.

---

## 12. Parser impact of removing `let`

Using `width = 150` instead of `let width = 150` makes the DSL cleaner, but the parser needs one extra rule.

A line should be treated as an assignment only when it matches this shape:

```text
<identifier> = <expression>
```

Examples that are assignments:

```text
width = 150
height = 112
axis = width / 2
stitch_spacing = 5
```

Examples that are not assignments:

```text
size width height
symmetry axis
symmetry vertical x=axis
rectangle panel
radius 8
```

This distinction is important because the current DSL already supports syntax like:

```text
symmetry vertical x=75
```

The presence of `=` inside a line is not enough to classify the line as an assignment. The whole line must start with one identifier followed by `=`.

Recommended implementation check:

```python
ASSIGNMENT_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$")
```

If the line matches this pattern, parse it as a variable assignment. Otherwise, parse it as a normal DSL command.

---

## 13. Suggested grammar

Informal grammar:

```text
assignment      = identifier "=" expression

expression       = addition
addition         = multiplication (("+" | "-") multiplication)*
multiplication   = unary (("*" | "/") unary)*
unary            = ("+" | "-") unary | primary
primary          = number | identifier | function_call | "(" expression ")"
function_call    = identifier "(" argument_list? ")"
argument_list    = expression ("," expression)*
```

For the first version, `function_call` can be omitted.

---

## 14. Evaluation model

Variables are evaluated in file order.

This should work:

```text
width = 150
axis = width / 2
size width 100
```

This should fail:

```text
axis = width / 2
width = 150
```

Error:

```text
line 1: unknown variable 'width'
```

This should also fail:

```text
size width 100
width = 150
```

Error:

```text
line 1: unknown variable 'width'
```

This simple rule makes the DSL easy to understand: define values before using them.

---

## 15. Reassignment

Recommended first version: disallow reassignment.

This should fail:

```text
width = 150
width = 160
```

Error:

```text
line 2: variable 'width' is already defined
```

Reason: accidental redefinition is more likely than intentional mutation in a pattern description language.

Reassignment can be added later with a different keyword if needed, for example:

```text
set width = 160
```

But this is not recommended for the first version.

---

## 16. Units

The current DSL uses millimeters only and does not allow unit suffixes. This should remain unchanged.

Allowed:

```text
width = 150
size width 112
```

Not allowed:

```text
width = 150mm
size width 112mm
```

Error:

```text
line 3: units are not allowed in numeric values. Use '150', not '150mm'
```

---

## 17. Comments

Comments should work as they already do.

```text
width = 150       # document width in mm
axis = width / 2  # vertical symmetry axis
```

The parser should remove or ignore comments before parsing expressions.

---

## 18. Floating-point output

Expression values should be stored as Python `float`.

For SVG output, existing formatting rules should be reused.

If formatting needs to be added, recommended behavior:

```text
75.0 -> 75
75.25 -> 75.25
75.333333333 -> 75.3333 or similar reasonable precision
```

Avoid excessive decimal noise in SVG output.

---

## 19. Validation rules

The compiler should raise `DslError` with useful messages.

### 18.1 Unknown variable

Input:

```text
size width 100
```

Error:

```text
line 1: unknown variable 'width'
```

### 18.2 Invalid variable name

Input:

```text
stitch-spacing = 5
```

Error:

```text
line 1: invalid variable name 'stitch-spacing'
```

### 18.3 Reserved variable name

Input:

```text
radius = 5
```

This one is debatable because `radius` is also a field name. Recommended: allow field names as variable names only if this does not complicate parsing.

Safer first version: forbid all DSL keywords, including field names.

Error:

```text
line 1: 'radius' is a reserved keyword and cannot be used as a variable name
```

Alternative: only reserve top-level/block keywords and allow names like `radius`, `spacing`, `margin`.

Recommended practical compromise:

- forbid structural keywords: `end`, `path`, `rectangle`, `stitches`, `holes`, etc.
- allow parameter-like names: `radius`, `spacing`, `margin`, because they are natural variable names

Suggested valid example:

```text
radius = 8

rounded_rectangle panel
  at 10 10
  size 100 60
  radius radius
end
```

This reads slightly odd but is useful.

### 18.4 Invalid expression

Input:

```text
width = 150 +
```

Error:

```text
line 1: invalid expression '150 +'
```

### 18.5 Division by zero

Input:

```text
step = width / 0
```

Error:

```text
line 1: division by zero in expression 'width / 0'
```

### 18.6 Unsupported function

Input:

```text
x = sin(45)
```

Error:

```text
line 1: unsupported function 'sin'
```

### 18.7 Unsupported syntax

Input:

```text
x = __import__("os").system("rm -rf /")
```

Error:

```text
line 1: unsupported expression syntax
```

---

## 20. Implementation recommendation

Do not use Python `eval`.

Recommended approach:

1. Tokenize or parse the expression.
2. Use Python `ast.parse(expression, mode="eval")`.
3. Walk the AST manually.
4. Allow only safe node types.
5. Resolve variable names from a dictionary.
6. Resolve function names from a small whitelist.

Allowed AST nodes for first implementation:

```python
ast.Expression
ast.Constant       # int/float only
ast.Name
ast.BinOp
ast.UnaryOp
ast.Add
ast.Sub
ast.Mult
ast.Div
ast.UAdd
ast.USub
ast.Load
```

Optional function support:

```python
ast.Call
```

Allowed functions should be stored in a dictionary:

```python
SAFE_FUNCTIONS = {
    "min": min,
    "max": max,
    "abs": abs,
    "round": round,
    "floor": math.floor,
    "ceil": math.ceil,
}
```

Everything else should raise `DslError`.

---

## 21. Suggested internal API

Add a small expression evaluator class:

```python
class ExpressionEvaluator:
    def __init__(self):
        self.variables: dict[str, float] = {}

    def define(self, name: str, expression: str, line_no: int) -> float:
        ...

    def eval(self, expression: str, line_no: int) -> float:
        ...
```

Possible helper methods:

```python
def parse_number_or_expression(text: str, evaluator: ExpressionEvaluator, line_no: int) -> float:
    ...

def parse_value_list(text: str, expected_count: int, evaluator: ExpressionEvaluator, line_no: int) -> list[float]:
    ...
```

For multi-value parsing:

```python
parse_value_list("width height", 2) 
# -> ["width", "height"]

parse_value_list("width - 2 * margin, height - 2 * margin", 2)
# -> ["width - 2 * margin", "height - 2 * margin"]
```

If no comma is present and the command expects more than one value, the parser can keep the old whitespace behavior, but each token must be a single value.

This means:

```text
size width height
```

works, but:

```text
size width - margin height
```

should fail with a helpful message:

```text
line 4: command 'size' expects 2 values. Use commas for complex expressions: size width - margin, height
```

---

## 22. Parser/compiler changes

### 21.1 Parsing phase

The parser should recognize assignment commands and store them in the AST, or evaluate them immediately during parsing.

Two possible designs:

### Option A — evaluate during parsing

Pros:

- simpler AST
- compiler receives already-resolved numeric values
- fewer changes to shape compilation

Cons:

- parser needs expression evaluator state
- AST does not preserve original expressions

### Option B — store expressions in AST and evaluate during compilation

Pros:

- cleaner separation
- AST can preserve source expressions
- easier future tooling, formatting, diagnostics

Cons:

- more changes to existing AST classes
- compiler must evaluate all numeric fields

Recommendation: Option A for speed and simplicity, unless the project already has a clean AST layer where expressions can be preserved easily.

---

## 23. Backward compatibility

All existing `.lcraft` files should continue to work unchanged.

Existing valid examples:

```text
size 120 80

rectangle panel
  at 10 10
  size 100 60
end
```

should still parse exactly as before.

The new syntax only adds extra possibilities:

```text
width = 120
height = 80

size width height

rectangle panel
  at 10 10
  size width - 20, height - 20
end
```

---

## 24. Complete example: card panel

```text
pattern card_panel

doc_width = 120
doc_height = 80
margin = 10
panel_width = doc_width - 2 * margin
panel_height = doc_height - 2 * margin
stitch_margin = 4
stitch_spacing = 5
stitch_length = 3

size doc_width doc_height

rectangle panel
  at margin margin
  size panel_width panel_height
end

stitches
  source panel
  edges all
  margin stitch_margin
  spacing stitch_spacing
  length stitch_length
end

export card_panel
```

---

## 25. Complete example: rounded pocket

```text
pattern rounded_pocket

doc_width = 120
doc_height = 90

margin = 10
pocket_width = doc_width - 2 * margin
pocket_height = doc_height - 2 * margin

corner_radius = min(8, pocket_height / 4)
seam_margin = 5
stitch_spacing = 5
stitch_length = 3.5

size doc_width doc_height

rounded_rectangle pocket
  at margin margin
  size pocket_width pocket_height
  radius corner_radius
end

stitches
  source pocket
  edges except_top
  margin seam_margin
  spacing stitch_spacing
  length stitch_length
  angle 45
end

export rounded_pocket
```

---

## 26. Complete example: symmetric lighter sleeve

```text
pattern lighter_sleeve

width = 150
height = 112
axis = width / 2

seam_margin = 4
stitch_spacing = 5
stitch_length = 3.8

keyring_distance = 30
keyring_y = 21
keyring_radius = 2.2

size width height
symmetry axis

layer cut red 0.12
layer stitch blue 0.35

outer smooth mirrored
  axis 14
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
  axis 105
end

stitches
  margin seam_margin
  spacing stitch_spacing
  length stitch_length
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
    axis 105
  end
end

hole keyring
  mirror
  x_from_center keyring_distance
  y keyring_y
  radius keyring_radius
end

export lighter_sleeve
```

---

## 27. Suggested tests

### 26.1 Basic variable replacement

Input:

```text
width = 120
height = 80
size width height
```

Expected:

```text
document width = 120
document height = 80
```

### 26.2 Arithmetic expression

Input:

```text
width = 120
margin = 10

size width 80

rectangle panel
  at margin margin
  size width - 2 * margin, 60
end
```

Expected:

```text
panel width = 100
```

### 26.3 Parentheses

Input:

```text
value = (10 + 5) * 2
```

Expected:

```text
value = 30
```

### 26.4 Variable order error

Input:

```text
axis = width / 2
width = 150
```

Expected error:

```text
unknown variable 'width'
```

### 26.5 Reassignment error

Input:

```text
width = 150
width = 160
```

Expected error:

```text
variable 'width' is already defined
```

### 26.6 Division by zero

Input:

```text
width = 150
x = width / 0
```

Expected error:

```text
division by zero
```

### 26.7 Invalid expression in multi-value command

Input:

```text
width = 120
margin = 10
size width - margin 80
```

Expected error:

```text
command 'size' expects 2 values. Use commas for complex expressions
```

### 26.8 Comma-separated expressions

Input:

```text
width = 120
height = 80
margin = 10

size width height

rectangle panel
  at margin, margin
  size width - 2 * margin, height - 2 * margin
end
```

Expected:

```text
panel x = 10
panel y = 10
panel width = 100
panel height = 60
```

### 26.9 Function support

Input:

```text
width = 120
radius = min(12, width / 4)
```

Expected:

```text
radius = 12
```

### 26.10 Unsupported function

Input:

```text
x = sin(45)
```

Expected error:

```text
unsupported function 'sin'
```

---

## 28. Recommended first implementation scope

The first implementation should include:

- document-level assignments using `<name> = <expression>`
- global variable scope
- numeric values only
- `+`, `-`, `*`, `/`, parentheses
- unary minus
- variable references
- comma-separated complex expressions in multi-value commands
- useful `DslError` messages with line numbers
- no reassignment
- no `eval`

Optional but recommended:

- `min`
- `max`
- `abs`
- `round`

Can be postponed:

- `floor`
- `ceil`
- local block variables
- `${...}` expression syntax
- constants like `pi`
- trigonometric functions
- conditionals
- loops
- macros/components

---

## 29. Final recommendation

Implement variables and expressions as a small, safe numeric layer on top of the existing DSL.

The most important rule is predictability: `.lcraft` files should still read like pattern descriptions, not like programs.

A good first version should make this possible:

```text
width = 150
height = 112
axis = width / 2
margin = 4

size width height
symmetry axis
```

and this:

```text
rectangle panel
  at margin, margin
  size width - 2 * margin, height - 2 * margin
end
```

without changing how existing files behave.
