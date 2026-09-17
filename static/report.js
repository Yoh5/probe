// Probe - the recruiter's report for one interview.
//
// Everything here was decided while the interview was running. This page reads
// the saved session back and lays it out; it never scores anything, so it cannot
// disagree with the interview it describes.
//
// Every value that came from a candidate's mouth reaches the DOM through
// textContent. A transcript is user input, and it is displayed, never parsed.

const $ = (id) => document.getElementById(id);

const CHIPS = {
  flag: "Worth a second look",
  clear: "Nothing flagged",
  none: "Nothing comparable",
};

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function when(iso) {
  if (!iso) return "";
  const at = new Date(iso);
  return Number.isNaN(at.valueOf()) ? "" : at.toLocaleString(undefined, {
    year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

function section(title) {
  return el("h2", null, title);
}

function answerBlock(answer, index) {
  const block = el("article", "answer");

  const chip = el("span", `verdict-chip ${answer.verdict}`, answer.title);
  block.append(chip);

  const asked = answer.question
    ? el("p", "asked", answer.question)
    : el("p", "asked unknown", `Question ${index + 1} - not recorded with this interview`);
  block.append(asked);

  if (answer.said) {
    const said = el("blockquote", "said");
    if (answer.excerpt) said.append(el("span", "partial", "Closing words of the answer"));
    said.append(document.createTextNode(answer.said));
    block.append(said);
  }

  const facts = el("p", "facts");
  const add = (label, value) => {
    if (value === null || value === undefined) return;
    const item = el("span");
    item.append(el("b", null, String(value)), document.createTextNode(` ${label}`));
    facts.append(item);
  };
  add("words", answer.facts.words || null);
  add("seconds", answer.facts.seconds);
  add("words a minute", answer.facts.words_per_minute);
  if (facts.childElementCount) block.append(facts);

  if (answer.reasons.length) {
    const why = el("ul", "why");
    for (const reason of answer.reasons) why.append(el("li", null, reason));
    block.append(why);
  } else {
    block.append(el("p", "why", answer.summary));
  }
  return block;
}

function render(report) {
  const main = $("report");
  main.replaceChildren();

  main.append(el("h1", null, report.headline));
  const meta = el("p", "meta");
  const parts = [when(report.recorded_at), report.language && report.language.toUpperCase(),
                 `${report.counts.words_spoken} words spoken`].filter(Boolean);
  meta.textContent = parts.join("  ·  ");
  const badge = el("p");
  badge.append(el("span", `verdict-chip ${report.status}`, CHIPS[report.status] || CHIPS.none));
  main.append(meta, badge);

  main.append(section(`Answers (${report.counts.compared} of ${report.counts.answers} could be compared)`));
  report.answers.forEach((answer, index) => main.append(answerBlock(answer, index)));

  main.append(section("What this report cannot tell you"));
  const limits = el("div", "limits");
  const list = el("ul");
  for (const line of report.limits) list.append(el("li", null, line));
  limits.append(list);
  main.append(limits);

  if (report.turns.length) {
    main.append(section("The interview, as it was spoken"));
    const talk = el("div", "talk");
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
  const main = $("report");
  main.replaceChildren(el("h1", null, message), el("p", "meta", detail));
}

async function load() {
  const id = new URLSearchParams(location.search).get("id");
  if (!id) return fail("No interview asked for", "This page needs an interview id in its address.");
  try {
    const response = await fetch(`/api/report/${encodeURIComponent(id)}`);
    if (response.status === 404) return fail("No such interview", "It may have been removed.");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    render(await response.json());
    document.title = "Interview report - Probe";
  } catch (error) {
    fail("The report could not be loaded", `${error.message}. Reload the page in a moment.`);
  }
}

load();
