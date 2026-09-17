// Probe - the recruiter's report for one interview.
//
// Everything here was decided while the interview was running. This page reads
// the saved session back and lays it out; it never scores anything, so it cannot
// disagree with the interview it describes.
//
// Every value that came from a candidate's mouth reaches the DOM through
// textContent. A transcript is user input: it is displayed, never parsed.

const $ = (id) => document.getElementById(id);

// An icon per status, drawn rather than coloured in, so the meaning survives a
// black and white print where the colour does not.
const ICONS = {
  flag: ["M12 3.4 21.2 19H2.8z", "M12 9.6v3.9", "M12 16.3v.1"],
  clear: ["M4.5 12.5 9.5 17.5 19.5 6.5"],
  none: ["M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17z", "M8.5 12h7"],
  brand: ["M12 5.7v.1", "M8.4 10.2Q12 14.6 15.6 10.2", "M5.2 13.4Q12 21.4 18.8 13.4"],
};
// Every word on this page comes from the report, in the language the interview
// was held in. The page holds none of its own, so a missing translation shows up
// instead of quietly falling back to English.
let say = {};
const CHIP_KEY = { flag: "worth_second_look", clear: "nothing_flagged", none: "nothing_comparable" };
const TILE = { prepared: "flag", spontaneous: "clear", baseline: "brand", not_measured: "none" };
const STEP_TILE = { prepared: "flag", not_measured: "none", missed: "none" };

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

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

