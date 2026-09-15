"""Probe - the server.

It does three things, and never touches the audio:

1. serves the interview and report pages;
2. mints the two short-lived AssemblyAI tokens the browser needs - one for the
   Voice Agent API, one for Realtime speech-to-text - so the API key stays here;
3. answers `assess_answer`: the browser sends the words of the answer that just
   ended, this computes the verdict (assess.py) and returns the instruction the
   agent follows.

The audio goes straight from the browser to AssemblyAI, in two parallel
connections fed by the same microphone: the agent connection carries the
conversation, the streaming connection carries the word timings the verdict
rests on.

Run: uvicorn server:app --port 8000
"""
from __future__ import annotations

import json
import os
import re
import secrets
import ssl
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import assess
import detector
from questions import load_questions

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")

SESSIONS_DIR = ROOT / "sessions"
MAX_SESSION_BYTES = 4_000_000
SESSION_ID = re.compile(r"^\d{8}T\d{6}Z-[0-9a-f]{8}$")

AGENT_TOKEN_URL = "https://agents.assemblyai.com/v1/token"
STREAMING_TOKEN_URL = "https://streaming.assemblyai.com/v3/token"
# Long enough to open both sockets, short enough that a token lifted from the
# page is worthless. Tokens are single-use: one interview, one fetch.
TOKEN_TTL_SECONDS = 120
MAX_SESSION_SECONDS = 1800

QUESTIONS = load_questions(Path(os.environ.get("PROBE_QUESTIONS", ROOT / "questions.json")))
MODEL = detector.load()


def tls_context():
    """Validate certificates against the operating system's trust store.

    Verification stays fully on; only the list of trusted roots changes. An
    antivirus that scans HTTPS re-signs every site with a root installed in the
    OS store, which certifi does not know about.
    """
    try:
        import truststore
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        return True


app = FastAPI(title="Probe")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/api/questions")
def questions() -> dict:
    return {"questions": QUESTIONS}


async def _token(client: httpx.AsyncClient, url: str, headers: dict, params: dict) -> str:
    try:
        response = await client.get(url, headers=headers, params=params)
    except httpx.HTTPError as error:
        raise HTTPException(502, f"AssemblyAI unreachable: {type(error).__name__}")
    if response.status_code >= 400:
        # The status is enough to tell a bad key (401) from an outage; the body
        # can echo request details back.
        raise HTTPException(502, f"AssemblyAI refused the token request ({response.status_code})")
    token = response.json().get("token")
    if not token:
        raise HTTPException(502, "AssemblyAI answered without a token")
    return token


@app.post("/api/tokens")
async def tokens() -> dict:
    """One token for the agent connection, one for the transcription connection."""
    key = os.environ.get("ASSEMBLYAI_API_KEY", "")
    if not key:
        raise HTTPException(503, "ASSEMBLYAI_API_KEY is not set on the server")
    async with httpx.AsyncClient(timeout=15, verify=tls_context()) as client:
        agent = await _token(client, AGENT_TOKEN_URL, {"Authorization": f"Bearer {key}"},
                             {"expires_in_seconds": TOKEN_TTL_SECONDS,
                              "max_session_duration_seconds": MAX_SESSION_SECONDS})
        streaming = await _token(client, STREAMING_TOKEN_URL, {"Authorization": key},
                                 {"expires_in_seconds": TOKEN_TTL_SECONDS})
    return {"agent": agent, "streaming": streaming, "ttl": TOKEN_TTL_SECONDS}


@app.post("/api/assess")
async def assess_answer(request: Request) -> dict:
    """The verdict for the answer that just ended, as the agent's tool result.

    The browser sends the AssemblyAI words of the answer and of the warm-up. The
    decision is made here, in tested code, never by the model conducting the
    interview.
    """
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(400, "body must be an object")
    words = body.get("answer_words")
    baseline = body.get("baseline_words")
    if not isinstance(words, list) or not all(isinstance(w, dict) for w in words):
        raise HTTPException(422, "answer_words must be a list of words")
    if baseline is not None and not isinstance(baseline, list):
        raise HTTPException(422, "baseline_words must be a list of words or null")
    try:
        answer = assess.from_assemblyai(words)
        base = assess.from_assemblyai(baseline) if baseline else None
    except (KeyError, TypeError, ValueError):
        raise HTTPException(422, "each word needs text, start and end")
    return assess.assess(answer, base, MODEL)


@app.post("/api/sessions")
async def save_session(request: Request) -> dict:
    raw = await request.body()
    if len(raw) > MAX_SESSION_BYTES:
        raise HTTPException(413, "session too large")
    try:
        session = json.loads(raw)
    except ValueError:
        raise HTTPException(400, "session is not valid JSON")
    if not isinstance(session, dict) or not isinstance(session.get("turns"), list):
        raise HTTPException(422, "a session needs a list of turns")

    # The id is built here, never taken from the request: it becomes a file name.
    session_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{secrets.token_hex(4)}"
    SESSIONS_DIR.mkdir(exist_ok=True)
    (SESSIONS_DIR / f"{session_id}.json").write_text(json.dumps(session, indent=2), encoding="utf-8")
    return {"id": session_id}


def _read_session(session_id: str) -> dict:
    # The id reaches a file path, so its shape is checked before anything else.
    if not SESSION_ID.match(session_id):
        raise HTTPException(404, "no such session")
    path = SESSIONS_DIR / f"{session_id}.json"
    if not path.is_file():
        raise HTTPException(404, "no such session")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/sessions/{session_id}")
def load_session(session_id: str) -> dict:
    return _read_session(session_id)
