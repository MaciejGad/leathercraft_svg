const tutorialSamples = [
  {
    id: "sample-1",
    title: "Your first pattern",
    description: "A pattern needs a name and a canvas size. This gives us a blank sheet to build on.",
    source: `pattern hello_rectangle
size 120 80

rectangle panel
  at 10 10
  size 100 60
end

export hello_rectangle
`,
  },
  {
    id: "sample-2",
    title: "Adding circles and single holes",
    description: "You can mix larger outline shapes with individual holes. This is a good pattern for snaps, rivets, or keyring holes.",
    source: `pattern circle_and_hole
size 140 90

rectangle panel
  at 15 15
  size 110 60
end

circle medallion
  at 70 45
  radius 18
  layer guide
end

hole snap
  at 70 45
  radius 3
  layer stitch
end

export circle_and_hole
`,
  },
  {
    id: "sample-3",
    title: "Automatic holes on edges",
    description: "The `holes` block places repeated holes along a source shape so you do not have to calculate each point by hand.",
    source: `pattern holes_demo
size 140 100

rounded_rectangle pocket
  at 20 20
  size 100 60
  radius 10
end

holes
  source pocket
  edges left right bottom
  margin 5
  spacing 8
  radius 1.2
  layer stitch
end

export holes_demo
`,
  },
  {
    id: "sample-4",
    title: "Laser stitch marks",
    description: "If you prefer laser marks instead of round holes, use `stitches` to draw short angled segments.",
    source: `pattern stitch_marks
size 150 100

rounded_rectangle sleeve
  at 20 20
  size 110 60
  radius 12
end

stitches
  source sleeve
  edges right bottom left
  margin 6
  spacing 7
  length 3.5
  angle 45
  layer stitch
end

export stitch_marks
`,
  },
  {
    id: "sample-5",
    title: "Building a custom outline",
    description: "For freeform panels, use `outer` and define the points yourself. This is a good next step once rectangles feel too limiting.",
    source: `pattern custom_flap
size 170 120

outer straight
  20 90
  20 35
  70 15
  120 35
  120 90
end

holes
  source outer
  edges all
  margin 6
  spacing 10
  radius 1.1
  layer stitch
end

export custom_flap
`,
  },
  {
    id: "sample-6",
    title: "A more complete pocket panel",
    description: "This combines a rounded outline, edge holes, and a snap hole so you can see how real patterns grow from small building blocks.",
    source: `pattern pocket_panel
size 170 120

rounded_rectangle outer_panel
  at 20 20
  size 120 80
  radius 14
end

holes
  source outer_panel
  edges left right bottom
  margin 6
  spacing 7
  radius 1.1
  layer stitch
end

hole snap
  at 80 45
  radius 3
  layer guide
end

export pocket_panel
`,
  },
];

const compiler = window.LeathercraftPyodide.createPyodideCompiler();
const pageStatus = document.getElementById("page-status");

function setPageStatus(state, text) {
  pageStatus.className = `status ${state}`;
  pageStatus.textContent = text;
}

function cleanSvg(svgText) {
  return svgText.replace(/^<\?xml[^?]*\?>\s*/m, "");
}

function fitPreview(container) {
  const svgEl = container.querySelector("svg");
  if (!svgEl) return;
  const vb = svgEl.viewBox.baseVal;
  if (vb && vb.width > 0 && vb.height > 0) {
    const width = container.clientWidth - 32;
    const height = Math.max(160, container.clientHeight - 32);
    const scale = Math.min(width / vb.width, height / vb.height);
    svgEl.setAttribute("width", `${Math.round(vb.width * scale)}px`);
    svgEl.setAttribute("height", `${Math.round(vb.height * scale)}px`);
  } else {
    svgEl.style.maxWidth = "100%";
    svgEl.style.maxHeight = "100%";
  }
}

function tutorialEditorUrl(source) {
  const url = new URL("./index.html", window.location.href);
  url.searchParams.set("source", source);
  return url.toString();
}

function createSampleCard(sample) {
  const card = document.createElement("section");
  card.className = "sample-card";
  card.innerHTML = `
    <div class="sample-copy">
      <div class="sample-heading">
        <h3>${sample.title}</h3>
        <p>${sample.description}</p>
      </div>
      <div class="sample-actions">
        <button class="sample-run">Render sample</button>
        <a class="sample-open" target="_blank" rel="noopener">Open in full editor</a>
      </div>
      <textarea class="sample-source" spellcheck="false"></textarea>
      <p class="sample-note">Edit the code, then render again to see what changes.</p>
      <div class="sample-error" hidden></div>
    </div>
    <div class="sample-preview-wrap">
      <div class="sample-preview">
        <div class="sample-placeholder">Render this example to see the generated SVG.</div>
      </div>
    </div>
  `;

  const textarea = card.querySelector(".sample-source");
  const button = card.querySelector(".sample-run");
  const openLink = card.querySelector(".sample-open");
  const preview = card.querySelector(".sample-preview");
  const errorBox = card.querySelector(".sample-error");

  textarea.value = sample.source;
  openLink.href = tutorialEditorUrl(sample.source);

  async function runSample() {
    errorBox.hidden = true;
    errorBox.textContent = "";
    button.disabled = true;
    button.textContent = "Rendering...";

    try {
      await compiler.ensureReady(setPageStatus);
      const result = await compiler.compile(textarea.value);
      if (result.error) {
        throw new Error(result.error);
      }
      preview.innerHTML = cleanSvg(result.svg);
      fitPreview(preview);
      openLink.href = tutorialEditorUrl(textarea.value);
      button.textContent = "Render sample";
      setPageStatus("ok", "sample rendered");
    } catch (error) {
      preview.innerHTML = '<div class="sample-placeholder">This sample did not compile.</div>';
      errorBox.hidden = false;
      errorBox.textContent = error.message;
      button.textContent = "Render sample";
      setPageStatus("err", "render error");
    } finally {
      button.disabled = false;
    }
  }

  button.addEventListener("click", runSample);
  textarea.addEventListener("input", () => {
    openLink.href = tutorialEditorUrl(textarea.value);
  });
  window.addEventListener("resize", () => fitPreview(preview));

  return card;
}

async function bootstrapTutorial() {
  setPageStatus("busy", "loading browser compiler");
  const container = document.getElementById("tutorial-samples");
  tutorialSamples.forEach(sample => {
    container.appendChild(createSampleCard(sample));
  });

  await compiler.ensureReady(setPageStatus);
  setPageStatus("ok", "ready to render");

  const firstButton = container.querySelector(".sample-run");
  if (firstButton) firstButton.click();
}

bootstrapTutorial().catch(error => {
  setPageStatus("err", `failed to load: ${error.message}`);
});
