"""The interview brief: topics, languages, and the rules the interviewer is given."""
import copy as copy_module
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import interview  # noqa: E402

GOOD = {
    "role": "Software engineer",
    "warmup": "Walk me through your day yesterday.",
    "topics": [
        {"id": "project", "goal": "A project they owned: what broke and what they chose"},
        {"id": "depth", "goal": "How well they understand what they use every day"},
    ],
    "max_followups": 2,
    "languages": ["en", "fr"],
}


def broken(change):
    data = copy_module.deepcopy(GOOD)
    change(data)
    return data


def test_the_shipped_brief_is_valid():
    brief = interview.load(ROOT / "interview.json")
    assert brief["topics"] and brief["languages"][0]["voice"]


def test_a_valid_brief_comes_back_cleaned_with_voices():
    brief = interview.validate(broken(lambda d: d["topics"][0].update(goal="  A   project  they owned ")))
    assert brief["topics"][0]["goal"] == "A project they owned"
    assert brief["languages"] == [{"code": "en", "name": "English", "voice": "alba"},
                                  {"code": "fr", "name": "Français", "voice": "estelle"}]


@pytest.mark.parametrize("change, fragment", [
    (lambda d: d.pop("role"), "role must say"),
    (lambda d: d.update(warmup=""), "warmup"),
    (lambda d: d.update(warmup="x" * 401), "longer than 400"),
    (lambda d: d.update(topics=[]), "between 1 and 6"),
    (lambda d: d["topics"][1].update(id="project"), "share an id"),
    (lambda d: d["topics"][0].pop("goal"), "topic 1 needs a goal"),
    (lambda d: d["topics"][0].update(question="read this"), "unknown fields: question"),
    (lambda d: d.update(max_followups=0), "between 1 and 4"),
    (lambda d: d.update(max_followups=True), "between 1 and 4"),
    (lambda d: d.update(languages=["ar"]), "no voice speaks ar"),
    (lambda d: d.update(languages=[]), "non-empty"),
    (lambda d: d.update(extra=1), "unknown fields: extra"),
])
def test_each_mistake_is_named(change, fragment):
    with pytest.raises(interview.InterviewError, match=fragment):
        interview.validate(broken(change))


def test_a_file_that_is_not_json_names_the_file(tmp_path):
    path = tmp_path / "interview.json"
    path.write_text("{oops", encoding="utf-8")
    with pytest.raises(interview.InterviewError, match="interview.json is not valid JSON"):
        interview.load(path)


# -- what the interviewer is told ------------------------------------------------------

def test_the_prompt_carries_the_topics_and_the_language():
    prompt = interview.system_prompt(interview.validate(GOOD), "fr")
    assert "Speak Français" in prompt
    assert "project: A project they owned" in prompt
    assert GOOD["warmup"] in prompt


def test_the_prompt_forbids_reading_prepared_questions():
    """The whole point: a candidate can rehearse a question they can predict."""
    prompt = interview.system_prompt(interview.validate(GOOD), "en").lower()
    assert "the only question you may ask without having heard the candidate" in prompt
    assert "repeat a phrase of theirs word for word inside your question" in prompt
    assert "could the candidate have answered it if they had been handed it a week ago?" in prompt
    assert "a topic is a direction to steer in, never a question to read out" in prompt


def test_the_prompt_keeps_the_assessment_from_the_candidate():
    prompt = interview.system_prompt(interview.validate(GOOD), "en")
    assert "Never mention the tool" in prompt
    assert "sounded prepared or read" in prompt


def test_an_unknown_language_falls_back_to_the_first_offered():
    brief = interview.validate(GOOD)
    assert interview.voice_for("zz", brief) == "alba"
    assert "Speak English" in interview.system_prompt(brief, "zz")
