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
  flag: "M12 3.4 21.2 19H2.8z M12 9.6v3.9 M12 16.3v.1",
  clear: "M4.5 12.5 9.5 17.5 19.5 6.5",
  none: "M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17z M8.5 12h7",
  brand: "M4 18V9 M10 18V5 M16 18v-7",
};
const WORDS = {
  flag: "Worth a second look",
  clear: "Nothing flagged",
  none: "Nothing comparable",
};
const TILE = { prepared: "flag", spontaneous: "clear", baseline: "brand", not_measured: "none" };

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
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", ICONS[kind] || ICONS.none);
  svg.append(path);
  box.append(svg);
  return box;
}

function when(iso) {
  const at = new Date(iso || "");
  return Number.isNaN(at.valueOf()) ? "" : at.toLocaleString(undefined, {
    year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

function stat(value, label) {
  const box = el("div", "stat");
  box.append(el("b", null, String(value)), el("span", null, label));
  return box;
}

function summary(report) {
  const card = el("section", "card");
  const head = el("div", "summary-head");
  head.append(tile(report.status === "flag" ? "flag" : report.status === "clear" ? "clear" : "none"),
              el("p", "headline", report.headline));
  card.append(head);

  const meta = [when(report.recorded_at), (report.language || "").toUpperCase(),
                WORDS[report.status] || WORDS.none].filter(Boolean);
  card.append(el("p", "meta", meta.join("  ·  ")));

  const stats = el("div", "stats");
  stats.append(stat(report.counts.answers, "answers"),
               stat(report.counts.compared, "compared"),
               stat(report.counts.flagged, "sound prepared"),
               stat(report.counts.words_spoken, "words spoken"));
  card.append(stats);
  return card;
}

function answerCard(answer, index) {
  const card = el("section", "card");

  card.append(el("span", `chip ${answer.verdict}`, answer.title));
  card.append(answer.question
    ? el("p", "asked", answer.question)
    : el("p", "asked unknown", `Question ${index + 1} - not recorded with this interview`));

  if (answer.said) {
    const quote = el("blockquote", "said-quote");
    if (answer.excerpt) quote.append(el("span", "partial", "Closing words of the answer"));
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
  add(answer.facts.words || null, "words");
  add(answer.facts.seconds, "seconds");
  add(answer.facts.words_per_minute, "words a minute");
  if (facts.childElementCount) card.append(facts);

  const remark = el("div", `remark ${answer.verdict}`);
  remark.append(tile(TILE[answer.verdict] || "none"));
  const body = el("div");
  body.append(el("p", null, answer.summary));
  if (answer.reasons.length) {
    const why = el("ul");
    for (const reason of answer.reasons) why.append(el("li", null, reason));
    body.append(why);
  }
  remark.append(body);
  card.append(remark);
  return card;
}

function render(report) {
  const main = $("report");
  main.replaceChildren();
  main.append(el("h1", null, "Interview report"), summary(report));

  main.append(el("h2", null, `Answers (${report.counts.compared} of ${report.counts.answers} could be compared)`));
  report.answers.forEach((answer, index) => main.append(answerCard(answer, index)));

  main.append(el("h2", null, "What this report cannot tell you"));
  const card = el("section", "card");
  const limits = el("div", "limits");
  limits.append(tile("none"));
  const list = el("ul");
  for (const line of report.limits) list.append(el("li", null, line));
  limits.append(list);
  card.append(limits);
  main.append(card);

  if (report.turns.length) {
    main.append(el("h2", null, "The interview, as it was spoken"));
    const talk = el("section", "card talk");
    for (const turn of report.turns) {
      const line = el("p", `turn ${turn.role}`);
      line.append(el("span", null, turn.role === "candidate" ? "Candidate" : "Interviewer"),
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
    render(await response.json());
  } catch (error) {
    fail("The report could not be loaded", `${error.message}. Reload the page in a moment.`);
  }
}

load();
