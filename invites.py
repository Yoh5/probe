"""Probe - one candidate, one link, and the link works once.

This is the whole of what replaces the video questionnaire's plumbing. A recruiter
makes an invite per candidate and sends the link. The candidate opens it and talks.
The invite is then spent, and the interview it produced is attached to it.

Working once is not a technicality, it is the product. A candidate who could take
the interview twice would have heard the questions before the second attempt, and
prepared answers are the exact thing the video questionnaire fails at. So a spent
invite says so plainly rather than quietly starting a second interview.

Invites are files under `invites/`, one JSON object each, named by their own id.
The id is the secret: it is what makes the link private, so it is generated here
and never taken from a request.
"""
from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path

# 32 hex characters: enough that guessing one is not a strategy, short enough to
# paste into an email without wrapping.
INVITE_ID = re.compile(r"^[0-9a-f]{32}$")
MAX_LABEL = 120


class InviteError(ValueError):
    """The invite cannot be used, with a sentence saying why."""

    def __init__(self, message: str, status: int = 404):
        super().__init__(message)
        self.status = status


def _now() -> str:
    return f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ}"


def _path(directory: Path, invite_id: str) -> Path:
    # The id reaches a file path, so its shape is checked before it is used as one.
    if not INVITE_ID.match(invite_id or ""):
        raise InviteError("no such invitation")
    return directory / f"{invite_id}.json"


def create(directory: Path, label: str = "", role: str = "") -> dict:
    """A fresh invitation. The label is the recruiter's own note of who it is for."""
    if not isinstance(label, str):
        raise InviteError("the label must be text", status=422)
    label = " ".join(label.split())[:MAX_LABEL]
    invite = {
        "id": secrets.token_hex(16),
        "label": label,
        "role": role,
        "created_at": _now(),
        "opened_at": None,
        "used_at": None,
        "session_id": None,
    }
    directory.mkdir(exist_ok=True)
    _path(directory, invite["id"]).write_text(json.dumps(invite, indent=2), encoding="utf-8")
    return invite


def read(directory: Path, invite_id: str) -> dict:
    path = _path(directory, invite_id)
    if not path.is_file():
        raise InviteError("no such invitation")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        raise InviteError("that invitation could not be read") from None


def claim(directory: Path, invite_id: str) -> dict:
    """Mark an invitation as opened, or refuse it because it has been used.

    Called when the interview is about to start rather than when the page loads: a
    candidate who opens the link, reads it and closes it again has not used their
    interview, and should not lose it.
    """
    invite = read(directory, invite_id)
    if invite.get("used_at"):
        raise InviteError("this interview has already been taken", status=409)
    invite["opened_at"] = invite.get("opened_at") or _now()
    _path(directory, invite_id).write_text(json.dumps(invite, indent=2), encoding="utf-8")
    return invite


def spend(directory: Path, invite_id: str, session_id: str) -> dict:
    """Attach the finished interview to its invitation and close it."""
    invite = read(directory, invite_id)
    invite["used_at"] = invite.get("used_at") or _now()
    invite["session_id"] = invite.get("session_id") or session_id
    _path(directory, invite_id).write_text(json.dumps(invite, indent=2), encoding="utf-8")
    return invite


def status(invite: dict) -> str:
    if invite.get("used_at"):
        return "done"
    if invite.get("opened_at"):
        return "started"
    return "waiting"


def listing(directory: Path) -> list[dict]:
    """Every invitation, newest first, with its status."""
    if not directory.is_dir():
        return []
    found = []
    for path in sorted(directory.glob("*.json"), reverse=True):
        if not INVITE_ID.match(path.stem):
            continue
        try:
            invite = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue    # a half-written file is skipped, never fatal to the list
        found.append({**invite, "status": status(invite)})
    found.sort(key=lambda i: i.get("created_at", ""), reverse=True)
    return found