function when(iso, language) {
  const at = new Date(iso || "");
  return Number.isNaN(at.valueOf()) ? "" : at.toLocaleString(language || undefined, {
    year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

function stat(value, label) {
  const box = el("div", "stat");
  box.append(el("b", null, String(value)), el("span", null, label));
  return box;
}

function summary(report) {
  const card = el("section", `card ${report.status}`);
  const head = el("div", "summary-head");
  head.append(tile(report.status === "flag" ? "flag" : report.status === "clear" ? "clear" : "none"),
              el("p", "headline", report.headline));
  card.append(head);

  const meta = [when(report.recorded_at, report.language), (report.language || "").toUpperCase(),
                say[CHIP_KEY[report.status] || CHIP_KEY.none]].filter(Boolean);
  card.append(el("p", "meta", meta.join("  ·  ")));

  const stats = el("div", "stats");
  const flagged = stat(report.counts.flagged, say.stat_prepared);
  if (report.counts.flagged) flagged.classList.add("flag");
  else if (report.counts.compared) flagged.classList.add("clear");
  stats.append(stat(report.counts.answers, say.stat_answers),
               stat(report.counts.compared, say.stat_compared),
               flagged,
               stat(report.counts.words_spoken, say.stat_words));
  card.append(stats);
  return card;
}

// One card per thing worth going back over. This is the report; everything under
// it is the evidence behind it.
function stepCard(step) {
  const card = el("section", `card step ${step.kind}`);
  const head = el("div", "summary-head");
  head.append(tile(STEP_TILE[step.kind] || "none"), el("p", "headline", step.title));
  card.append(head);

  if (step.claim) {
    const said = el("blockquote", "said-quote");
    said.append(el("span", "partial", say.what_they_said), document.createTextNode(step.claim));
    card.append(said);
  }
  card.append(el("p", "why-step", step.why));

  if (step.goal) {
    const goal = el("p", "goal");
    goal.append(el("b", null, say.come_away), document.createTextNode(step.goal));
    card.append(goal);
  }
  if (step.reasons.length) {
    const why = el("ul", "why");
    for (const reason of step.reasons) why.append(el("li", null, reason));
    card.append(why);
  }
  return card;
}

function answerCard(answer, index) {
  const card = el("section", "card");

  card.append(el("span", `chip ${answer.verdict}`, answer.title));
  card.append(answer.question
    ? el("p", "asked", answer.question)
    : el("p", "asked unknown", say.not_recorded.replace("{n}", String(index + 1))));

  if (answer.said) {
    const quote = el("blockquote", "said-quote");
    if (answer.excerpt) quote.append(el("span", "partial", say.closing_words));
    quote.append(document.createTextNode(answer.said));
    card.append(quote);
  }

  const facts = el("div", "facts");
  const add = (value, label) => {
    if (value === null || value === undefined) return;
    const box = el("span", "fact");
    box.append(el("b", null, String(value)), document.createTextNode(` ${label}`));
    facts.append(box);
  };
  add(answer.facts.words || null, say.fact_words);
  add(answer.facts.seconds, say.fact_seconds);
  add(answer.facts.words_per_minute, say.fact_rate);
  if (facts.childElementCount) card.append(facts);

  const remark = el("div", `remark ${answer.verdict}`);
  remark.append(tile(TILE[answer.verdict] || "none"));
  const body = el("div");
  body.append(el("p", null, answer.summary));
  remark.append(body);
  card.append(remark);

  const steps = chain(answer);
  if (steps) card.append(steps);
  return card;
}

// The whole architecture, made visible for one answer: what was measured, what
// was decided from it, what the interviewer was told, and what it then asked.
// Without this the page shows a voice assistant having a chat, and the one thing
// that makes Probe different stays inside a pipe nobody can see.
function chain(answer) {
  if (!answer.instruction && !answer.measured_signals.length) return null;
  const box = el("div", "chain");
  box.append(el("p", "chain-title", say.chain));
  const steps = el("ol", "chain-steps");

  if (answer.measured_signals.length) {
    const step = el("li", "chain-step");
    step.append(el("span", "chain-what", say.measured));
    const gauges = el("div", "gauges");
    for (const signal of answer.measured_signals) {
      const gauge = el("div", `gauge${signal.points_to_reading ? " points" : ""}`);
      gauge.append(el("b", null, signal.value),
                   el("span", "gauge-label", signal.label),
                   el("span", "gauge-unit", signal.unit));
      gauges.append(gauge);
    }
    step.append(gauges);
    steps.append(step);
  }

  const decided = el("li", "chain-step");
  decided.append(el("span", "chain-what", say.decided));
  decided.append(el("span", `chip ${answer.verdict}`, answer.title));
  if (answer.reasons.length) {
    const why = el("ul", "why");
    for (const reason of answer.reasons) why.append(el("li", null, reason));
    decided.append(why);
  }
  steps.append(decided);

  if (answer.instruction) {
    const told = el("li", "chain-step");
    told.append(el("span", "chain-what", say.told));
    told.append(el("blockquote", "instruction", answer.instruction));
    steps.append(told);
  }

  if (answer.then_asked) {
    const asked = el("li", "chain-step");
    asked.append(el("span", "chain-what", say.then_asked));
    asked.append(el("p", "asked", answer.then_asked));
    steps.append(asked);
  }

  box.append(steps);
  box.append(el("p", "chain-note", say.chain_note));
  return box;
}

function render(report) {
  say = report.labels || {};
  document.documentElement.lang = report.language || "en";
  const back = document.querySelector(".nav .back");
  if (back && say.all_interviews) back.textContent = say.all_interviews;

  const main = $("report");
  main.replaceChildren();
  main.append(el("h1", null, say.report_title), summary(report));

  if (report.next_steps.length) {
    main.append(el("h2", null, say.dig));
    for (const step of report.next_steps) main.append(stepCard(step));
  }

  main.append(el("h2", null, say.answers
    .replace("{compared}", String(report.counts.compared))
    .replace("{total}", String(report.counts.answers))));
  report.answers.forEach((answer, index) => main.append(answerCard(answer, index)));

  main.append(el("h2", null, say.limits));
  const card = el("section", "card");
  const limits = el("div", "limits");
  limits.append(tile("none"));
  const list = el("ul");
  for (const line of report.limits) list.append(el("li", null, line));
  limits.append(list);
  card.append(limits);
  main.append(card);

  if (report.turns.length) {
    main.append(el("h2", null, say.spoken));
    const talk = el("section", "card talk");
    for (const turn of report.turns) {
      const line = el("p", `turn ${turn.role}`);
      line.append(el("span", null, turn.role === "candidate" ? say.candidate : say.interviewer),
                  document.createTextNode(turn.text));
      talk.append(line);
    }
    main.append(talk);
  }
}

function fail(message, detail) {
  $("report").replaceChildren(el("h1", null, message), el("p", "meta", detail));
}

async function load() {
  const id = new URLSearchParams(location.search).get("id");
  if (!id) return fail("No interview asked for", "This page needs an interview id in its address.");
  try {
    const response = await fetch(`/api/report/${encodeURIComponent(id)}`);
    if (response.status === 404) return fail("No such interview", "It may have been removed.");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const built = await response.json();
    render(built);
    document.title = `${built.labels?.report_title || "Interview report"} - Probe`;
  } catch (error) {
    fail("The report could not be loaded", `${error.message}. Reload the page in a moment.`);
  }
}

load();
