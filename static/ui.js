// What the report and the list of interviews share: DOM helpers that only ever
// set text (transcripts are what a microphone heard, never markup), the status
// glyphs, and the names of the recording modes. Loaded before each page script.

const $ = (id) => document.getElementById(id);

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else node.setAttribute(key, value);
  }
  node.append(...children.filter((c) => c !== null && c !== undefined));
  return node;
}

function svg(path, strokeWidth = 2.4) {
  const ns = "http://www.w3.org/2000/svg";
  const s = document.createElementNS(ns, "svg");
  s.setAttribute("viewBox", "0 0 24 24");
  s.setAttribute("fill", "none");
  s.setAttribute("stroke", "currentColor");
  s.setAttribute("stroke-width", String(strokeWidth));
  s.setAttribute("stroke-linecap", "round");
  s.setAttribute("stroke-linejoin", "round");
  s.setAttribute("aria-hidden", "true");
  const p = document.createElementNS(ns, "path");
  p.setAttribute("d", path);
  s.append(p);
  return s;
}

// Every status colour ships with its own glyph: the meaning never rests on hue.
const ICONS = {
  flag: "M12 7v6M12 17h.01",
  clear: "M5 12.5l4.5 4.5L19 7",
  none: "M7 12h10",
  baseline: "M12 19a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM12 12h.01",
};

const statusTile = (tone) => el("span", { class: `status-tile ${tone}`, "aria-hidden": "true" }, svg(ICONS[tone] || ICONS.none));

const MODE_LABELS = {
  interview: "Interview",
  "calibration-spontaneous": "Calibration, answered spontaneously",
  "calibration-reading": "Calibration, read aloud",
  calibration: "Calibration, marked per answer",
};
