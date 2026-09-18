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
import strings

def words_for(language: str) -> dict:
    """The report's whole vocabulary, in the language the interview was held in.

    Not the reader's language: a candidate answers in theirs and the recruiter
    reads the result, so the report follows the interview. An unknown code falls
    back to English rather than to half a page of missing strings.
    """
    return strings.STRINGS.get((language or "").lower(), strings.STRINGS["en"])


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


def _words_of(assessment: dict, transcript: list[dict]) -> list[dict]:
    """The answer's words: a slice of the transcript, which is where they live.

    Three shapes have been stored over time. Newest is a pair of indices into the
    session's own word list, which is the only one that does not keep a second copy
    of every word. Before that the words themselves were copied in, and before
    that only a count survived - a count is not a list, and the report says less
    about those sessions rather than inventing the difference.
    """
    start, stop = assessment.get("from"), assessment.get("to")
    if isinstance(start, int) and isinstance(stop, int) and not isinstance(start, bool):
        return [w for w in transcript[max(0, start):max(0, stop)] if isinstance(w, dict)]
    words = assessment.get("answer_words")
    if isinstance(words, list) and all(isinstance(w, dict) for w in words):
        return words
    stored = assessment.get("words")
    return stored if isinstance(stored, list) and all(isinstance(w, dict) for w in stored) else []


def _started_after(assessment: dict) -> float | None:
    """How long the candidate took to start, in seconds, when the page timed it."""
    ms = assessment.get("started_after_ms")
    if not isinstance(ms, (int, float)) or isinstance(ms, bool) or ms < 0:
        return None
    return round(ms / 1000, 1)


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


def _steps(answers: list[dict], brief: dict | None, say: dict) -> list[dict]:
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
        title, why = say[f"step_{kind}"], say[f"why_{kind}"]
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


# The reverse of detector.EXPLANATIONS. Sessions recorded before the signal names
# were stored still carry the English sentences they produced, and a sentence
# names its signal exactly once.
FROM_REASON = {reason: name for name, reason in detector.EXPLANATIONS.items()}


def _pointed(assessment: dict) -> set[str]:
    """Which signals leaned towards a prepared answer, by name."""
    stored = assessment.get("pointed")
    if isinstance(stored, list):
        return set(stored)
    return {FROM_REASON[r] for r in assessment.get("reasons") or [] if r in FROM_REASON}


def _measured(assessment: dict, say: dict) -> list[dict]:
    """What the code actually looked at, in the order the model was fitted on."""
    signals = assessment.get("signals") or {}
    pointed = _pointed(assessment)
    out = []
    for name, kind in strings.SIGNAL_KINDS.items():
        value = signals.get(name)
        if not isinstance(value, (int, float)):
            continue
        out.append({
            "name": name,
            "label": say[f"signal_{name}"],
            "unit": say["unit_ratio"] if kind == "ratio" else say["unit_rate"],
            "value": f"{value:.2f}×" if kind == "ratio" else f"{value:.1f}",
            "points_to_reading": name in pointed,
        })
    return out


def _answer(assessment: dict, turns: list[dict], say: dict, transcript: list[dict]) -> dict:
    words = _words_of(assessment, transcript)
    verdict = assessment.get("verdict", "not_measured")
    if verdict not in ("prepared", "spontaneous", "baseline", "not_measured"):
        verdict = "not_measured"
    # The question is recorded with the answer, by the page, at the moment the
    # answer is assessed - it is the one on screen. Older sessions did not store
    # it, and for those it is worked out from the clock.
    question = str(assessment.get("question", "")).strip()
    if not question and words:
        question = question_before(turns, words[0]["start"])
    # Built from the signal names rather than repeated from the stored English, so
    # the reasons speak the same language as the rest of the page.
    reasons = [say[f"reason_{name}"] for name in strings.SIGNAL_KINDS if name in _pointed(assessment)]
    return {
        "topic_id": assessment.get("topic_id", ""),
        "claim": str(assessment.get("claim", "")).strip(),
        "question": question,
        "said": _text(words) or str(assessment.get("quote", "")).strip(),
        "excerpt": not words,          # what is shown is the closing words, not all of them
        "verdict": verdict,
        "title": say[f"verdict_{verdict}"],
        "summary": say[f"summary_{verdict}"],
        "measured": bool(assessment.get("measured")),
        # How steady the verdict is, which is a question about how much speech it
        # was computed from, not about the candidate.
        "confidence": assessment.get("confidence") or ("solid" if len(words) >= 45 else "thin"),
        "reasons": reasons,
        "score": assessment.get("score"),
        "threshold": assessment.get("threshold"),
        # The chain, end to end: what was measured, what the code decided from it,
        # and what the interviewer said next. The model never saw the numbers and
        # never chose the instruction; it chose the wording of the question.
        "measured_signals": _measured(assessment, say),
        "instruction": str(assessment.get("instruction", "")).strip(),
        "then_asked": "",      # filled in below: it is the next answer's question
        "facts": {
            "words": len(words) or _counted(assessment),
            "seconds": _seconds(words),
            "words_per_minute": _speech_rate(words),
            "started_after": _started_after(assessment),
        },
    }


