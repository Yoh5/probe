"""Run a whole interview without a microphone, against the real APIs.

This is the browser's job, done from Python: two AssemblyAI connections fed by
the same synthesized audio, the agent's tool calls answered by the running
server, and the follow-up questions printed as they come back.

It answers the question the page cannot answer on its own: does the agent
actually probe the answer that was read, and leave the spontaneous one alone?

The two answers are spoken by the Windows voice, so the "spontaneous" one is a
written imitation of speech, not real speech. It exercises the loop; it does not
calibrate anything.

Start the server first (uvicorn server:app --port 8000), then:
    python scripts/dryrun.py
"""
from __future__ import annotations

import asyncio
import base64
import os
import json
import ssl
import subprocess
import time
import sys
import wave
from pathlib import Path

import httpx
import websockets

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
RATE = 24000
SERVER = "http://127.0.0.1:8000"
LANGUAGE = os.environ.get("PROBE_LANGUAGE", "en")
CLIPS = ROOT / "scripts" / "clips"

# The warm-up: speech as it comes out, hesitations and all.
WARMUP = ("Um, yesterday, I got up pretty late, like, nine or so, and then I, I made coffee "
          "and answered a few emails. Then I went to the office, and, uh, we had this meeting "
          "about the migration that ran way too long. After that I just, I fixed a bug that had "
          "been annoying me since Friday, and then I went home and watched a film.")

# The answer a candidate would read from a screen: finished sentences, written words.
READ = ("I designed and delivered an intelligent data cleaning platform as the sole developer. "
        "The architecture combined a profiling engine that detects missing values and infers column "
        "types, a recommendation engine that suggests cleaning strategies, and a generator that "
        "produces validated Python scripts. The most demanding aspect was handling inconsistent "
        "delimiters and malformed encodings, which taught me defensive programming and rigorous "
        "edge case analysis.")

# The answer to the follow-up: spoken, not read, which is the point. The tool
# should leave this one alone.
PROBED = ("Honestly, the first thing that broke was the encoding sniffing. I, uh, I assumed UTF-8 everywhere, "
          "and then a client sent a file in Latin-1 and the whole run just, it died on the first row. "
          "So I added a fallback that tries a few encodings and, and asks the user when it is not sure.")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def tls():
    try:
        import truststore
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        return ssl.create_default_context()


def clip(name: str, text: str) -> bytes:
    CLIPS.mkdir(exist_ok=True)
    path = CLIPS / f"{name}.wav"
    if not path.exists():
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Add-Type -AssemblyName System.Speech;"
                        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
                        "$s.SelectVoice('Microsoft Zira Desktop'); $s.Rate = 0;"
                        f"$f = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo({RATE}, 16, 1);"
                        f"$s.SetOutputToWaveFile('{path}', $f); $s.Speak('{text}'); $s.Dispose()"], check=True)
    with wave.open(str(path)) as w:
        if w.getframerate() != RATE:
            raise SystemExit(f"{path} is {w.getframerate()} Hz, expected {RATE}")
        return w.readframes(w.getnframes())


