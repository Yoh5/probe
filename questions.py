"""Unscripted - the questions an interview asks, read from questions.json.

A recruiter edits that file, not the code. What makes a list of questions
usable is checked here, when the server starts, so a mistake stops the server
with a sentence that names it - instead of an interview that runs and then
produces a report with nothing to compare against.

The rules, and why:
- The first question is the baseline, and there is exactly one. Every other
  answer is divided by how the candidate speaks there; a second baseline would
  make "the" baseline ambiguous, and one asked later would be answered by a
  candidate already warmed up by the others.
- The baseline must be something nobody can prepare for (yesterday, a recent
  trip). That cannot be checked by code, only written down: see the README.
- Between 2 and 12 questions: at least one answer to compare, and few enough
  that a candidate is still speaking naturally at the end.
- Kinds are the ones the report knows how to name.
- Unknown fields are refused. "txt" instead of "text" should fail loudly, not
  ask an empty question.
"""
from __future__ import annotations

import json
from pathlib import Path

KINDS = ("baseline", "experience", "technical")
MIN_QUESTIONS = 2
MAX_QUESTIONS = 12
MAX_TEXT = 400


class QuestionsError(ValueError):
    pass


def validate_questions(data: object) -> list[dict]:
    """The questions, cleaned, or QuestionsError with the first problem found."""
    if not isinstance(data, dict) or set(data) != {"questions"}:
        raise QuestionsError('the file must be an object with a single "questions" list')
    questions = data["questions"]
    if not isinstance(questions, list):
        raise QuestionsError('"questions" must be a list')
    if not MIN_QUESTIONS <= len(questions) <= MAX_QUESTIONS:
        raise QuestionsError(f"there must be between {MIN_QUESTIONS} and {MAX_QUESTIONS} questions, not {len(questions)}")

    cleaned = []
    for number, q in enumerate(questions, start=1):
        where = f"question {number}"
        if not isinstance(q, dict):
            raise QuestionsError(f"{where} must be an object")
        unknown = set(q) - {"kind", "text"}
        if unknown:
            raise QuestionsError(f"{where} has unknown fields: {', '.join(sorted(unknown))}")
        if q.get("kind") not in KINDS:
            raise QuestionsError(f"{where} kind must be one of {', '.join(KINDS)}")
        text = q.get("text")
        if not isinstance(text, str) or not text.strip():
            raise QuestionsError(f"{where} needs a text")
        if len(text) > MAX_TEXT:
            raise QuestionsError(f"{where} is longer than {MAX_TEXT} characters; it is read aloud")
        cleaned.append({"kind": q["kind"], "text": " ".join(text.split())})

    if cleaned[0]["kind"] != "baseline":
        raise QuestionsError("question 1 must be the baseline: every other answer is compared to it")
    if sum(q["kind"] == "baseline" for q in cleaned) != 1:
        raise QuestionsError("there must be exactly one baseline question")
    return cleaned


def load_questions(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise QuestionsError(f"{path.name} could not be read: {error.strerror}") from None
    except ValueError as error:
        raise QuestionsError(f"{path.name} is not valid JSON: {error}") from None
    try:
        return validate_questions(data)
    except QuestionsError as error:
        raise QuestionsError(f"{path.name}: {error}") from None