def limits(model: dict | None = None, language: str = "en") -> list[str]:
    """What this report cannot tell you. It is part of the report, not a footnote.

    Every line here is a fact about how the detector was built, taken from the
    model itself where possible, so it cannot drift away from the truth as the
    model is refit.
    """
    model = model or detector.load()
    say = words_for(language)
    trained = model.get("trained_on", {})
    answers = trained.get("answers")
    speakers = trained.get("speakers")
    accuracy = (model.get("unseen_session_accuracy") or {}).get("balanced_accuracy")
    lines = [say["limit_delivery"], say["limit_reasons"], say["limit_notes"]]
    if answers:
        who = say["one_speaker"] if speakers == 1 else say["many_speakers"].format(n=speakers)
        lines.append(say["limit_fitted"].format(answers=answers, who=who))
    if accuracy:
        lines.append(say["limit_accuracy"].format(percent=round(accuracy * 100)))
    return lines


def scale_of(answers: list[dict], model: dict) -> dict | None:
    """Every measured answer on one axis, with the line the decision was made on.

    One number per answer, and the only thing that matters is which side of the
    line it falls. Without it the scores are four decimals in a list and a reader
    has no way to see that one answer sat a hair from the line while another was
    nowhere near it.
    """
    threshold = model.get("threshold")
    scored = [a for a in answers if isinstance(a.get("score"), (int, float))]
    if not scored or not isinstance(threshold, (int, float)):
        return None
    values = [a["score"] for a in scored] + [threshold]
    low, high = min(values), max(values)
    margin = max((high - low) * 0.18, 0.35)      # never a dot pinned to the edge
    low, high = low - margin, high + margin
    span = high - low
    return {
        "low": round(low, 3),
        "high": round(high, 3),
        "threshold": round(threshold, 3),
        "threshold_at": round((threshold - low) / span * 100, 2),
        "marks": [{
            "topic_id": a["topic_id"],
            "verdict": a["verdict"],
            "score": round(a["score"], 2),
            "at": round((a["score"] - low) / span * 100, 2),
        } for a in scored],
    }


def build(session: dict, model: dict | None = None, brief: dict | None = None) -> dict:
    """The whole report for one saved interview.

    It opens on what to do next, not on what was measured. A recruiter reading this
    has already decided to spend five minutes on the candidate; what they need is
    the half hour after it spent well.
    """
    model = model or detector.load()
    language = str(session.get("language", "en") or "en").lower()
    say = words_for(language)
    turns = session.get("turns") or []
    assessments = session.get("assessments") or []

    transcript = session.get("words") or []
    answers = [_answer(a, turns, say, transcript) for a in assessments]
    # The last link in the chain, and the one that makes the rest of it checkable:
    # the question that followed an answer is the question of the next one.
    for earlier, later in zip(answers, answers[1:]):
        earlier["then_asked"] = later["question"]
    graded = [a for a in answers if a["verdict"] in ("prepared", "spontaneous")]
    flagged = [a for a in graded if a["verdict"] == "prepared"]
    steps = _steps(answers, brief, say)

    # "Nothing to dig into" out of two comparable answers in seven is not a clean
    # interview, it is a thin one, and the two must not read the same.
    thin = bool(answers) and len(graded) * 2 < len(answers)

    if steps:
        headline = say["head_one"] if len(steps) == 1 else say["head_many"].format(n=len(steps))
        status = "flag" if any(s["kind"] == "prepared" for s in steps) else "none"
    elif not graded:
        headline = say["head_empty"]
        status = "none"
    elif thin:
        headline = say["head_thin"].format(compared=len(graded), total=len(answers))
        status = "none"
    else:
        headline = say["head_clear"]
        status = "clear"

    spoken = sum(a["facts"]["words"] or 0 for a in answers)
    return {
        "recorded_at": session.get("recordedAt", ""),
        "language": session.get("language", ""),
        "headline": headline,
        "status": status,
        "next_steps": steps,
        "scale": scale_of(answers, model),
        "thin": thin,
        "counts": {
            "answers": len(answers),
            "compared": len(graded),
            "flagged": len(flagged),
            "words_spoken": spoken,
        },
        "answers": answers,
        "turns": [{"role": t.get("role", ""), "text": str(t.get("text", ""))} for t in turns],
        "limits": limits(model, language),
        # Every label the page shows, in the same language, so the page holds no
        # words of its own and a missing translation cannot hide behind English.
        "labels": say,
    }
