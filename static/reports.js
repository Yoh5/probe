// Probe - every interview that has been recorded, newest first.
//
// The headline of each row is the one the report itself produces, so the list
// and the report can never say different things about the same interview.

const $ = (id) => document.getElementById(id);

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function when(iso, id) {
  const at = new Date(iso || "");
  if (!Number.isNaN(at.valueOf())) {
    return at.toLocaleString(undefined, {
      year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
    });
  }
  // The id starts with the moment it was saved, so a session with no recordedAt
  // still says when it happened rather than nothing.
  const stamp = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})/.exec(id || "");
  return stamp ? `${stamp[3]}/${stamp[2]}/${stamp[1]} ${stamp[4]}:${stamp[5]}` : "";
}

const CHIPS = { flag: "Worth a second look", clear: "Nothing flagged", none: "Nothing comparable" };

const ICONS = {
  flag: ["M12 3.4 21.2 19H2.8z", "M12 9.6v3.9", "M12 16.3v.1"],
  clear: ["M4.5 12.5 9.5 17.5 19.5 6.5"],
  none: ["M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17z", "M8.5 12h7"],
};

function tile(kind) {
  const box = el("span", `tile ${kind}`);
  box.setAttribute("aria-hidden", "true");
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "2.2");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  for (const d of ICONS[kind] || ICONS.none) {
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", d);
    svg.append(path);
  }
  box.append(svg);
  return box;
}

function row(session) {
  const link = el("a", "entry");
  link.href = `/report?id=${encodeURIComponent(session.id)}`;
  link.append(tile(session.status));
  const body = el("div");
  body.append(el("p", "entry-head", session.headline));
  const mark = `${when(session.recorded_at, session.id)}  ·  ${CHIPS[session.status] || CHIPS.none}`;
  body.append(el("p", "entry-when", mark));
  link.append(body);
  return link;
}

async function load() {
  try {
    const response = await fetch("/api/sessions");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const { sessions } = await response.json();
    $("count").textContent = sessions.length === 1
      ? "One interview recorded."
      : `${sessions.length} interviews recorded.`;
    const list = $("list");
    list.className = sessions.length ? "group" : "";
    list.replaceChildren();
    if (!sessions.length) {
      list.append(el("p", "empty", "No interview has been recorded yet. The first one will appear here."));
      return;
    }
    for (const session of sessions) list.append(row(session));
  } catch (error) {
    $("count").textContent = `The list could not be loaded: ${error.message}`;
  }
}

load();
