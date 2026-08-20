const params = new URLSearchParams(window.location.search);
const mode = "chunks";
const cameraId = params.get("camera") || "1";
const facing = params.get("facing") || "environment";
const deviceId = params.get("device") || null;
const operatorName = params.get("name") || "";

const statusEl = document.getElementById("status");
const statsEl = document.getElementById("stats");
const pathEl = document.getElementById("save-path");
const elapsedEl = document.getElementById("elapsed");
pathEl.textContent = `Salvando na Pi em: ~/managerreplay/data/recordings/camera-${cameraId}/`;

if (operatorName) {
  document.getElementById("operator-name").textContent = operatorName;
  document.getElementById("operator-badge").hidden = false;
}

let totalBytesSent = 0;
let chunksSent = 0;
let startedAt = null;
let statsTimer = null;

const LANCE_MIN_MS = 30000;
const lanceButtonEl = document.getElementById("lance-button");
const recordToggleEl = document.getElementById("record-toggle");
const recBadgeEl = document.getElementById("rec-badge");
const deviceSelectEl = document.getElementById("camera-device");
const qualitySelectEl = document.getElementById("quality-select");
const saveToastEl = document.getElementById("save-toast");

const QUALITY_PRESETS = {
  hd30: { width: 1280, height: 720, frameRate: 30 },
  hd60: { width: 1280, height: 720, frameRate: 60 },
  fhd30: { width: 1920, height: 1080, frameRate: 30 },
  fhd60: { width: 1920, height: 1080, frameRate: 60 },
};

