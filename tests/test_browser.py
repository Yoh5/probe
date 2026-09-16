"""The interview, conducted end to end in a real browser against a fake AssemblyAI.

Everything else in this suite tests Python. The part of Probe that decides when the
interviewer speaks, when it waits and when it gives up lives in `static/app.js`, and
it is the part that failed in front of a candidate: a tool result held back until an
event that could no longer arrive, and an interview that went silent for good.

`tests/browser/harness.html` loads the real page and the real app.js on top of stubs,
runs a whole conversation through them with time sped up, and puts the outcome in the
document title. This module finds a browser, serves the folder, and reads that title.

Skipped, never failed, when no Chromium-based browser is installed: a machine without
one has nothing to say about the interview.
"""
from __future__ import annotations

import http.server
import os
import re
import shutil
import socket
import subprocess
import tempfile
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = "/tests/browser/harness.html"

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def find_browser() -> str | None:
    for name in ("google-chrome", "chromium", "chromium-browser", "msedge"):
        found = shutil.which(name)
        if found:
            return found
    for path in BROWSERS:
        if os.path.exists(path):
            return path
    return None


def serve(directory: Path):
    """A plain file server on a free port. No API key, no interview, just the files."""
    handler = type("Quiet", (http.server.SimpleHTTPRequestHandler,), {
        "log_message": lambda *args, **kwargs: None,
        "directory_": str(directory),
        "__init__": lambda self, *a, **kw: http.server.SimpleHTTPRequestHandler.__init__(
            self, *a, directory=str(directory), **kw),
    })
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, port


@pytest.fixture(scope="module")
def outcome() -> str:
    browser = find_browser()
    if not browser:
        pytest.skip("no Chromium-based browser on this machine")
    server, port = serve(ROOT)
    try:
        with tempfile.TemporaryDirectory() as profile:
            done = subprocess.run(
                [browser, "--headless=new", "--disable-gpu", "--no-first-run",
                 f"--user-data-dir={profile}", "--virtual-time-budget=60000", "--dump-dom",
                 f"http://127.0.0.1:{port}{HARNESS}"],
                capture_output=True, text=True, timeout=180, encoding="utf-8", errors="replace")
    finally:
        server.shutdown()
    return done.stdout


def report(dom: str) -> str:
    found = re.search(r'<pre id="report">(.*?)</pre>', dom, re.S)
    return found.group(1) if found else dom[-2000:]


def test_the_whole_interview_runs_in_a_browser(outcome):
    title = re.search(r"<title>(.*?)</title>", outcome, re.S)
    assert title, f"the harness never finished:\n{report(outcome)}"
    assert title.group(1).startswith("PASS"), f"{title.group(1)}\n{report(outcome)}"
