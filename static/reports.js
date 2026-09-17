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

function row(session) {
  const link = el("a", "row");
  link.href = `/report?id=${encodeURIComponent(session.id)}`;
  link.append(el("span", "row-head", session.headline));
  link.append(el("span", `verdict-chip ${session.status}`, CHIPS[session.status] || CHIPS.none));
  link.append(el("span", "row-when", when(session.recorded_at, session.id)));
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