class DryRun:
    """The page's state machine, with the microphone replaced by two clips."""

    def __init__(self, answers: list[bytes]):
        self.answers = answers
        self.samples_sent = 0
        self.words: list[dict] = []
        self.answer_start_ms = 0.0
        self.baseline: list[dict] | None = None
        self.pending: list[dict] = []
        self.last_event = None
        self.spoken = 0
        self.speaking: asyncio.Task | None = None
        self.done = asyncio.Event()

    @property
    def clock_ms(self) -> float:
        return self.samples_sent / RATE * 1000

    async def run(self) -> None:
        async with httpx.AsyncClient(timeout=30) as http:
            tokens = (await http.post(f"{SERVER}/api/session", json={"language": LANGUAGE})).json()
        if "agent_id" not in tokens:
            raise SystemExit(f"the server refused a session: {tokens}")
        agent_url = f"wss://agents.assemblyai.com/v1/ws?token={tokens['agent']}"
        stt_url = (f"wss://streaming.assemblyai.com/v3/ws?token={tokens['streaming']}"
                   f"&speech_model=universal-3-5-pro&sample_rate={RATE}&encoding=pcm_s16le&format_turns=true")
        # The AssemblyAI servers ping; our own keepalive would fight them while
        # we are streaming audio out of a background task.
        async with websockets.connect(agent_url, ssl=tls(), ping_interval=None) as agent, \
                   websockets.connect(stt_url, ssl=tls(), ping_interval=None) as stt:
            self.agent, self.stt = agent, stt
            # The interviewer lives at AssemblyAI: its prompt, voice and tools are
            # stored server-side, exactly as the browser uses it.
            await agent.send(json.dumps({"type": "session.update",
                                         "session": {"agent_id": tokens["agent_id"]}}))
            await agent.send(json.dumps({"type": "reply.create",
                                         "instructions": "Open the interview now: greet in one short "
                                                         "sentence, then ask the warm-up question."}))
            await asyncio.wait_for(asyncio.gather(self.read_agent(), self.read_stt()), 420)

    async def read_stt(self) -> None:
        async for raw in self.stt:
            message = json.loads(raw)
            kind = message.get("type")
            if kind == "Turn" and message.get("end_of_turn"):
                self.words.extend(message.get("words", []))
            elif kind in ("Begin", "Termination", "Error"):
                # The Error message carries the reason the session is closing;
                # without it a close code says nothing.
                print(f"  [stt {kind}] {json.dumps({k: v for k, v in message.items() if k != 'type'})[:200]}")
            if self.done.is_set():
                return

    async def read_agent(self) -> None:
        async for raw in self.agent:
            message = json.loads(raw)
            kind = message.get("type")
            if kind == "reply.audio":
                continue
            if kind == "transcript.agent":
                print(f"\ninterviewer: {message.get('text')}")
            elif kind == "transcript.user":
                print(f"candidate  : {message.get('text')}")
            elif kind == "session.error":
                print("session error:", message)
                return
            if kind not in ("transcript.agent.delta", "transcript.user.delta", "reply.audio"):
                print(f"  . {kind}")
            if kind in ("reply.started", "input.speech.started"):
                self.last_event = kind
            if kind == "tool.call":
                await self.tool(message)
            if kind == "reply.done":
                self.last_event = kind
                self.answer_start_ms = self.clock_ms
                await self.flush()
                if self.spoken < len(self.answers) and (self.speaking is None or self.speaking.done()):
                    # In the background: this loop must keep reading, or the
                    # connection's own keepalive times out while we are talking.
                    # One answer at a time: two overlapping streams would send
                    # audio faster than real time and the session would close.
                    self.speaking = asyncio.create_task(self.answer(self.answers[self.spoken]))
                    self.spoken += 1
            if self.done.is_set():
                return

    async def answer(self, audio: bytes) -> None:
        # Let the agent finish speaking first. A real candidate does not talk
        # over the question; barge-in would cut it off mid-sentence.
        await asyncio.sleep(3)
        await self.speak(audio)

    async def speak(self, audio: bytes) -> None:
        """Stream a clip to both connections, paced just under real time.

        AssemblyAI closes a streaming session that receives audio faster than it
        is spoken (error 3007), and sleeping per chunk drifts fast enough to
        trip it. Each chunk is therefore released against the clock, with a
        small margin.
        """
        step = RATE // 20 * 2                      # 50 ms of 16-bit samples
        silence = bytes(step)
        chunks = [audio[i:i + step] for i in range(0, len(audio), step)]
        # Every chunk must carry between 50 and 1000 ms of audio: a short last
        # chunk closes the streaming session (error 3007).
        chunks[-1] = chunks[-1].ljust(step, b"\0")
        chunks += [silence] * 50                   # 2.5 s, so both sides see the turn end
        started = time.monotonic()
        for index, chunk in enumerate(chunks):
            await self.agent.send(json.dumps({"type": "input.audio", "audio": base64.b64encode(chunk).decode()}))
            await self.stt.send(chunk)
            self.samples_sent += len(chunk) // 2
            due = started + (index + 1) * 0.052
            await asyncio.sleep(max(0, due - time.monotonic()))

    async def tool(self, call: dict) -> None:
        if call["name"] == "end_interview":
            self.pending.append({"call_id": call["call_id"], "result": {"ok": True}})
            await self.flush()
            self.done.set()
            return
        topic = str(call.get("arguments", {}).get("topic_id", "warmup"))
        warmup = self.baseline is None
        answer = [w for w in self.words if w["start"] >= self.answer_start_ms]
        async with httpx.AsyncClient(timeout=20) as http:
            verdict = (await http.post(f"{SERVER}/api/assess", json={
                "answer_words": answer,
                "baseline_words": None if warmup else self.baseline,
            })).json()
        if warmup and answer:
            self.baseline = answer
        print(f"  [assess {topic}] {verdict.get('verdict')} "
              f"score={verdict.get('score')} words={verdict.get('words')} reasons={verdict.get('reasons')}")
        self.pending.append({"call_id": call["call_id"],
                             "result": {"instruction": verdict.get("instruction"), "verdict": verdict.get("verdict")}})
        await self.flush()

    async def flush(self) -> None:
        if self.last_event != "reply.done" or not self.pending:
            return
        for pending in self.pending:
            await self.agent.send(json.dumps({"type": "tool.result", "call_id": pending["call_id"],
                                              "result": json.dumps(pending["result"])}))
        self.pending.clear()


async def main() -> None:
    answers = [clip("warmup", WARMUP), clip("read", READ), clip("probe", PROBED)]
    try:
        await DryRun(answers).run()
    except asyncio.TimeoutError:
        print("\nno end after 7 minutes")


if __name__ == "__main__":
    asyncio.run(main())
