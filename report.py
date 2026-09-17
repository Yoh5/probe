"""Probe - what the recruiter reads after the interview.

The report is built from the saved session, never from a fresh opinion: every
verdict in it was computed by `assess.py` while the interview was running, and is
repeated here with the facts it was based on. Nothing is re-judged, and nothing is
judged that was not measured.

Three rules carried through from Unscripted:

- THE MODEL OBSERVES, THE CODE DECIDES. The language model conducting the
  interview never decided anything that appears here.
- NOTHING MEASURED IS NOT A PASS. An answer too short to compare says exactly
  that, and counts towards nothing.
- A REPORT SUGGESTS, IT NEVER CONCLUDES. It says what to ask about at the next
  interview. It does not rank, score or recommend a candidate.
"""
from __future__ import annotations

import detector

# What a signal means, in a sentence a recruiter can act on. Same wording the
# interviewer was given, so the report and the interview cannot disagree.
TITLES = {
    "prepared": "Sounds prepared",
    "spontaneous": "Sounds thought through on the spot",
    "not_measured": "Too short to compare",
    "baseline": "Warm-up, used as the comparison",
}

SUMMARIES = {
    "prepared": "worth asking about again, in person",
    "spontaneous": "nothing here suggests a rehearsed answer",
    "not_measured": "not enough speech to say anything either way",
    "baseline": "this is what the other answers were compared against",
}


def _text(words: list[dict]) -> str:
    return " ".join(str(w.get("text", "")) for w in words).strip()


def _seconds(words: list[dict]) -> float | None:
    """How long the answer ran, from the first word to the last, in seconds."""
    if len(words) < 2:
        return None
    return round((words[-1]["end"] - words[0]["start"]) / 1000, 1)


def _speech_rate(words: list[dict]) -> int | None:
    span = _seconds(words)
    if not span or span < 1:
        return None
    return round(len(words) / span * 60)


def question_before(turns: list[dict], began_ms: float) -> str:
    """The last thing the interviewer said before this answer started.

    Turns and words share the audio clock, so this is a comparison rather than a
    guess. Counting turns instead would drift: the transcription splits one spoken
    answer into several turns whenever the candidate pauses, while the interviewer
    asks for one assessment per answer.
    """
    asked = [t for t in turns
             if t.get("role") == "interviewer"
             and isinstance(t.get("at"), (int, float)) and t["at"] <= began_ms]
    return str(asked[-1].get("text", "")).strip() if asked else ""


def _words_of(assessment: dict) -> list[dict]:
    """The answer's words, when the session has them.

    Sessions recorded before this was stored kept only a count under the same
    name; a count is not a list, and the report says less about those rather than
    inventing the difference.
    """
    words = assessment.get("answer_words")
    if isinstance(words, list) and all(isinstance(w, dict) for w in words):
        return words
    stored = assessment.get("words")
    return stored if isinstance(stored, list) and all(isinstance(w, dict) for w in stored) else []


def _counted(assessment: dict) -> int:
    """The word count the interview recorded, for sessions that kept only that."""
    for key in ("words", "answer_words"):
        stored = assessment.get(key)
        if isinstance(stored, int) and not isinstance(stored, bool):
            return stored
    return 0


# What a recruiter should do about each kind of answer, in the second interview.
# The measurement never decides anything about a candidate; it decides what is
# worth thirty more seconds of a human being's time.
NEXT = {
    "prepared": ("Ask for the parts a rehearsal does not contain",
                 "This answer came out polished. That is not misconduct and it is not a "
                 "finding about the candidate - it is a sign that the ground underneath it "
                 "was not tested."),
    "not_measured": ("Not covered - ask it again",
                     "There was not enough here to go on. The topic is still open."),
    "missed": ("Never came up",
               "The interview ran out of questions before reaching this."),
}