let quality = params.get("quality") || "hd30";
if (!QUALITY_PRESETS[quality]) quality = "hd30";
qualitySelectEl.value = quality;

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function formatElapsed(ms) {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function updateStats() {
  const elapsedMs = Date.now() - startedAt;
  elapsedEl.textContent = formatElapsed(elapsedMs);
  statsEl.textContent = `Modo: ${mode} · Câmera: ${cameraId} · Chunks enviados: ${chunksSent} · Total enviado: ${formatBytes(totalBytesSent)}`;

  if (elapsedMs >= LANCE_MIN_MS) {
    if (lanceButtonEl.disabled) {
      lanceButtonEl.disabled = false;
      lanceButtonEl.textContent = "⚡ Lance";
    }
  } else {
    const remaining = Math.ceil((LANCE_MIN_MS - elapsedMs) / 1000);
    lanceButtonEl.textContent = `⚡ Lance em ${remaining}s`;
  }
}

function buildVideoConstraints(overrideDeviceId) {
  const preset = QUALITY_PRESETS[quality];
  const base = {
    width: { ideal: preset.width },
    height: { ideal: preset.height },
    frameRate: { ideal: preset.frameRate },
  };
  const targetDeviceId = overrideDeviceId || deviceId;
  return targetDeviceId
    ? { ...base, deviceId: { exact: targetDeviceId } }
    : { ...base, facingMode: { ideal: facing } };
}

const constraints = { video: buildVideoConstraints(), audio: false };

const FACING_LABEL_HINTS = {
  environment: ["back", "traseira", "rear", "environment"],
  user: ["front", "frontal", "user", "selfie"],
};

function matchesFacing(label, targetFacing) {
  const hints = FACING_LABEL_HINTS[targetFacing] || [];
  const lower = label.toLowerCase();
  return hints.some((hint) => lower.includes(hint));
}

async function populateDeviceSelect(activeStream) {
  const select = document.getElementById("camera-device");
  const devices = await navigator.mediaDevices.enumerateDevices();
  const videoDevices = devices.filter((d) => d.kind === "videoinput");

  // Restrict the list to the side (frontal/traseira) this camera slot is locked to.
  // Labels are only reliably available once permission is granted, which is
  // already true here since activeStream exists; fall back to the full list
  // if no device label matches (some browsers/devices don't expose hints).
  const matching = videoDevices.filter((d) => matchesFacing(d.label, facing));
  const relevantDevices = matching.length > 0 ? matching : videoDevices;

  const activeTrack = activeStream.getVideoTracks()[0];
  const activeDeviceId = activeTrack ? activeTrack.getSettings().deviceId : null;

  select.innerHTML = "";
  relevantDevices.forEach((device, index) => {
    const option = document.createElement("option");
    option.value = device.deviceId;
    option.textContent = device.label || `Câmera ${index + 1}`;
    if (device.deviceId === activeDeviceId) option.selected = true;
    select.appendChild(option);
  });

  select.addEventListener("change", () => switchCamera(select.value));
}

async function switchVideoTrack(newConstraints, urlUpdates) {
  const newStream = await navigator.mediaDevices.getUserMedia({ video: newConstraints, audio: false });
  const newVideoTrack = newStream.getVideoTracks()[0];
  const oldVideoTrack = mediaStream.getVideoTracks()[0];

  // Swap the track on the same MediaStream object instead of reloading the
  // page, so an in-progress MediaRecorder keeps recording continuously
  // (same session, same part sequence) instead of starting a new file series.
  mediaStream.removeTrack(oldVideoTrack);
  mediaStream.addTrack(newVideoTrack);
  oldVideoTrack.stop();

  document.getElementById("preview").srcObject = mediaStream;

  const nextUrl = new URL(window.location.href);
  Object.entries(urlUpdates).forEach(([key, value]) => nextUrl.searchParams.set(key, value));
  window.history.replaceState({}, "", nextUrl.toString());
}

function switchCamera(newDeviceId) {
  return switchVideoTrack(buildVideoConstraints(newDeviceId), { device: newDeviceId });
}

qualitySelectEl.addEventListener("change", () => {
  quality = qualitySelectEl.value;
  const activeDeviceId = mediaStream.getVideoTracks()[0].getSettings().deviceId;
  switchVideoTrack(buildVideoConstraints(activeDeviceId), { quality });
});

let mediaStream = null;
let recorder = null;
let lastUploadPromise = Promise.resolve();

function beginRecording() {
  totalBytesSent = 0;
  chunksSent = 0;
  startedAt = Date.now();
  lastUploadPromise = Promise.resolve();

  recorder = new MediaRecorder(mediaStream, { mimeType: "video/webm;codecs=vp8" });
  const sessionId = new Date().toISOString().replace(/[:.]/g, "-");
  let partNumber = 1;

  recorder.ondataavailable = (event) => {
    if (event.data.size === 0) return;
    const part = partNumber++;
    lastUploadPromise = lastUploadPromise.then(async () => {
      await fetch(`/upload?camera=${cameraId}&session=${sessionId}&part=${part}`, {
        method: "POST",
        body: event.data,
      });
      totalBytesSent += event.data.size;
      chunksSent += 1;
      statusEl.textContent = `chunks: enviado parte ${part} (${formatBytes(event.data.size)})`;
      updateStats();
    });
  };

  recorder.start(30000);

  qualitySelectEl.disabled = true;
  recBadgeEl.hidden = false;
  recordToggleEl.textContent = "■ Parar gravação";
  recordToggleEl.classList.add("recording");
  lanceButtonEl.hidden = false;
  lanceButtonEl.disabled = true;
  lanceButtonEl.textContent = "⚡ Lance em 30s";
  statsTimer = setInterval(updateStats, 1000);
  updateStats();
}

function showSavedToast() {
  saveToastEl.textContent = "✅ Gravação salva no app";
  saveToastEl.classList.add("visible");
  setTimeout(() => saveToastEl.classList.remove("visible"), 3000);
}

async function endRecording() {
  recordToggleEl.disabled = true;
  const stopped = new Promise((resolve) => {
    recorder.onstop = resolve;
  });
  recorder.stop();
  await stopped;
  await lastUploadPromise;

  clearInterval(statsTimer);
  qualitySelectEl.disabled = false;
  recBadgeEl.hidden = true;
  deviceSelectEl.disabled = false;
  lanceButtonEl.hidden = true;
  recordToggleEl.textContent = "● Iniciar gravação";
  recordToggleEl.classList.remove("recording");
  recordToggleEl.disabled = false;
  statusEl.textContent = "pronto pra gravar";
  showSavedToast();
}

recordToggleEl.addEventListener("click", () => {
  if (recorder && recorder.state === "recording") {
    endRecording();
  } else {
    beginRecording();
  }
});

let wakeLock = null;

async function requestWakeLock() {
  if (!("wakeLock" in navigator)) return;
  try {
    wakeLock = await navigator.wakeLock.request("screen");
  } catch (err) {
    console.error("wake lock failed:", err);
  }
}

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") {
    requestWakeLock();
  }
});

async function start() {
  await requestWakeLock();

  mediaStream = await navigator.mediaDevices.getUserMedia(constraints);
  document.getElementById("preview").srcObject = mediaStream;
  await populateDeviceSelect(mediaStream);
  statusEl.textContent = "pronto pra gravar";
}

const lanceToastEl = document.getElementById("lance-toast");
const videoWrapEl = document.getElementById("video-wrap");
let lanceToastTimer = null;

function notifyLancePressed(message) {
  lanceToastEl.textContent = message;
  lanceToastEl.classList.add("visible");
  clearTimeout(lanceToastTimer);
  lanceToastTimer = setTimeout(() => lanceToastEl.classList.remove("visible"), 3000);

  videoWrapEl.classList.remove("flash");
  void videoWrapEl.offsetWidth; // force reflow so the animation restarts on repeated clicks
  videoWrapEl.classList.add("flash");

  if (navigator.vibrate) navigator.vibrate(150);
}

lanceButtonEl.addEventListener("click", async () => {
  try {
    const response = await fetch(`/events?camera=${cameraId}`, { method: "POST" });
    const event = await response.json();
    notifyLancePressed(`✅ ${event.nome} registrado`);
  } catch (err) {
    notifyLancePressed(`erro ao registrar lance: ${err.message}`);
  }
});

start().catch((err) => {
  statusEl.textContent = `erro: ${err.message}`;
  console.error(err);
});
