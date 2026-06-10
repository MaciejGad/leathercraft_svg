const BLOCK_STARTERS = new Set([
  "rectangle", "rounded_rectangle", "stadium", "circle", "ellipse", "arc", "triangle", "rounded_triangle", "regular_polygon", "rounded_regular_polygon",
  "outer", "stitches", "holes", "hole", "path",
]);
const TOP_KEYWORDS = new Set(["pattern", "size", "export", "end"]);
const ALL_KEYWORDS = new Set([...BLOCK_STARTERS, ...TOP_KEYWORDS]);

const PROPERTY_NAMES = new Set([
  "at", "radius", "corner_radius", "radius_tl", "radius_tr", "radius_br", "radius_bl", "rx", "ry", "inner_radius", "from_angle", "to_angle", "sides", "rotation", "layer", "edges", "margin", "spacing", "length", "angle",
  "source", "mirror", "side", "rounded_path", "p1", "p2", "p3", "smooth", "step", "count", "from", "to",
]);

const VALUE_ATOMS = new Set([
  "all", "top", "bottom", "left", "right",
  "cut", "stitch", "crease", "guide",
  "svg", "png", "pdf", "dxf",
]);

const EXPR_FUNCTIONS = new Set(["min", "max", "abs", "round", "floor", "ceil"]);

const BLOCK_PROPS = {
  rectangle: ["at", "size", "layer", "end"],
  rounded_rectangle: ["at", "size", "radius", "radius_tl", "radius_tr", "radius_br", "radius_bl", "layer", "end"],
  stadium: ["at", "size", "layer", "end"],
  circle: ["at", "radius", "layer", "end"],
  ellipse: ["at", "rx", "ry", "size", "layer", "end"],
  arc: ["at", "radius", "inner_radius", "from_angle", "to_angle", "layer", "end"],
  triangle: ["p1", "p2", "p3", "at", "size", "layer", "end"],
  rounded_triangle: ["p1", "p2", "p3", "at", "size", "radius", "layer", "end"],
  regular_polygon: ["at", "radius", "sides", "rotation", "layer", "end"],
  rounded_regular_polygon: ["at", "radius", "corner_radius", "corner_radius_0", "sides", "rotation", "layer", "end"],
  outer: ["smooth", "mirror", "end"],
  stitches: ["source", "edges", "margin", "spacing", "length", "angle", "layer", "mirror", "side", "rounded_path", "path", "end"],
  holes: ["source", "edges", "margin", "spacing", "radius", "layer", "rounded_path", "end"],
  hole: ["at", "radius", "layer", "mirror", "from", "to", "step", "count", "end"],
  path: ["end"],
};

const PROP_VALUES = {
  layer: ["cut", "stitch", "crease", "guide"],
  edges: ["all", "top", "right", "bottom", "left", "0", "1", "2"],
  side: ["right", "left"],
};

const DEFAULT_SOURCE = `pattern rectangle_panel
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

export rectangle_panel
`;

const compiler = window.LeathercraftPyodide.createPyodideCompiler();
let lastGoodSvg = null;
let lastCompileError = null;
let compileTimer = null;
let compileGeneration = 0;

const statusEl = document.getElementById("status");
const errorBar = document.getElementById("error-bar");
const svgCont = document.getElementById("svg-container");
const placeholder = document.getElementById("preview-placeholder");
const btnLcraft = document.getElementById("btn-lcraft");
const btnSvg = document.getElementById("btn-svg");
const splitEl = document.getElementById("split");
const editorPanel = document.getElementById("editor-panel");
const resizer = document.getElementById("resizer");

