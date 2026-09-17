"""One candidate, one link, and the link works once.

Working once is not a technicality here, it is the product: a candidate who could
take the interview twice would have heard the questions before the second attempt,
and answers prepared from heard questions are the exact failure of the video
questionnaire Probe replaces.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import invites  # noqa: E402


@pytest.fixture
def box(tmp_path):
    return tmp_path / "invites"


def test_an_invitation_starts_out_waiting(box):
    invite = invites.create(box, "Amina", "Engineer")
    assert invites.status(invite) == "waiting"
    assert invite["label"] == "Amina"
    assert invite["session_id"] is None


def test_the_id_is_generated_here_and_never_taken_from_a_request(box):
    """The id is what makes the link private, so it is not something a caller can
    choose. Two invitations made back to back must not collide either."""
    first = invites.create(box, "one")
    second = invites.create(box, "two")
    assert invites.INVITE_ID.match(first["id"])
    assert first["id"] != second["id"]


def test_opening_the_link_does_not_spend_it(box):
    """A candidate who opens the link, reads the page and closes it again has not
    taken their interview, and must not lose it."""
    invite = invites.create(box, "Amina")
    invites.read(box, invite["id"])
    assert invites.status(invites.read(box, invite["id"])) == "waiting"


def test_starting_the_interview_marks_it_started_but_leaves_it_usable(box):
    invite = invites.create(box, "Amina")
    invites.claim(box, invite["id"])
    assert invites.status(invites.read(box, invite["id"])) == "started"
    invites.claim(box, invite["id"])          # a dropped connection, and they retry
    assert invites.status(invites.read(box, invite["id"])) == "started"


def test_a_finished_interview_closes_the_link_for_good(box):
    invite = invites.create(box, "Amina")
    invites.claim(box, invite["id"])
    invites.spend(box, invite["id"], "20260917T090000Z-abcdabcd")
    with pytest.raises(invites.InviteError) as refused:
        invites.claim(box, invite["id"])
    assert refused.value.status == 409
    assert "already been taken" in str(refused.value)


def test_the_finished_interview_stays_attached_to_its_invitation(box):
    invite = invites.create(box, "Amina")
    invites.spend(box, invite["id"], "20260917T090000Z-abcdabcd")
    stored = invites.read(box, invite["id"])
    assert stored["session_id"] == "20260917T090000Z-abcdabcd"
    assert invites.status(stored) == "done"


def test_a_second_interview_never_overwrites_the_first(box):
    """If a session were ever saved twice against one invitation, the report the
    recruiter opens must still be the interview that was actually taken."""
    invite = invites.create(box, "Amina")
    invites.spend(box, invite["id"], "first")
    invites.spend(box, invite["id"], "second")
    assert invites.read(box, invite["id"])["session_id"] == "first"


@pytest.mark.parametrize("bad", ["", "../server", "ZZZ", "a" * 31, "a" * 33, None])
def test_an_id_shaped_like_a_path_never_reaches_the_disk(box, bad):
    """The id becomes a file name, so anything that is not an id is refused before
    it is used as one."""
    invites.create(box, "Amina")
    with pytest.raises(invites.InviteError):
        invites.read(box, bad)


def test_a_label_is_trimmed_and_capped(box):
    invite = invites.create(box, "  Amina   Diallo\n\n")
    assert invite["label"] == "Amina Diallo"
    assert len(invites.create(box, "x" * 500)["label"]) == invites.MAX_LABEL


def test_a_label_that_is_not_text_is_refused(box):
    with pytest.raises(invites.InviteError) as refused:
        invites.create(box, {"name": "Amina"})
    assert refused.value.status == 422


def test_the_list_is_newest_first_and_carries_the_status(box):
    older = invites.create(box, "older")
    newer = invites.create(box, "newer")
    invites.spend(box, older["id"], "session-1")
    listed = invites.listing(box)
    assert {i["label"] for i in listed} == {"older", "newer"}
    assert {i["label"]: i["status"] for i in listed} == {"older": "done", "newer": "waiting"}


def test_a_half_written_file_is_skipped_rather_than_breaking_the_list(box):
    invites.create(box, "Amina")
    (box / ("f" * 32 + ".json")).write_text("{not json", encoding="utf-8")
    assert len(invites.listing(box)) == 1


def test_an_empty_or_missing_folder_is_an_empty_list(tmp_path):
    assert invites.listing(tmp_path / "nothing") == []
