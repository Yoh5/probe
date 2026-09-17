"""Probe - does this answer sound prepared, and what should the interviewer do next?

The voice agent calls the `assess_answer` tool when a candidate finishes an
answer. This module turns the AssemblyAI words of that answer into the result the
agent reads: a decision computed by code, the reasons behind it, and a single
instruction for the next thing to say.

Two rules carried over from Unscripted:

- THE MODEL OBSERVES, THE CODE DECIDES. The language model conducting the
  interview never judges whether an answer was read. It receives the verdict and
  its reasons, and chooses the wording of the follow-up.
- NOTHING MEASURED IS NOT A PASS. An answer too short to measure, or a warm-up
  too short to compare against, says so and asks for nothing.
"""
from __future__ import annotations

import detector
import features

MIN_WORDS = 25
MIN_BASELINE_WORDS = 15

# Above the floor, a verdict is still only as steady as the speech it was computed
# from. Three of the four signals are rates, and a rate over a short answer swings
# on a single word: one extra hesitation moves the z-score by 1.66 standard
# deviations in a 25-word answer, 0.92 in a 45-word one, 0.69 in a 60-word one.
# 41 words is where one hesitation stops moving it by a whole deviation, so an
# answer under 45 is reported as a lean rather than a finding.
#
# This is the honest form of something obvious: a short answer is rarely a
# prepared one. There is not enough of it to have been prepared, and not enough of
# it to tell.
SOLID_WORDS = 45

# AssemblyAI's streaming transcript keeps filler words verbatim but does not tag
# them, so they are recognised by their text.
FILLERS = {"um", "uh", "uhm", "umm", "er", "erm", "ah", "hmm", "mm", "mhm"}


def from_assemblyai(words: list[dict]) -> list[dict]:
    """AssemblyAI streaming words (milliseconds) into the shape features.py reads (seconds)."""
    out = []
    for w in words:
        text = str(w.get("text", ""))
        bare = text.strip(" ,.?!;:").lower()
        out.append({
            "text": text,
            "start": w["start"] / 1000,
            "end": w["end"] / 1000,
            "confidence": w.get("confidence"),
            "disfluency": bare in FILLERS,
            "boundary": text.rstrip().endswith((".", "?", "!")),
        })
    return out


def words_between(words: list[dict], start_s: float, end_s: float | None) -> list[dict]:
    """The words that started inside [start_s, end_s)."""
    return [w for w in words if w["start"] >= start_s and (end_s is None or w["start"] < end_s)]


QUOTE_WORDS = 20


def quote_of(answer: list[dict]) -> str:
    """The candidate's own closing words, verbatim from the transcript.

    The agent summarises what it heard when it calls the tool; the summary is
    already one step away from what was said. Handing the real words back is what
    lets the next question be built on them.
    """
    return " ".join(str(w["text"]) for w in answer[-QUOTE_WORDS:]).strip()


def _ground(quote: str) -> str:
    """The sentence every instruction ends on, whatever the verdict.

    A question drawn from a topic heading is a question the candidate could have
    answered before hearing it - the exact thing this interview is built to stop.
    So every result, even a clean one, makes the next question come out of the
    candidate's own words.
    """
    if not quote:
        return ("Build the next question on what the candidate just said, not on a topic heading. "
                "It must be a question they could not have answered before speaking.")
    return (f'These are the candidate\'s own closing words: "{quote}". Take one phrase from them '
            "and put it word for word inside your next question, then ask for what only the person "
            "who lived it would know.")


def closing(quote: str = "") -> str:
    """What to say when the interview has used up its questions.

    The count is kept by code rather than by the model, because a model asked to
    count its own questions will keep finding one more worth asking - which is how
    a five minute screening becomes twenty.
    """
    return ("That was the last question of the interview: the allowance is used up. Do not ask "
            "another one, not even a short one. Thank the candidate in one sentence and call "
            "end_interview now.")


