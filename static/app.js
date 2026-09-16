// Probe - the candidate's side.
//
// Two AssemblyAI connections, one microphone:
//
//   mic ──┬── Voice Agent API   : the conversation. It hears, decides what to
//         │                       say, speaks, and calls our tool.
//         └── Realtime STT      : the same audio again, for the timing of every
//                                 word. The agent connection returns text only,
//                                 and the verdict rests on timings.
//
// When the agent calls `assess_answer`, this page collects the words of the
// answer that just ended and asks the server for the verdict. The server
// decides; the agent only chooses how to word the follow-up.
//
// WHAT THE CANDIDATE SEES: the conversation, and nothing else. No score, no
// signal, no hint that an answer was probed. Showing it would teach a candidate
// what to fake.

const AGENT_URL = "wss://agents.assemblyai.com/v1/ws";
const STT_URL = "wss://streaming.assemblyai.com/v3/ws";
const RATE = 24000;
// How long to wait for the transcription connection to finish the last words of
// an answer before assessing it. The agent is holding its turn meanwhile.
const WORDS_SETTLE_MS = 1200;

let questions = [];
let agentWs, sttWs, audioContext, playerContext, player, stream;
let samplesSent = 0;
let words = [];            // every final word from the transcription connection
let lastWordAt = 0;        // when the last final word arrived (page clock)
let answerStartMs = 0;     // audio clock at the end of the agent's last reply
let baselineWords = null;  // the warm-up answer, what every later answer is compared to
let turns = [];            // the conversation, for the recruiter's report
let assessments = [];
let pendingResults = [];
let lastEvent = null;
let finished = false;
let failed = false;

const clockMs = () => (samplesSent / RATE) * 1000;
const $ = (id) => document.getElementById(id);

function show(name) {
  for (const screen of document.querySelectorAll(".screen")) screen.hidden = screen.id !== `screen-${name}`;
}

// -- welcome ------------------------------------------------------------------

$("consent").addEventListener("change", () => {
  $("start").disabled = !$("consent").checked || !questions.length;
  $("start-hint").textContent = $("consent").checked
    ? "Your browser will ask to use the microphone."
    : "Turn on the switch above to start.";
});

async function loadQuestions() {
  try {
    const response = await fetch("/api/questions");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    questions = (await response.json()).questions;
  } catch (error) {
    return fail("The interview could not load", "The questions did not arrive.",
      `Reason: ${error.message}. Reload the page in a moment.`);
  }
  $("count").textContent = `${questions.length} questions, plus whatever the interviewer asks next.`;
  $("start").disabled = !$("consent").checked;
}

// -- the two connections ---------------------------------------------------------

function systemPrompt() {
  const list = questions.map((q, i) => `${i}. ${q.text}`).join("\n");
  return [
    "You are conducting a short spoken job interview. You are warm, brief and neutral.",
    "Ask these questions in order, one at a time, in your own words but keeping their meaning:",
    list,
    "",
    "After every candidate answer, call the tool assess_answer with the index of the question they were answering and a one-line summary of the main claim they made. Wait for its result before you speak.",
    "The tool result contains an instruction. Follow it exactly: it tells you either to move on to the next question, or to ask exactly one follow-up.",
    "A follow-up must quote the candidate's own words and ask for something a prepared text would not contain: a concrete detail, a moment something went wrong, a trade-off, or why one specific decision was made. Ask one, listen to the answer, then move on.",
    "Never mention the tool, a score, an assessment, or that an answer sounded prepared or read. Never evaluate the candidate out loud, and never say whether an answer was good.",
    "Keep every turn under two sentences. When the last question has been answered, thank the candidate in one sentence and call end_interview.",
  ].join("\n");
}

const TOOLS = [
  {
    type: "function",
    name: "assess_answer",
    description: "Call this immediately after the candidate finishes answering a question, before you say anything. Returns the instruction you must follow next.",
    parameters: {
      type: "object",
      properties: {
        question_index: { type: "integer", description: "Index of the question they just answered, starting at 0" },
        claim: { type: "string", description: "One line: the main claim the candidate made" },
      },
      required: ["question_index", "claim"],
    },
    execution_mode: "interactive",
    timeout_seconds: 20,
  },
  {
    type: "function",
    name: "end_interview",
    description: "Call this once the last question has been answered and you have thanked the candidate.",
    parameters: { type: "object", properties: {}, required: [] },
    execution_mode: "interactive",
    timeout_seconds: 10,
  },
];