def _steps(answers: list[dict], brief: dict | None) -> list[dict]:
    """What to dig into at the next interview, and why.

    This is the report. Everything below it is the evidence behind it: a recruiter
    who reads nothing else should still know what to do with their next half hour.

    One line per TOPIC, never one per answer. A topic that took four turns to get
    nowhere is one thing to go back over, not four, and a recruiter handed the same
    sentence four times stops reading the list.
    """
    goals = {t["id"]: t["goal"] for t in (brief or {}).get("topics", [])}
    order = list(goals) + [a["topic_id"] for a in answers if a["topic_id"] not in goals]
    by_topic: dict[str, list[dict]] = {}
    for answer in answers:
        if answer["verdict"] != "baseline":
            by_topic.setdefault(answer["topic_id"], []).append(answer)

    steps = []
    for topic_id in dict.fromkeys(order):
        got = by_topic.get(topic_id, [])
        prepared = [a for a in got if a["verdict"] == "prepared"]
        if prepared:
            kind, about = "prepared", prepared
        elif any(a["verdict"] == "spontaneous" for a in got):
            continue      # answered, and nothing about it asks for a second look
        elif got:
            kind, about = "not_measured", got
        elif topic_id in goals:
            kind, about = "missed", []
        else:
            continue
        title, why = NEXT[kind]
        claims = [a["claim"] for a in about if a["claim"]]
        reasons = [r for a in about for r in a["reasons"]]
        steps.append({
            "kind": kind,
            "title": title,
            "why": why,
            "topic_id": topic_id,
            "goal": goals.get(topic_id, ""),
            "claim": claims[-1] if claims else "",
            "question": next((a["question"] for a in reversed(about) if a["question"]), ""),
            "reasons": list(dict.fromkeys(reasons)),
        })
    return steps


# Each measured signal, in words and in the unit it is actually in. Three of the
# four are ratios against the candidate's own warm-up, which is the point: the
# comparison is always to the same person a minute earlier, never to other people.
SIGNALS = {
    "long_word_share/base": ("Long words", "against their own warm-up", "ratio"),
    "disfluency_rate": ("Hesitations and restarts", "per 100 words", "rate"),
    "comma_rate/base": ("Clause breaks", "against their own warm-up", "ratio"),
    "mean_run/base": ("Words between pauses", "against their own warm-up", "ratio"),
}


# The reverse of detector.EXPLANATIONS. Sessions recorded before the signal names
# were stored still carry the sentences they produced, and a sentence names its
# signal exactly once.
FROM_REASON = {reason: name for name, reason in detector.EXPLANATIONS.items()}


def _pointed(assessment: dict) -> set[str]:
    """Which signals leaned towards a prepared answer, by name."""
    stored = assessment.get("pointed")
    if isinstance(stored, list):
        return set(stored)
    return {FROM_REASON[r] for r in assessment.get("reasons") or [] if r in FROM_REASON}


def _measured(assessment: dict) -> list[dict]:
    """What the code actually looked at, in the order the model was fitted on."""
    signals = assessment.get("signals") or {}
    pointed = _pointed(assessment)
    out = []
    for name, (label, unit, kind) in SIGNALS.items():
        value = signals.get(name)
        if not isinstance(value, (int, float)):
            continue
        out.append({
            "name": name,
            "label": label,
            "unit": unit,
            "value": f"{value:.2f}x".replace("x", "×") if kind == "ratio" else f"{value:.1f}",
            "points_to_reading": name in pointed,
        })
    return out


def _then_asked(turns: list[dict], words: list[dict]) -> str:
    """The question the interviewer asked once it had been told what to do.

    The last link in the chain, and the one that makes the rest of it checkable: a
    reader can see the measurement, the instruction it produced, and the sentence
    that came out of the interviewer's mouth afterwards.
    """
    if not words:
        return ""
    ended = words[-1]["end"]
    after = [t for t in turns
             if t.get("role") == "interviewer"
             and isinstance(t.get("at"), (int, float)) and t["at"] >= ended]
    return str(after[0].get("text", "")).strip() if after else ""


