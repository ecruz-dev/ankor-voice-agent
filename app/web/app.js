
const els = {
  wsUrl: document.getElementById("wsUrl"),
  accessToken: document.getElementById("accessToken"),
  orgId: document.getElementById("orgId"),
  teamId: document.getElementById("teamId"),
  coachId: document.getElementById("coachId"),
  locale: document.getElementById("locale"),
  textInput: document.getElementById("textInput"),
  status: document.getElementById("status"),
  messages: document.getElementById("messages"),
  events: document.getElementById("events"),
  connectBtn: document.getElementById("connectBtn"),
  disconnectBtn: document.getElementById("disconnectBtn"),
  initBtn: document.getElementById("initBtn"),
  resetBtn: document.getElementById("resetBtn"),
  sendTextBtn: document.getElementById("sendTextBtn"),
  startMicBtn: document.getElementById("startMicBtn"),
  stopMicBtn: document.getElementById("stopMicBtn"),
};

const wsProtocol = window.location.protocol === "https:" ? "wss" : "ws";
els.wsUrl.value = `${wsProtocol}://${window.location.host}/ws/voice`;

let socket = null;
let audioCtx = null;
let micStream = null;
let sourceNode = null;
let processorNode = null;
let playbackQueue = [];
let playbackBusy = false;

function setStatus(text, isError = false) {
  els.status.textContent = text;
  els.status.style.color = isError ? "#ff7c7c" : "#7af2b7";
}

function appendMessage(kind, text) {
  const div = document.createElement("div");
  div.className = `entry ${kind}`;
  div.textContent = text;
  els.messages.appendChild(div);
  els.messages.scrollTop = els.messages.scrollHeight;
}

function appendEvent(obj) {
  const div = document.createElement("div");
  div.className = "entry";
  div.textContent = JSON.stringify(obj);
  els.events.appendChild(div);
  els.events.scrollTop = els.events.scrollHeight;
}

function send(payload) {
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    appendMessage("error", "Socket is not connected.");
    return;
  }
  socket.send(JSON.stringify(payload));
}

function decodeBase64ToInt16(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return new Int16Array(bytes.buffer);
}

function playPcm16(base64, sampleRate = 16000) {
  const pcm16 = decodeBase64ToInt16(base64);
  const floats = new Float32Array(pcm16.length);
  for (let i = 0; i < pcm16.length; i += 1) {
    floats[i] = Math.max(-1, Math.min(1, pcm16[i] / 32768));
  }
  playbackQueue.push({ floats, sampleRate });
  if (!playbackBusy) playNextChunk();
}

function playNextChunk() {
  if (!playbackQueue.length) {
    playbackBusy = false;
    return;
  }
  playbackBusy = true;
  if (!audioCtx) audioCtx = new AudioContext();
  const { floats, sampleRate } = playbackQueue.shift();
  const buffer = audioCtx.createBuffer(1, floats.length, sampleRate);
  buffer.copyToChannel(floats, 0, 0);
  const src = audioCtx.createBufferSource();
  src.buffer = buffer;
  src.connect(audioCtx.destination);
  src.onended = playNextChunk;
  src.start();
}

function floatToInt16Buffer(float32Array) {
  const int16 = new Int16Array(float32Array.length);
  for (let i = 0; i < float32Array.length; i += 1) {
    const s = Math.max(-1, Math.min(1, float32Array[i]));
    int16[i] = s < 0 ? s * 32768 : s * 32767;
  }
  return int16;
}

function downsampleTo16k(input, inputSampleRate) {
  if (inputSampleRate === 16000) return input;
  const ratio = inputSampleRate / 16000;
  const outLength = Math.round(input.length / ratio);
  const output = new Float32Array(outLength);
  let offsetResult = 0;
  let offsetBuffer = 0;
  while (offsetResult < output.length) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
    let accum = 0;
    let count = 0;
    for (let i = offsetBuffer; i < nextOffsetBuffer && i < input.length; i += 1) {
      accum += input[i];
      count += 1;
    }
    output[offsetResult] = count > 0 ? accum / count : 0;
    offsetResult += 1;
    offsetBuffer = nextOffsetBuffer;
  }
  return output;
}

