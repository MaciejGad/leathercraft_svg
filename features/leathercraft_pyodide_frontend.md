# Pyodide Browser Frontend — Development Specification

This document describes a new browser-only frontend for `leathercraft_svg`
that runs Python compilation in the browser via Pyodide instead of using
`leathercraft_server.py`.

The goal is to preserve the feel and workflow of the current editor in
`leathercraft_server.py` + `static/index.html`, while removing the server-side
compile/export dependency.

This file is intended to be the source of truth for future implementation.

---

## 1. Goal

Add a new frontend that:

- runs entirely in the browser
- uses Pyodide to execute the existing Python DSL/compiler code
- feels and behaves like the current split-pane editor
- supports live preview of compiled SVG
- supports download of:
  - `.lcraft`
  - `.svg`
- does **not** support PNG, PDF, or DXF export
- does **not** require Flask or any other runtime server-side dependency for compilation

Recommended first version:

- keep the current UI structure and most interactions
- replace `/api/compile` with in-browser Pyodide calls
- replace `/api/export/svg` with in-browser SVG file generation and download
- remove or disable PNG export

---

## 2. Why This Feature Is Useful

The current frontend depends on:

- Flask
- a local Python environment
- optional export dependencies for non-SVG formats

A Pyodide frontend would make the editor easier to share and run:

- as a static site
- in GitHub Pages or similar hosting
- without running a backend process
- without local installation beyond opening the page

This is especially useful for experimentation, teaching, and lightweight pattern editing.

---

## 3. Existing Behavior To Preserve

The current browser editor is defined by:

- [leathercraft_server.py](/Users/bazyl/Code/leatherLaser/laser_svg_library_fixed_holes/leathercraft_server.py)
- [static/index.html](/Users/bazyl/Code/leatherLaser/laser_svg_library_fixed_holes/static/index.html)

The new frontend should preserve as much of the current behavior as practical:

- split layout:
  - code editor on the left
  - SVG preview on the right
- CodeMirror-based `.lcraft` editing
- live compile / preview updates
- status indicator:
  - ready
  - busy
  - ok
  - error
- visible compile errors in an error bar
- download of source `.lcraft`
- download of compiled `.svg`
- draggable vertical splitter
- autocomplete and editor ergonomics where possible

The main functional change is:

```text
compile in browser via Pyodide
instead of POST /api/compile to Flask
```

---

## 4. Non-Goals

The first implementation should **not** include:

- server-side compilation
- Flask integration
- PNG export
- PDF export
- DXF export
- file persistence to a backend
- multi-user collaboration
- package installation at runtime from PyPI

The browser version should stay dependency-light and static-site-friendly.

---

## 5. Product Direction

### 5.1 Core idea

Load:

- Pyodide runtime
- local project Python files needed for parsing and SVG compilation

Then compile `.lcraft` source entirely in the browser using the existing Python implementation.

### 5.2 Key constraint

The browser frontend should only support export formats that can be produced
without extra binary/rendering dependencies.

Therefore:

- supported:
  - `.lcraft`
  - `.svg`
- not supported:
  - `.png`
  - `.pdf`
  - `.dxf`

SVG is enough because:

- `compile_document(...).to_svg()` already produces a complete SVG string
- it does not require CairoSVG or DXF tooling

---

## 6. Recommended File Structure

The implementation may take many forms, but a clean first version would likely add:

```text
static/pyodide_index.html
static/pyodide_editor.js
```

Optional:

```text
static/pyodide_worker.js
```

if compilation should later move off the main thread.

Alternative:

```text
static/index.html
```

could gain a mode switch or be replaced entirely, but the recommended first
implementation is to keep the current Flask UI intact and add a separate
browser-only entry point.

Recommended first version:

- keep the existing server frontend untouched
- add a parallel browser-only frontend

This reduces risk and keeps comparison easy during development.

---

## 7. Runtime Architecture

### 7.1 Browser-only compile flow

Recommended flow:

1. User edits `.lcraft` source in CodeMirror.
2. Frontend debounces changes.
3. Frontend calls a JavaScript `compileSource(source)` function.
4. `compileSource(source)` invokes Python inside Pyodide.
5. Python runs:
   - `parse(source)`
   - `compile_document(doc)`
   - `to_svg()`
6. Python returns either:
   - SVG string
   - error message
7. Frontend updates preview and status.

### 7.2 Python modules to load

The Pyodide runtime must have access to local project modules needed for SVG compilation.

At minimum:

- `leathercraft_svg.py`
- `leathercraft_dsl.py`

Possible strategy:

- fetch those files as plain text
- write them into Pyodide’s virtual filesystem
- import them inside Pyodide