def _answer(assessment: dict, turns: list[dict]) -> dict:
    words = _words_of(assessment)
    verdict = assessment.get("verdict", "not_measured")
    # Without the answer's own words there is no way to say which question it
    # followed, so the report says nothing rather than the wrong thing. What was
    # assessed is still shown: `quote` was taken from the answer itself.
    question = question_before(turns, words[0]["start"]) if words else ""
    reasons = assessment.get("reasons") or []
    return {
        "topic_id": assessment.get("topic_id", ""),
        "claim": str(assessment.get("claim", "")).strip(),
        "question": question,
        "said": _text(words) or str(assessment.get("quote", "")).strip(),
        "excerpt": not words,          # what is shown is the closing words, not all of them
        "verdict": verdict,
        "title": TITLES.get(verdict, TITLES["not_measured"]),
        "summary": SUMMARIES.get(verdict, SUMMARIES["not_measured"]),
        "measured": bool(assessment.get("measured")),
        "reasons": reasons,
        "score": assessment.get("score"),
        "threshold": assessment.get("threshold"),
        # The chain, end to end: what was measured, what the code decided from it,
        # and what the interviewer said next. The model never saw the numbers and
        # never chose the instruction; it chose the wording of the question.
        "measured_signals": _measured(assessment),
        "instruction": str(assessment.get("instruction", "")).strip(),
        "then_asked": _then_asked(turns, words),
        "facts": {
            "words": len(words) or _counted(assessment),
            "seconds": _seconds(words),
            "words_per_minute": _speech_rate(words),
        },
    }


def limits(model: dict | None = None) -> list[str]:
    """What this report cannot tell you. It is part of the report, not a footnote.

    Every line here is a fact about how the detector was built, taken from the
    model itself where possible, so it cannot drift away from the truth as the
    model is refit.
    """
    model = model or detector.load()
    trained = model.get("trained_on", {})
    answers = trained.get("answers")
    speakers = trained.get("speakers")
    accuracy = (model.get("unseen_session_accuracy") or {}).get("balanced_accuracy")
    lines = [
        "This measures how an answer was delivered, never whether it was true, and "
        "never whether the candidate is any good at the job.",
        "An answer can sound prepared because the candidate rehearsed, because they "
        "have told the story many times, or because that is how they speak. The "
        "report cannot tell those apart, and neither can anyone else from a recording.",
        "Reading from notes is not misconduct. Treat a flag as something to ask "
        "about, never as a reason to reject.",
    ]
    if answers:
        who = "one speaker" if speakers == 1 else f"{speakers} speakers"
        lines.append(f"The detector was fitted on {answers} labelled answers from {who}, "
                     "and the signals were chosen after looking at that data. It has not "
                     "been tested on a speaker it was not fitted on.")
    if accuracy:
        lines.append(f"Held out one session at a time, it was right {round(accuracy * 100)}% "
                     "of the time. It will be wrong about some answers here.")
    return lines


def build(session: dict, model: dict | None = None, brief: dict | None = None) -> dict:
    """The whole report for one saved interview.

    It opens on what to do next, not on what was measured. A recruiter reading this
    has already decided to spend five minutes on the candidate; what they need is
    the half hour after it spent well.
    """
    model = model or detector.load()
    turns = session.get("turns") or []
    assessments = session.get("assessments") or []

    answers = [_answer(a, turns) for a in assessments]
    graded = [a for a in answers if a["verdict"] in ("prepared", "spontaneous")]
    flagged = [a for a in graded if a["verdict"] == "prepared"]
    steps = _steps(answers, brief)

    if steps:
        headline = ("One thing to dig into at the next interview." if len(steps) == 1
                    else f"{len(steps)} things to dig into at the next interview.")
        status = "flag" if any(s["kind"] == "prepared" for s in steps) else "none"
    elif graded:
        headline = "Nothing here needs a second look."
        status = "clear"
    else:
        headline = "This interview produced nothing to go on."
        status = "none"

    spoken = sum(a["facts"]["words"] or 0 for a in answers)
    return {
        "recorded_at": session.get("recordedAt", ""),
        "language": session.get("language", ""),
        "headline": headline,
        "status": status,
        "next_steps": steps,
        "counts": {
            "answers": len(answers),
            "compared": len(graded),
            "flagged": len(flagged),
            "words_spoken": spoken,
        },
        "answers": answers,
        "turns": [{"role": t.get("role", ""), "text": str(t.get("text", ""))} for t in turns],
        "limits": limits(model),
    }
