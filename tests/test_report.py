"""The recruiter's report: what it says, and what it refuses to say."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import report  # noqa: E402
from test_assess import MODEL  # noqa: E402


def words(text, start_ms):
    """Words shaped like a saved answer: milliseconds, in order."""
    out, at = [], start_ms
    for token in text.split():
        out.append({"text": token, "start": at, "end": at + 260})
        at += 300
    return out


def session(**over):
    answer_one = words("I got up early and went to the gym before work", 3000)
    answer_two = words("The first file that broke was the export from the old system", 20000)
    base = {
        "recordedAt": "2026-09-17T09:00:00Z",
        "language": "en",
        "turns": [
            {"role": "interviewer", "text": "What did you do yesterday?", "at": 1000},
            {"role": "candidate", "text": "I got up early...", "at": 9000},
            {"role": "interviewer", "text": "You said the delimiters broke - which file?", "at": 16000},
            {"role": "candidate", "text": "The first file...", "at": 27000},
        ],
        "assessments": [
            {"topic_id": "warmup", "verdict": "baseline", "measured": False, "reasons": [],
             "quote": "before work", "answer_words": answer_one},
            {"topic_id": "project", "verdict": "prepared", "measured": True, "score": 0.9,
             "threshold": -0.2, "reasons": ["vocabulary closer to written text than in the warm-up"],
             "pointed": ["long_word_share/base"], "claim": "the export broke",
             "instruction": "Ask exactly one short follow-up.",
             "signals": {"long_word_share/base": 2.18, "disfluency_rate": 3.0,
                         "comma_rate/base": 0.8, "mean_run/base": 1.19},
             "quote": "the old system", "answer_words": answer_two},
        ],
    }
    base.update(over)
    return base


def test_the_question_comes_from_the_clock_not_from_counting_turns():
    """The transcription splits one spoken answer into several turns whenever the
    candidate pauses. Counting turns would pair every later answer with the wrong
    question; comparing timestamps cannot drift."""
    noisy = session()
    noisy["turns"].insert(2, {"role": "candidate", "text": "...and then work", "at": 11000})
    built = report.build(noisy, MODEL)
    assert built["answers"][0]["question"] == "What did you do yesterday?"
    assert built["answers"][1]["question"] == "You said the delimiters broke - which file?"


def test_an_answer_with_no_stored_words_admits_it_does_not_know_the_question():
    """Sessions recorded before the answer words were kept cannot be paired. The
    report shows what was assessed and says nothing about which question it was."""
    old = session()
    for assessment in old["assessments"]:
        del assessment["answer_words"]
        assessment["words"] = 31               # the count that used to land under this name
    built = report.build(old, MODEL)
    for answer in built["answers"]:
        assert answer["question"] == ""
        assert answer["excerpt"] is True
        assert answer["said"]                   # the quote taken from the answer itself
    assert built["answers"][0]["facts"]["words"] == 31


BRIEF = {"topics": [{"id": "project", "goal": "What they built and what broke"},
                    {"id": "judgement", "goal": "How they behave when they are wrong"}]}


def test_the_report_opens_on_what_to_do_next():
    """A recruiter reading this has already spent the five minutes. What they need
    is the half hour after it spent well, not a measurement."""
    built = report.build(session(), MODEL, BRIEF)
    assert built["headline"] == "2 things to dig into at the next interview."
    assert built["status"] == "flag"
    assert built["counts"] == {"answers": 2, "compared": 1, "flagged": 1, "words_spoken": 23}


def test_a_polished_answer_becomes_one_thing_to_ask_about():
    step = report.build(session(), MODEL, BRIEF)["next_steps"][0]
    assert step["kind"] == "prepared" and step["topic_id"] == "project"
    assert step["goal"] == "What they built and what broke"
    assert step["reasons"] == ["vocabulary closer to written text than in the warm-up"]
    assert "not misconduct" in step["why"]


def test_a_topic_the_interview_never_reached_is_said_plainly():
    step = report.build(session(), MODEL, BRIEF)["next_steps"][-1]
    assert step["kind"] == "missed" and step["topic_id"] == "judgement"
    assert step["claim"] == "" and step["reasons"] == []


def test_one_line_per_topic_however_many_turns_it_took():
    """A topic that took four turns to get nowhere is one thing to go back over,
    not four. A recruiter handed the same sentence four times stops reading."""
    long_one = session()
    extra = dict(long_one["assessments"][1], verdict="not_measured", reasons=[], measured=False)
    long_one["assessments"] = [long_one["assessments"][0], extra, extra, extra,
                               long_one["assessments"][1]]
    steps = report.build(long_one, MODEL, BRIEF)["next_steps"]
    assert [s["topic_id"] for s in steps] == ["project", "judgement"]


def test_a_topic_answered_well_is_not_on_the_list():
    """Nothing to go back over is the point of the list being short."""
    fine = session()
    fine["assessments"][1].update(verdict="spontaneous", reasons=[])
    steps = report.build(fine, MODEL, BRIEF)["next_steps"]
    assert [s["topic_id"] for s in steps] == ["judgement"]      # only the one never reached


def test_nothing_comparable_is_not_a_pass():
    """An interview with nothing measurable in it says so, and is never reported as
    clear. A clear report and an empty one mean different things."""
    empty = session(assessments=[{"topic_id": "warmup", "verdict": "baseline",
                                  "quote": "um", "answer_words": []}])
    built = report.build(empty, MODEL)
    assert built["status"] == "none"
    assert built["headline"] == "This interview produced nothing to go on."


def test_a_clean_interview_says_so_plainly():
    clean = session()
    clean["assessments"][1].update(verdict="spontaneous", reasons=[])
    built = report.build(clean, MODEL)          # no brief: no topic can be missed
    assert built["status"] == "clear"
    assert built["headline"] == "Nothing here needs a second look."
    assert built["next_steps"] == []


def test_the_facts_are_measured_never_estimated():
    built = report.build(session(), MODEL)
    facts = built["answers"][1]["facts"]
    assert facts["words"] == 12
    assert facts["seconds"] == pytest.approx(3.6, abs=0.1)     # 11 gaps of 300ms, plus one word
    assert facts["words_per_minute"] == round(12 / facts["seconds"] * 60)


def test_a_single_word_answer_has_no_rate_to_report():
    """One word has no duration between words, so there is no rate. Reporting one
    anyway would be inventing a measurement."""
    one = session(assessments=[{"topic_id": "warmup", "verdict": "not_measured", "quote": "yes",
                                "answer_words": words("yes", 0)}])
    facts = report.build(one, MODEL)["answers"][0]["facts"]
    assert facts["seconds"] is None and facts["words_per_minute"] is None


def test_the_limits_quote_the_model_rather_than_a_slogan():
    """Every number in the limits comes from the fitted model, so refitting it
    cannot leave a stale claim behind in the report."""
    lines = " ".join(report.limits(MODEL))
    assert "never whether the candidate is any good at the job" in lines
    assert "never as a reason to reject" in lines


def test_the_limits_survive_a_model_with_no_provenance():
    bare = {"threshold": -0.2, "signals": []}
    lines = report.limits(bare)
    assert lines and all(isinstance(line, str) for line in lines)


def test_the_report_repeats_the_verdict_and_never_recomputes_it():
    """The interview decided; the report reads. A report that scored answers again
    could contradict the interview it describes."""
    odd = session()
    odd["assessments"][1]["verdict"] = "spontaneous"      # disagrees with its own reasons
    built = report.build(odd, MODEL)
    assert built["answers"][1]["verdict"] == "spontaneous"
    assert built["status"] == "clear"


# -- the chain, made visible --------------------------------------------------------

def test_the_report_shows_what_was_measured_and_what_it_produced():
    """The one thing that makes Probe different happens inside a pipe nobody can
    see. A reader must be able to follow it: the numbers, the decision taken from
    them, the instruction sent, and the sentence the interviewer said next."""
    built = report.build(session(), MODEL, BRIEF)
    measured = built["answers"][1]
    assert [m["label"] for m in measured["measured_signals"]] == [
        "Long words", "Hesitations and restarts", "Clause breaks", "Words between pauses"]
    assert measured["instruction"] == "Ask exactly one short follow-up."
    # The chain closes on the transcript: the question that followed the warm-up is
    # the one the interviewer really asked next.
    assert built["answers"][0]["then_asked"] == "You said the delimiters broke - which file?"


def test_a_ratio_is_shown_as_a_ratio_and_a_rate_as_a_rate():
    measured = {m["name"]: m for m in report.build(session(), MODEL, BRIEF)["answers"][1]["measured_signals"]}
    assert measured["long_word_share/base"]["value"].endswith("\u00d7")
    assert measured["long_word_share/base"]["unit"] == "against their own warm-up"
    assert measured["disfluency_rate"]["value"] == "3.0"
    assert measured["disfluency_rate"]["unit"] == "per 100 words"


def test_the_signals_that_leaned_towards_prepared_are_the_ones_marked():
    """Four numbers with none of them marked leaves a reader to guess which
    mattered, which is the same as showing nothing."""
    marked = [m["label"] for m in report.build(session(), MODEL, BRIEF)["answers"][1]["measured_signals"]
              if m["points_to_reading"]]
    assert marked == ["Long words"]


def test_an_older_session_recovers_the_signals_from_its_own_reasons():
    """Sessions recorded before the signal names were stored still carry the
    sentences they produced, and a sentence names its signal exactly once."""
    old = session()
    old["assessments"][1].pop("pointed", None)
    marked = [m["points_to_reading"] for m in report.build(old, MODEL, BRIEF)["answers"][1]["measured_signals"]]
    assert marked == [True, False, False, False]


def test_the_last_answer_has_no_question_after_it():
    """The interview ended there. Inventing a follow-up would break the one thing
    the chain is for, which is being checkable against the transcript."""
    built = report.build(session(), MODEL, BRIEF)
    assert built["answers"][-1]["then_asked"] == ""


# -- the scale, and being honest about a thin interview -----------------------------

def scored(session_dict, *scores):
    """Give the assessments real scores, so the scale has something to plot."""
    for assessment, value in zip(session_dict["assessments"], scores):
        assessment["score"] = value
    return session_dict


def test_every_measured_answer_lands_on_the_scale():
    """Scores in a list are four decimals nobody reads. On one axis with the line
    drawn, which side an answer fell on is the whole finding."""
    built = report.build(scored(session(), None, 0.9), MODEL, BRIEF)
    scale = built["scale"]
    assert [m["verdict"] for m in scale["marks"]] == ["prepared"]
    assert scale["threshold"] == MODEL["threshold"]
    assert 0 < scale["marks"][0]["at"] < 100
    assert 0 < scale["threshold_at"] < 100


def test_a_dot_is_never_pinned_to_the_edge():
    """One answer and the threshold would otherwise sit at 0% and 100%, where a
    reader cannot see how far apart they are."""
    scale = report.build(scored(session(), None, -0.19), MODEL, BRIEF)["scale"]
    assert 5 < scale["marks"][0]["at"] < 95


def test_an_answer_the_wrong_side_of_the_line_is_on_the_wrong_side():
    both = session()
    both["assessments"].append(dict(both["assessments"][1], topic_id="judgement",
                                    verdict="spontaneous", reasons=[], pointed=[]))
    scale = report.build(scored(both, None, 0.9, -1.4), MODEL, BRIEF)["scale"]
    prepared = next(m for m in scale["marks"] if m["verdict"] == "prepared")
    spontaneous = next(m for m in scale["marks"] if m["verdict"] == "spontaneous")
    assert spontaneous["at"] < scale["threshold_at"] < prepared["at"]


def test_no_scale_when_nothing_was_measured():
    """An empty axis would say a measurement happened. None did."""
    empty = session(assessments=[{"topic_id": "warmup", "verdict": "baseline", "quote": "um",
                                  "answer_words": []}])
    assert report.build(empty, MODEL, BRIEF)["scale"] is None


def test_a_thin_interview_does_not_read_as_a_clean_one():
    """Two comparable answers out of seven with nothing flagged is not a clean
    interview, it is one that measured almost nothing, and a recruiter must not
    read the first when the truth is the second."""
    thin = session()
    thin["assessments"][1].update(verdict="spontaneous", reasons=[], pointed=[])
    # Both topics answered, so nothing is left to dig into - and yet four of the
    # six answers told us nothing at all.
    thin["assessments"].append(dict(thin["assessments"][1], topic_id="judgement"))
    for _ in range(4):
        thin["assessments"].append({"topic_id": "project", "verdict": "not_measured",
                                    "question": "q", "quote": "hm", "answer_words": []})
    built = report.build(thin, MODEL, BRIEF)
    assert built["thin"] is True
    assert built["status"] != "clear"
    assert built["next_steps"] == []
    assert "2" in built["headline"] and "7" in built["headline"]


def test_an_interview_that_measured_most_of_itself_is_clean():
    fine = session()
    fine["assessments"][1].update(verdict="spontaneous", reasons=[], pointed=[])
    fine["assessments"].append(dict(fine["assessments"][1], topic_id="judgement"))
    built = report.build(fine, MODEL, BRIEF)
    assert built["thin"] is False
    assert built["status"] == "clear"