Recommended bootstrap sequence:

1. load Pyodide
2. write project Python files into the virtual FS
3. pre-import `leathercraft_svg` and `leathercraft_dsl`
4. run a small compile smoke test
5. mark the UI as ready

---

## 8. Pyodide Assumptions

Recommended assumption:

```text
Pyodide is loaded from CDN
```

Example direction:

```html
<script src="https://cdn.jsdelivr.net/pyodide/.../pyodide.js"></script>
```

Exact version can be chosen during implementation.

The feature should avoid depending on Python packages that are not already
bundled with Pyodide or trivially unnecessary.

Important consequence:

- no CairoSVG
- no Pillow
- no ezdxf

The browser compiler should use only the pure-Python SVG path already present.

---

## 9. UI Requirements

### 9.1 Layout

The page should closely match the current editor:

- top toolbar
- left editor panel
- draggable splitter
- right preview panel

### 9.2 Toolbar

Recommended controls:

- logo / title
- status pill
- download `.lcraft`
- download `.svg`

Recommended first version:

- remove PNG button completely

Alternative:

- show disabled PNG button with tooltip

Recommended choice:

```text
remove unsupported export buttons
```

This is clearer and avoids implying missing functionality is temporarily broken.

### 9.3 Status states

Required states:

- `loading pyodide`
- `ready`
- `compiling`
- `ok`
- `error`

The existing `busy`, `ok`, `err` visual style can be reused.

### 9.4 Error panel

Compile errors should be shown in a dedicated visible area, similar to the
current `#error-bar`.

Error output should prefer the Python DSL error message directly, for example:

```text
Line 12: unknown source 'panel2'
```

If a JavaScript/Pyodide infrastructure error occurs, show a clear message such as:

```text
Pyodide initialization failed: ...
```

---

## 10. Functional Behavior

### 10.1 Live preview

The SVG preview should update automatically after edits using a debounce.

Recommended debounce:

```text
200–400 ms
```

Recommended default:

```text
300 ms
```

### 10.2 `.lcraft` download

The user should be able to download the current editor contents as a `.lcraft` file.

Recommended filename logic:

1. use DSL `pattern <name>` if present
2. otherwise use:

```text
pattern.lcraft
```

### 10.3 `.svg` download

The user should be able to download the currently compiled SVG string directly
from the browser.

Recommended behavior:

- if the current source compiles successfully:
  - generate Blob from SVG text
  - trigger browser download
- if compilation fails:
  - block download
  - show the compile error instead

### 10.4 Initial sample content

The editor should open with a useful default pattern, similar to the existing page.

Recommended source:

- reuse the current sample pattern from the existing frontend if one exists
- otherwise use a simple rectangle with stitches or holes

---

## 11. Python Integration Strategy

### 11.1 Recommended Python entry point

The browser should execute logic equivalent to:

```python
from leathercraft_dsl import parse, compile_document

def compile_lcraft_to_svg(source: str) -> dict:
    try:
        doc = parse(source)
        svg = compile_document(doc).to_svg()
        return {"svg": svg, "error": None}
    except Exception as exc:
        return {"svg": None, "error": str(exc)}
```

Recommended improvement:

Catch `DslError` separately if helpful for display, but for the first version a
simple error string is acceptable as long as DSL messages survive clearly.

### 11.2 No file-based build path

The browser compiler should compile from in-memory source text.

Do not use:

```text
build_file(path)
```

because browser mode should not depend on writing real files into a user-visible filesystem.

Use:

```text
parse(source) -> compile_document(doc) -> to_svg()
```

---

## 12. Export Limitations

### 12.1 Allowed exports

Supported:

- `.lcraft`
- `.svg`

### 12.2 Unsupported exports

The browser frontend must not offer:

- `.png`
- `.pdf`
- `.dxf`

Reason:

- these need optional dependencies or additional rendering infrastructure
- the goal is a no-extra-dependency static frontend

Recommended user-facing wording:

```text
Browser mode supports SVG export only.
```

---

## 13. Dependency Constraints

The feature should not introduce required Python-side runtime dependencies
beyond the existing project files needed by the DSL/compiler.

Frontend dependencies may still include:

- Pyodide
- CodeMirror

Recommended first version:

- keep CodeMirror 5 if reusing current `index.html`
- avoid a broad frontend rewrite

This is a compatibility feature, not a redesign project.

---

## 14. Error Handling Requirements

### 14.1 Pyodide load failure

If Pyodide cannot load:

- disable compile/export actions
- show a clear error in status and error panel

Example:

```text
Failed to load Pyodide. Check your network connection or static asset configuration.
```

### 14.2 Python import failure