async function startMic() {
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    appendMessage("error", "Connect first.");
    return;
  }
  if (!audioCtx) audioCtx = new AudioContext();
  micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  sourceNode = audioCtx.createMediaStreamSource(micStream);
  processorNode = audioCtx.createScriptProcessor(2048, 1, 1);

  processorNode.onaudioprocess = (event) => {
    const input = event.inputBuffer.getChannelData(0);
    const downsampled = downsampleTo16k(input, audioCtx.sampleRate);
    const int16 = floatToInt16Buffer(downsampled);
    const bytes = new Uint8Array(int16.buffer);
    let binary = "";
    for (let i = 0; i < bytes.byteLength; i += 1) {
      binary += String.fromCharCode(bytes[i]);
    }
    send({
      type: "input_audio_chunk",
      data: btoa(binary),
      sample_rate_hz: 16000,
      channels: 1,
      format: "pcm16le",
    });
  };

  sourceNode.connect(processorNode);
  processorNode.connect(audioCtx.destination);
  appendMessage("user", "Mic started");
}

function stopMic() {
  if (processorNode) {
    processorNode.disconnect();
    processorNode.onaudioprocess = null;
    processorNode = null;
  }
  if (sourceNode) {
    sourceNode.disconnect();
    sourceNode = null;
  }
  if (micStream) {
    micStream.getTracks().forEach((t) => t.stop());
    micStream = null;
  }
  send({ type: "client_event", name: "end_of_utterance" });
  appendMessage("user", "Mic stopped + end_of_utterance sent");
}

function connect() {
  if (socket && socket.readyState === WebSocket.OPEN) {
    appendMessage("error", "Already connected.");
    return;
  }

  socket = new WebSocket(els.wsUrl.value.trim());
  socket.onopen = () => {
    setStatus("Connected");
    send({ type: "auth", access_token: els.accessToken.value.trim() });
  };
  socket.onclose = () => setStatus("Disconnected");
  socket.onerror = () => setStatus("Socket error", true);
  socket.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    appendEvent(msg);
    if (msg.type === "auth_ok") appendMessage("agent", `auth_ok session_id=${msg.session_id}`);
    if (msg.type === "auth_error") appendMessage("error", msg.message || "auth_error");
    if (msg.type === "state_update") appendMessage("agent", `state_update ${JSON.stringify(msg.summary)}`);
    if (msg.type === "partial_transcript") appendMessage("agent", `partial: ${msg.text}`);
    if (msg.type === "final_transcript") appendMessage("agent", `final: ${msg.text}`);
    if (msg.type === "agent_message") appendMessage("agent", msg.text);
    if (msg.type === "error") appendMessage("error", `${msg.code}: ${msg.message}`);
    if (msg.type === "agent_audio_chunk") playPcm16(msg.data, msg.sample_rate_hz || 16000);
  };
}

function disconnect() {
  if (socket) socket.close();
  socket = null;
  stopMic();
}

function sendSessionInit() {
  send({
    type: "session_init",
    org_id: els.orgId.value.trim(),
    team_id: els.teamId.value.trim() || null,
    coach_id: els.coachId.value.trim() || null,
    evaluation_flow: "create_evaluation",
    locale: els.locale.value.trim() || "en-US",
  });
}

function resetSession() {
  send({ type: "session_control", action: "reset" });
}

function sendText() {
  const text = els.textInput.value.trim();
  if (!text) return;
  appendMessage("user", text);
  send({ type: "input_text", text });
}

els.connectBtn.addEventListener("click", connect);
els.disconnectBtn.addEventListener("click", disconnect);
els.initBtn.addEventListener("click", sendSessionInit);
els.resetBtn.addEventListener("click", resetSession);
els.sendTextBtn.addEventListener("click", sendText);
els.startMicBtn.addEventListener("click", startMic);
els.stopMicBtn.addEventListener("click", stopMic);
