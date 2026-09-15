"""The routes: the two tokens, the verdict, and saved sessions."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import server  # noqa: E402
from test_assess import CHATTY, WRITTEN, aai_words  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setenv("ASSEMBLYAI_API_KEY", "long-lived-secret")
    return TestClient(server.app)


@pytest.fixture
def minted(monkeypatch):
    """Both token calls answered, with the request recorded."""
    seen = []

    async def fake(client, url, headers, params):
        seen.append({"url": url, "headers": headers, "params": params})
        return f"token-for-{'agent' if 'agents' in url else 'streaming'}"

    monkeypatch.setattr(server, "_token", fake)
    return seen


# -- tokens ---------------------------------------------------------------------------

def test_the_browser_gets_one_token_per_connection(client, minted):
    body = client.post("/api/tokens").json()
    assert body["agent"] == "token-for-agent" and body["streaming"] == "token-for-streaming"
    assert body["ttl"] == server.TOKEN_TTL_SECONDS


def test_the_long_lived_key_never_reaches_the_browser(client, minted):
    text = client.post("/api/tokens").text
    assert "long-lived-secret" not in text
    # The agent endpoint wants a Bearer prefix, the streaming one wants the bare key.
    agent, streaming = minted
    assert agent["headers"]["Authorization"] == "Bearer long-lived-secret"
    assert streaming["headers"]["Authorization"] == "long-lived-secret"


def test_a_missing_key_is_named(client, monkeypatch):
    monkeypatch.delenv("ASSEMBLYAI_API_KEY", raising=False)
    r = client.post("/api/tokens")
    assert r.status_code == 503 and "ASSEMBLYAI_API_KEY" in r.json()["detail"]


def test_certificate_verification_is_never_disabled():
    assert server.tls_context() is not False


# -- the verdict ---------------------------------------------------------------------------

def test_a_written_answer_comes_back_with_an_instruction(client):
    r = client.post("/api/assess", json={
        "answer_words": aai_words(WRITTEN, pause_every=9, pause_ms=400),
        "baseline_words": aai_words(CHATTY)})
    assert r.status_code == 200
    body = r.json()
    assert body["verdict"] == "prepared" and body["sounds_prepared"] is True
    assert "follow-up" in body["instruction"]


def test_the_warm_up_itself_is_not_judged(client):
    body = client.post("/api/assess", json={"answer_words": aai_words(CHATTY), "baseline_words": None}).json()
    assert body["verdict"] == "baseline"


@pytest.mark.parametrize("payload, status", [
    ({}, 422),
    ({"answer_words": "no"}, 422),
    ({"answer_words": [{"text": "hi"}]}, 422),
    ({"answer_words": [], "baseline_words": "no"}, 422),
])
def test_a_malformed_assessment_request_is_refused_with_a_reason(client, payload, status):
    r = client.post("/api/assess", json=payload)
    assert r.status_code == status and r.json()["detail"]


# -- sessions ------------------------------------------------------------------------------------

def test_a_session_round_trips(client):
    saved = client.post("/api/sessions", json={"turns": [{"role": "agent", "text": "Hello"}]})
    assert saved.status_code == 200
    session_id = saved.json()["id"]
    assert server.SESSION_ID.match(session_id)
    assert client.get(f"/api/sessions/{session_id}").json()["turns"][0]["text"] == "Hello"


def test_the_id_is_never_taken_from_the_request(client):
    body = client.post("/api/sessions", json={"id": "../escape", "turns": []}).json()
    assert server.SESSION_ID.match(body["id"])


@pytest.mark.parametrize("bad", ["../secrets", "stray", "20260916T120000Z-zz"])
def test_loading_refuses_anything_but_a_generated_id(client, bad):
    assert client.get(f"/api/sessions/{bad}").status_code == 404


def test_a_session_without_turns_is_refused(client):
    assert client.post("/api/sessions", json={"turns": "none"}).status_code == 422


def test_an_oversized_session_is_refused(client, monkeypatch):
    monkeypatch.setattr(server, "MAX_SESSION_BYTES", 50)
    assert client.post("/api/sessions", json={"turns": [{"text": "x" * 200}]}).status_code == 413


def test_the_questions_are_served_for_the_page(client):
    body = client.get("/api/questions").json()
    assert body["questions"][0]["kind"] == "baseline"