def _guidance(kind: str, reasons: list[str], quote: str = "") -> str:
    ground = _ground(quote)
    if kind == "prepared":
        because = "; ".join(reasons) if reasons else "several signals lean that way"
        return ("This answer sounds prepared rather than thought through on the spot "
                f"({because}). Ask exactly one short follow-up that a script cannot cover: a concrete "
                "number, the first thing that broke, a trade-off they chose, who disagreed, or how "
                f"they found out they were wrong. {ground} Never say or hint that the answer sounded "
                "prepared or read.")
    if kind == "spontaneous":
        return ("This answer sounds spontaneous, so there is nothing to press on for its own sake. "
                f"Move the interview forward. {ground}")
    if kind == "baseline":
        return ("That was the warm-up. Do not dig into it. Open the first topic with one short "
                f"question. {ground}")
    return ("There is not enough here to assess, which is not a finding about the candidate. Do not "
            f"press them about it. Ask one short question that takes the thread further. {ground}")


def assess(answer: list[dict], baseline: list[dict] | None, model: dict | None = None,
           asked: int | None = None, limit: int | None = None) -> dict:
    """The verdict for one answer, in words the agent and the report can both use.

    `answer` and `baseline` are words already converted by `from_assemblyai`.
    Pass `baseline=None` when assessing the warm-up itself.
    """
    model = model or detector.load()
    result = {"words": len(answer), "measured": False, "sounds_prepared": None,
              "score": None, "threshold": model["threshold"], "reasons": [], "signals": {}}

    quote = quote_of(answer)
    result["quote"] = quote
    result["confidence"] = "solid" if len(answer) >= SOLID_WORDS else "thin"
    # The verdict is still computed and still reported: the interview ends because
    # it has run out of questions, not because of anything the candidate said.
    result["last"] = bool(asked is not None and limit is not None and asked >= limit)

    def finish(verdict: dict) -> dict:
        if verdict["last"]:
            verdict["instruction"] = closing(quote)
        return verdict

    if baseline is None:
        # The warm-up is what every later answer is compared against, so it has to
        # be long enough to be one. A short warm-up used to be accepted anyway, and
        # then nothing else in the interview could be measured against it - the
        # whole interview came back "not measured". The interviewer stays on the
        # warm-up until there is enough of it.
        result["verdict"] = "baseline"
        result["baseline_ready"] = len(answer) >= MIN_BASELINE_WORDS
        if result["baseline_ready"]:
            result["instruction"] = _guidance("baseline", [], quote)
        else:
            result["instruction"] = (
                "The warm-up is still too short to compare later answers against. Stay on it: ask them "
                "for a little more of the same thing, one or two sentences, without changing the subject "
                "and without saying why you are asking.")
        return finish(result)
    if len(answer) < MIN_WORDS or len(baseline) < MIN_BASELINE_WORDS:
        result["verdict"] = "not_measured"
        result["instruction"] = _guidance("not_measured", [], quote)
        return finish(result)

    own = features.extract(answer, None)
    base = features.extract(baseline, None)
    row = {**own, **features.relative(own, base)}
    scored = detector.score(row, model)
    result["signals"] = {s["name"]: row.get(s["name"]) for s in model["signals"]}
    if scored["score"] is None:
        result["verdict"] = "not_measured"
        result["instruction"] = _guidance("not_measured", [], quote)
        return finish(result)

    reasons = [detector.EXPLANATIONS[n] for n in scored["pointing_to_reading"] if n in detector.EXPLANATIONS]
    kind = "prepared" if scored["suggests_reading"] else "spontaneous"
    # A short answer that scores as prepared is not worth pressing on its own
    # terms - there is too little of it for the score to be steady. What it is
    # worth is more of the same answer, so the next one can be measured properly.
    if kind == "prepared" and result["confidence"] == "thin":
        result.update(measured=True, sounds_prepared=True, score=scored["score"],
                      reasons=reasons, verdict=kind, pointed=scored["pointing_to_reading"],
                      instruction=(
                          "This answer leans towards prepared, but it is short enough that the "
                          "measurement is not steady - so do not press it as though it were settled. "
                          "Ask them to take you further into the same thing they just described, in "
                          f"more detail. {_ground(quote)}"))
        return finish(result)
    result.update(measured=True, sounds_prepared=scored["suggests_reading"], score=scored["score"],
                  reasons=reasons if kind == "prepared" else [], verdict=kind,
                  # Which signals leaned that way, by name: the report shows the
                  # numbers, and a reader should not have to work out which of the
                  # four mattered.
                  pointed=scored["pointing_to_reading"],
                  instruction=_guidance(kind, reasons, quote))
    return finish(result)