CodeMirror.defineMode("lcraft", function() {
  return {
    startState: () => ({}),
    token(stream) {
      if (stream.eatSpace()) return null;

      if (stream.peek() === "#") {
        const rest = stream.string.slice(stream.pos + 1);
        if (!/^[0-9a-fA-F]{3,8}(\s|$)/.test(rest)) {
          stream.skipToEnd();
          return "comment";
        }
      }

      if (stream.match(/^-?[0-9]+(\.[0-9]+)?/)) return "number";
      if (stream.match(/^#[0-9a-fA-F]{3,8}/)) return "atom";
      if (stream.match(/^[+\-*/()=,]/)) return "operator";

      if (stream.match(/^[a-zA-Z_][a-zA-Z0-9_]*/)) {
        const word = stream.current();
        if (ALL_KEYWORDS.has(word)) return "keyword";
        if (EXPR_FUNCTIONS.has(word)) return "builtin";
        if (/^(radius|corner_radius)_\d+$/.test(word)) return "property";
        if (PROPERTY_NAMES.has(word)) return "property";
        if (VALUE_ATOMS.has(word)) return "atom";
        return "variable";
      }

      stream.next();
      return null;
    },
  };
});

function setStatus(state, text) {
  statusEl.className = state;
  statusEl.textContent = text;
}

function setButtonsEnabled(enabled) {
  btnLcraft.disabled = !enabled;
  btnSvg.disabled = !enabled;
}

function showError(message) {
  errorBar.textContent = message;
  errorBar.classList.add("visible");
}

function clearError() {
  errorBar.textContent = "";
  errorBar.classList.remove("visible");
}

function findCurrentBlock(editor, cursor) {
  const depth = [];
  for (let i = 0; i <= cursor.line; i += 1) {
    const line = editor.getLine(i);
    const maxCh = i === cursor.line ? cursor.ch : line.length;
    const text = line.slice(0, maxCh).trim();
    const first = text.split(/\s+/)[0];
    if (!first) continue;
    if (BLOCK_STARTERS.has(first)) depth.push(first);
    else if (first === "end") depth.pop();
  }
  return depth.length > 0 ? depth[depth.length - 1] : null;
}

function lcraftHint(editor) {
  const cursor = editor.getCursor();
  const line = editor.getLine(cursor.line);
  const before = line.slice(0, cursor.ch);
  const wordMatch = before.match(/[a-zA-Z0-9_#]*$/);
  const typed = wordMatch ? wordMatch[0] : "";
  const from = CodeMirror.Pos(cursor.line, cursor.ch - typed.length);
  const propMatch = before.trimStart().match(/^([a-z_]+)\s+[a-zA-Z0-9_#]*$/);
  const leadingProp = propMatch ? propMatch[1] : null;

  let candidates = [];
  if (leadingProp && PROP_VALUES[leadingProp]) {
    candidates = PROP_VALUES[leadingProp];
  } else {
    const block = findCurrentBlock(editor, cursor);
    if (block) {
      candidates = BLOCK_PROPS[block] || [];
    } else {
      candidates = [
        "pattern", "size", "rectangle", "rounded_rectangle", "stadium", "circle", "ellipse", "arc",
        "triangle", "rounded_triangle", "regular_polygon", "rounded_regular_polygon", "outer", "stitches", "holes", "hole", "export",
      ];
    }
  }

  const list = candidates.filter(candidate => candidate.startsWith(typed) && candidate !== typed);
  if (!list.length) return null;
  return { list, from, to: CodeMirror.Pos(cursor.line, cursor.ch) };
}

const editor = CodeMirror.fromTextArea(document.getElementById("editor"), {
  mode: "lcraft",
  theme: "dracula",
  lineNumbers: true,
  indentUnit: 2,
  tabSize: 2,
  indentWithTabs: false,
  lineWrapping: false,
  autofocus: true,
  extraKeys: {
    "Ctrl-Space": cm => cm.showHint({ hint: lcraftHint, completeSingle: false }),
    "Ctrl-/": cm => cm.toggleComment(),
    Tab: cm => {
      if (cm.somethingSelected()) cm.indentSelection("add");
      else cm.replaceSelection("  ");
    },
  },
  hintOptions: { hint: lcraftHint, completeSingle: false },
});
editor.setSize("100%", "100%");
function initialSource() {
  const params = new URLSearchParams(window.location.search);
  return params.get("source") || DEFAULT_SOURCE;
}

editor.setValue(initialSource());

function patternName() {
  const match = editor.getValue().match(/^pattern\s+(\S+)/m);
  return match ? match[1] : "pattern";
}

function clientDownload(content, mimeType, filename) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = Object.assign(document.createElement("a"), { href: url, download: filename });
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function renderSvg(svgStr, dimmed = false) {
  if (placeholder && placeholder.parentNode) placeholder.remove();
  const clean = svgStr.replace(/^<\?xml[^?]*\?>\s*/m, "");
  svgCont.innerHTML = clean;
  const svgEl = svgCont.querySelector("svg");
  if (!svgEl) return;

  const vb = svgEl.viewBox.baseVal;
  if (vb && vb.width > 0 && vb.height > 0) {
    const scroll = document.getElementById("preview-scroll");
    const availableWidth = Math.max(100, scroll.clientWidth - 48);
    const availableHeight = Math.max(100, scroll.clientHeight - 48);
    const scale = Math.min(availableWidth / vb.width, availableHeight / vb.height);
    svgEl.setAttribute("width", `${Math.round(vb.width * scale)}px`);
    svgEl.setAttribute("height", `${Math.round(vb.height * scale)}px`);
  } else {
    svgEl.style.maxWidth = "calc(100vw - 80px)";
    svgEl.style.maxHeight = "calc(100vh - 140px)";
  }

  svgEl.style.display = "block";
  svgEl.style.opacity = dimmed ? "0.4" : "1";
  svgEl.style.transition = "opacity .2s";
}

async function compileAndRender(source) {
  const generation = ++compileGeneration;
  setStatus("busy", compiler.isReady() ? "compiling" : "loading pyodide");

  try {
    const result = await compiler.compile(source);
    if (generation !== compileGeneration) return;

    if (result.svg) {
      lastGoodSvg = result.svg;
      lastCompileError = null;
      renderSvg(result.svg);
      clearError();
      setStatus("ok", "compiled ✓");
    } else {
      lastCompileError = result.error || "Unknown error";
      if (lastGoodSvg) renderSvg(lastGoodSvg, true);
      showError(lastCompileError);
      setStatus("err", "error");
    }
  } catch (error) {
    if (generation !== compileGeneration) return;
    lastCompileError = `Pyodide compilation failed: ${error.message}`;
    if (lastGoodSvg) renderSvg(lastGoodSvg, true);
    showError(lastCompileError);
    setStatus("err", "error");
  }
}

async function bootstrapPyodide() {
  await compiler.ensureReady(setStatus);
  setButtonsEnabled(true);
  clearError();
  setStatus("ready", "ready");
  await compileAndRender(editor.getValue());
}

editor.on("change", () => {
  clearTimeout(compileTimer);

  if (!compiler.isReady()) return;

  compileTimer = window.setTimeout(() => {
    compileAndRender(editor.getValue());
  }, 300);

  const cursor = editor.getCursor();
  const line = editor.getLine(cursor.line).slice(0, cursor.ch);
  if (/[a-zA-Z_]$/.test(line)) {
    editor.showHint({ hint: lcraftHint, completeSingle: false });
  }
});

btnLcraft.addEventListener("click", () => {
  clientDownload(editor.getValue(), "text/plain", `${patternName()}.lcraft`);
});

btnSvg.addEventListener("click", async () => {
  if (!compiler.isReady()) {
    showError("Pyodide is still loading.");
    setStatus("busy", "loading pyodide");
    return;
  }

  const source = editor.getValue();
  await compileAndRender(source);
  if (!lastGoodSvg || lastCompileError) {
    showError(lastCompileError || "Compile successfully first.");
    setStatus("err", "error");
    return;
  }
  clientDownload(lastGoodSvg, "image/svg+xml", `${patternName()}.svg`);
});

let isResizing = false;

resizer.addEventListener("mousedown", event => {
  isResizing = true;
  resizer.classList.add("active");
  document.body.style.cursor = "col-resize";
  document.body.style.userSelect = "none";
  event.preventDefault();
});

document.addEventListener("mousemove", event => {
  if (!isResizing) return;
  const rect = splitEl.getBoundingClientRect();
  const newWidth = Math.max(200, Math.min(event.clientX - rect.left, rect.width - 200));
  editorPanel.style.flex = "none";
  editorPanel.style.width = `${newWidth}px`;
  editor.refresh();
});

document.addEventListener("mouseup", () => {
  if (!isResizing) return;
  isResizing = false;
  resizer.classList.remove("active");
  document.body.style.cursor = "";
  document.body.style.userSelect = "";
  editor.refresh();
});

setButtonsEnabled(false);
showError("Loading Pyodide and Python modules...");

bootstrapPyodide().catch(error => {
  setButtonsEnabled(false);
  showError(`Pyodide initialization failed: ${error.message}`);
  setStatus("err", "error");
});