async function start() {
  $("start").disabled = true;
  $("start").replaceChildren(Object.assign(document.createElement("span"), { className: "spinner" }), " Connecting");

  let tokens;
  try {
    const response = await fetch("/api/tokens", { method: "POST" });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || `HTTP ${response.status}`);
    tokens = body;
  } catch (error) {
    return fail("The interview could not start", "The service that hears and answers you did not respond.",
      `Reason: ${error.message}. Try again in a moment; if it keeps happening, the recruiter can check the server.`);
  }

  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
  } catch (error) {
    if (error.name === "NotAllowedError") {
      return fail("Microphone access is blocked", "The interview needs your microphone, and the browser refused it.",
        "Click the icon at the left of the address bar, set Microphone to Allow, then press Try again.");
    }
    return fail("No microphone found", "The browser could not open a microphone.",
      `Plug in or enable a microphone, then press Try again. (${error.name})`);
  }

  openAgent(tokens.agent);
  openTranscription(tokens.streaming);
}

function openAgent(token) {
  agentWs = new WebSocket(`${AGENT_URL}?token=${encodeURIComponent(token)}`);
  agentWs.onopen = () => agentWs.send(JSON.stringify({
    type: "session.update",
    session: {
      system_prompt: systemPrompt(),
      greeting: `Thanks for joining. ${questions[0]?.text ?? ""}`,
      tools: TOOLS,
      output: { voice: "alba" },
      input: {
        // An interview answer has thinking pauses in it. Ending the turn on a
        // short silence would cut the candidate off mid-thought.
        turn_detection: { min_silence: 1200, max_silence: 4000, interrupt_response: true },
      },
    },
  }));
  agentWs.onmessage = (event) => handleAgent(JSON.parse(event.data));
  agentWs.onclose = (event) => {
    if (!finished && !failed && event.code !== 1000) {
      fail("The connection was lost", "The interview stopped before it was finished, and it was not saved.",
        "Check your internet connection, then press Try again to start over.");
    }
  };
}

function openTranscription(token) {
  const url = new URL(STT_URL);
  url.searchParams.set("token", token);
  url.searchParams.set("speech_model", "universal-3-5-pro");
  url.searchParams.set("sample_rate", String(RATE));
  url.searchParams.set("encoding", "pcm_s16le");
  url.searchParams.set("format_turns", "true");
  sttWs = new WebSocket(url);
  sttWs.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.type === "Turn" && message.end_of_turn) {
      // Only finalised turns carry settled timings; partials would be counted twice.
      for (const word of message.words || []) words.push(word);
      lastWordAt = performance.now();
    }
  };
}

// -- audio ---------------------------------------------------------------------------

async function startAudio() {
  audioContext = new AudioContext({ sampleRate: RATE });
  await audioContext.audioWorklet.addModule("/static/pcm-worklet.js");
  playerContext = new AudioContext({ sampleRate: RATE });
  await playerContext.audioWorklet.addModule("/static/player-worklet.js");
  player = new AudioWorkletNode(playerContext, "agent-player");
  player.connect(playerContext.destination);
  player.port.onmessage = ({ data }) => setSpeaking(Boolean(data));

  const source = audioContext.createMediaStreamSource(stream);
  const chunker = new AudioWorkletNode(audioContext, "pcm-chunker");
  chunker.port.onmessage = ({ data }) => {
    const pcm = new Int16Array(data.length);
    let peak = 0;
    for (let i = 0; i < data.length; i++) {
      const sample = Math.max(-1, Math.min(1, data[i]));
      pcm[i] = sample * 0x7fff;
      peak = Math.max(peak, Math.abs(sample));
    }
    samplesSent += data.length;
    updateLevel(peak);
    const bytes = new Uint8Array(pcm.buffer);
    if (agentWs?.readyState === WebSocket.OPEN) {
      agentWs.send(JSON.stringify({ type: "input.audio", audio: base64(bytes) }));
    }
    if (sttWs?.readyState === WebSocket.OPEN) sttWs.send(bytes);
  };
  source.connect(chunker);
}