If project Python modules cannot be loaded into Pyodide:

```text
Failed to load leathercraft Python modules in browser mode.
```

### 14.3 Compile failure

If DSL compilation fails:

- do not replace the last good preview unless explicitly desired
- show the error message
- keep editor responsive

Recommended first version:

- keep the last valid SVG preview visible
- show the new error

This matches how live code editors usually feel better in practice.

### 14.4 Export with invalid source

If `.svg` download is requested while the current source is invalid:

- do not download anything
- show compile error

---

## 15. Performance Expectations

### 15.1 Startup

Pyodide startup will be slower than the Flask-backed frontend.

Expected first-load phases:

- load JS/CSS
- load Pyodide runtime
- load Python project files
- initialize compiler

The UI should communicate that clearly via status text.

### 15.2 Editing

After initialization, editing should feel reasonably interactive for normal-sized
`.lcraft` documents.

Recommended expectations:

- compile triggered via debounce
- no compile on every keystroke without delay
- avoid blocking the UI excessively

### 15.3 Future optimization

If compile latency becomes annoying, a future improvement can move Pyodide
execution to a Web Worker.

This is optional and not required for the first version.

---

## 16. Security / Hosting Notes

Because the frontend runs Python in the browser, deployment is simpler, but:

- the browser still needs to fetch Pyodide assets
- the browser still needs to fetch local Python source files unless bundled

Recommended first version:

- static hosting is sufficient
- no API server required

If hosting from `file://` causes import/fetch issues, document that the page
should be served over HTTP, even if it is a static server.

---

## 17. Recommended Implementation Order

1. Create a new browser-only HTML entry point in `static/`.
2. Copy the current editor layout and remove server-specific export controls.
3. Load Pyodide and display startup status.
4. Load `leathercraft_svg.py` and `leathercraft_dsl.py` into Pyodide.
5. Implement in-browser `compileSource(source) -> {svg, error}`.
6. Wire live preview updates.
7. Implement `.lcraft` download.
8. Implement `.svg` download.
9. Add error handling for Pyodide/module/init failures.
10. Add docs and usage notes.

---

## 18. Suggested Tests

### 18.1 Manual browser tests

Verify:

1. Page loads with loading state.
2. Pyodide initializes successfully.
3. Valid `.lcraft` source renders SVG preview.
4. Invalid source shows readable error.
5. `.lcraft` download works.
6. `.svg` download works.
7. No server API calls are required for compile/export.
8. Existing server-backed frontend still works unchanged.

### 18.2 Developer-level checks

If test tooling is later added for frontend behavior, useful checks include:

1. compile is debounced
2. last valid preview remains visible after a compile error
3. download buttons are disabled until Pyodide is ready
4. browser mode does not expose PNG export
5. browser mode does not issue requests to `/api/compile`

---

## 19. Example UX Copy

Recommended toolbar/button labels:

- `.lcraft`
- `.svg`

Recommended status text:

- `loading pyodide`
- `ready`
- `compiling`
- `ok`
- `error`

Recommended preview placeholder:

```text
Type a pattern in the editor.
Python runs locally in your browser via Pyodide.
```

---

## 20. Backward Compatibility

This feature must not break or replace:

- `leathercraft_server.py`
- the current Flask routes
- existing SVG/PNG export behavior in server mode

Recommended first implementation:

- add a separate browser-only frontend
- keep the current server frontend available as-is

This allows a gradual migration or side-by-side comparison.

---

## 21. Open Questions

These do not need to block the first implementation, but should be considered:

### 21.1 Single page or separate page?

Recommended first version:

```text
separate page
```

Reason:

- lower risk
- easier to compare against current frontend
- keeps Flask mode untouched

### 21.2 Module loading strategy?

Options:

- fetch raw `.py` files into Pyodide FS
- bundle Python source into JS strings
- package the project for Pyodide consumption

Recommended first version:

```text
fetch raw local .py files
```

because it is simple and keeps source-of-truth in the existing Python files.

### 21.3 Keep CodeMirror 5 or modernize?

Recommended first version:

```text
keep CodeMirror 5
```

Reason:

- current editor already uses it
- lower rewrite cost
- feature goal is browser execution, not editor redesign

---

## 22. Summary

The new feature is a browser-only `.lcraft` editor and live SVG compiler using
Pyodide.

The implementation should:

- resemble the current split-pane editor
- compile using the existing Python DSL/compiler in-browser
- export only `.lcraft` and `.svg`
- avoid PNG/PDF/DXF and backend dependencies
- keep the current Flask frontend unchanged

This provides a static, dependency-light way to use `leathercraft_svg` directly in the browser.