function base64(bytes) {
  let binary = "";
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

function playAgentAudio(base64Audio) {
  const binary = atob(base64Audio);
  const pcm = new Int16Array(binary.length / 2);
  for (let i = 0; i < pcm.length; i++) {
    pcm[i] = (binary.charCodeAt(i * 2 + 1) << 8) | binary.charCodeAt(i * 2);
  }
  const floats = new Float32Array(pcm.length);
  for (let i = 0; i < pcm.length; i++) floats[i] = pcm[i] / 0x8000;
  player?.port.postMessage(floats);
}

let level = 0;
function updateLevel(peak) {
  level = level * 0.6 + Math.min(1, peak * 1.8) * 0.4;
  $("mic").style.setProperty("--level", level.toFixed(3));
}

function setSpeaking(on) {
  $("mic").classList.toggle("speaking", on);
  $("state-label").textContent = on ? "The interviewer is speaking" : "Listening. Answer when you are ready.";
}

// -- the agent's events ---------------------------------------------------------------

function handleAgent(message) {
  switch (message.type) {
    case "session.ready":
      startAudio().then(() => show("interview"));
      break;
    case "reply.audio":
      playAgentAudio(message.data);
      break;
    case "transcript.agent":
      addTurn("interviewer", message.text);
      break;
    case "transcript.user":
      addTurn("you", message.text);
      break;
    case "input.speech.started":
      player?.port.postMessage("flush");   // barge-in: stop the half-spoken sentence
      lastEvent = "input.speech.started";
      break;
    case "reply.started":
      lastEvent = "reply.started";
      break;
    case "reply.done":
      lastEvent = "reply.done";
      // The agent has stopped talking: whatever is said from now on is the answer.
      answerStartMs = clockMs();
      if (message.status === "interrupted") pendingResults = [];
      else flushResults();
      break;
    case "tool.call":
      handleTool(message);
      break;
    case "session.error":
      fail("The interview stopped", "The voice service reported a problem.",
        `${message.code || ""} ${message.message || ""}`.trim() + " Press Try again to start over.");
      break;
    default:
      break;
  }
}

async function handleTool(call) {
  if (call.name === "end_interview") {
    queueResult(call.call_id, { ok: true });
    return finish();
  }
  if (call.name !== "assess_answer") return queueResult(call.call_id, { error: "unknown tool" });

  const index = Number(call.arguments?.question_index ?? 0);
  const start = answerStartMs;
  await settle();
  const answerWords = words.filter((w) => w.start >= start);

  let verdict;
  try {
    const response = await fetch("/api/assess", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answer_words: answerWords, baseline_words: index === 0 ? null : baselineWords }),
    });
    verdict = await response.json();
    if (!response.ok) throw new Error(verdict.detail || `HTTP ${response.status}`);
  } catch (error) {
    // A failed assessment must not derail the interview: the agent moves on.
    verdict = { verdict: "not_measured", instruction: "Move on to the next question.", error: error.message };
  }
  if (index === 0 && answerWords.length) baselineWords = answerWords;
  assessments.push({ question_index: index, claim: call.arguments?.claim ?? "", words: answerWords, ...verdict });
  queueResult(call.call_id, { instruction: verdict.instruction, verdict: verdict.verdict });
}

// Give the transcription connection a moment to finalise the last words of the
// answer: it settles a beat after the agent's own turn detection fires.
function settle() {
  return new Promise((resolve) => {
    const deadline = performance.now() + WORDS_SETTLE_MS;
    const tick = () => {
      const quiet = performance.now() - lastWordAt > 400;
      if (quiet || performance.now() > deadline) resolve();
      else setTimeout(tick, 100);
    };
    tick();
  });
}

function queueResult(callId, result) {
  pendingResults.push({ call_id: callId, result });
  flushResults();
}

function flushResults() {
  if (lastEvent !== "reply.done" || !pendingResults.length || agentWs?.readyState !== WebSocket.OPEN) return;
  for (const pending of pendingResults) {
    agentWs.send(JSON.stringify({ type: "tool.result", call_id: pending.call_id, result: JSON.stringify(pending.result) }));
  }
  pendingResults = [];
}

// -- the conversation on screen -----------------------------------------------------------

function addTurn(role, text) {
  if (!text) return;
  turns.push({ role, text, at: Math.round(clockMs()) });
  const line = document.createElement("p");
  line.className = `turn ${role === "you" ? "you" : "interviewer"}`;
  line.append(Object.assign(document.createElement("b"), { textContent: role === "you" ? "You" : "Interviewer" }), " ", text);
  $("conversation").append(line);
  $("conversation").scrollTop = $("conversation").scrollHeight;
}

// -- the end -----------------------------------------------------------------------------------

async function finish() {
  if (finished) return;
  finished = true;
  show("saving");
  stream?.getTracks().forEach((track) => track.stop());
  setTimeout(() => agentWs?.send(JSON.stringify({ type: "session.end" })), 200);
  sttWs?.send(JSON.stringify({ type: "Terminate" }));

  try {
    const response = await fetch("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        recordedAt: new Date().toISOString(),
        questions,
        turns,
        assessments,
        words,
      }),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || `HTTP ${response.status}`);
    $("report-link").href = `/report?id=${encodeURIComponent(body.id)}`;
    show("done");
  } catch (error) {
    fail("Your interview was not saved", "The conversation finished, but saving it failed.",
      `Reason: ${error.message}. Keep this page open and tell the recruiter.`, false);
  }
}

function fail(title, text, fix, canRetry = true) {
  failed = true;
  $("error-title").textContent = title;
  $("error-text").textContent = text;
  $("error-fix").textContent = fix;
  $("retry").hidden = !canRetry;
  show("error");
  stream?.getTracks().forEach((track) => track.stop());
  for (const socket of [agentWs, sttWs]) {
    if (socket?.readyState === WebSocket.OPEN) socket.close(1000);
  }
}

$("start").addEventListener("click", start);
$("finish").addEventListener("click", finish);
$("retry").addEventListener("click", () => location.reload());
loadQuestions();
