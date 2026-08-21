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

// Upload health, surfaced in Detalhes técnicos so the person recording can
// spot a struggling connection without needing someone else watching
// "Quem está gravando" on another screen.
let pendingUploads = 0;
let lastChunkConfirmedAt = null;
let lastUploadLatencyMs = null;
let lastUploadRateBytesPerSec = null;

const transferStatsEl = document.getElementById("transfer-stats");

const LANCE_MIN_MS = 30000;
const lanceButtonEl = document.getElementById("lance-button");
const lanceButtonLabelEl = document.getElementById("lance-button-label");
const recordToggleEl = document.getElementById("record-toggle");
const recordToggleLabelEl = document.getElementById("record-toggle-label");
const recBadgeEl = document.getElementById("rec-badge");
const deviceSelectEl = document.getElementById("camera-device");
const qualitySelectEl = document.getElementById("quality-select");
const saveToastEl = document.getElementById("save-toast");
const saveToastLabelEl = document.getElementById("save-toast-label");

const QUALITY_PRESETS = {
  hd30: { width: 1280, height: 720, frameRate: 30, label: "HD · 30fps" },
  hd60: { width: 1280, height: 720, frameRate: 60, label: "HD · 60fps" },
  fhd30: { width: 1920, height: 1080, frameRate: 30, label: "FHD · 30fps" },
  fhd60: { width: 1920, height: 1080, frameRate: 60, label: "FHD · 60fps" },
  uhd30: { width: 3840, height: 2160, frameRate: 30, label: "4K · 30fps" },
  uhd60: { width: 3840, height: 2160, frameRate: 60, label: "4K · 60fps" },
};

// Presets known to work broadly (Safari/iOS mostly doesn't expose
// getCapabilities(), so we can't confirm anything beyond these — see
// supportedQualityIds below). 4K only ever shows up when detected.
const FALLBACK_QUALITY_IDS = ["hd30", "hd60", "fhd30", "fhd60"];

// Preferred order when picking the default: target HD·60fps, only
// stepping down/up from there if the device can't actually do it.
const DEFAULT_QUALITY_PRIORITY = ["hd60", "hd30", "fhd60", "fhd30", "uhd60", "uhd30"];

let quality = params.get("quality") || "hd60";
if (!QUALITY_PRESETS[quality]) quality = "hd60";

// supportedIds is null while getUserMedia hasn't resolved yet; the actual
// quality list is only built once we can inspect the camera's real limits.
//
// Only gates on width/height — capabilities.frameRate.max is unreliable on
// Android Chrome (observed on a Galaxy S20 FE reporting max 30 for a sensor
// that does 60fps just fine): it reflects whatever format got negotiated
// for the current request, not the device's real ceiling. frameRate stays
// an "ideal" constraint everywhere it's used (see buildVideoConstraints),
// so it's never fatal to offer 60fps and let the browser do its best.
function supportedQualityIds(capabilities) {
  if (!capabilities || !capabilities.width || !capabilities.height) {
    return FALLBACK_QUALITY_IDS;
  }
  const maxWidth = capabilities.width.max || 0;
  const maxHeight = capabilities.height.max || 0;
  const supported = Object.keys(QUALITY_PRESETS).filter((id) => {
    const preset = QUALITY_PRESETS[id];
    return maxWidth >= preset.width && maxHeight >= preset.height;
  });
  return supported.length > 0 ? supported : FALLBACK_QUALITY_IDS;
}

function pickDefaultQuality(supportedIds) {
  const requested = params.get("quality");
  if (requested && supportedIds.includes(requested)) return requested;
  return DEFAULT_QUALITY_PRIORITY.find((id) => supportedIds.includes(id)) || supportedIds[0];
}

function populateQualitySelect(supportedIds, selectedId) {
  qualitySelectEl.innerHTML = "";
  supportedIds.forEach((id) => {
    const option = document.createElement("option");
    option.value = id;
    option.textContent = QUALITY_PRESETS[id].label;
    if (id === selectedId) option.selected = true;
    qualitySelectEl.appendChild(option);
  });
}

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

function updateTransferStats() {
  if (!transferStatsEl) return;

  const rate = lastUploadRateBytesPerSec != null ? `${formatBytes(Math.round(lastUploadRateBytesPerSec))}/s` : "—";
  const latency = lastUploadLatencyMs != null ? `${Math.round(lastUploadLatencyMs)} ms` : "—";
  const sinceLast = lastChunkConfirmedAt != null
    ? `${Math.round((Date.now() - lastChunkConfirmedAt) / 1000)}s atrás`
    : "aguardando 1º envio";

  transferStatsEl.textContent =
    `Taxa: ${rate} · Fila: ${pendingUploads} · Último envio: ${sinceLast} · Latência: ${latency}`;
}

function updateStats() {
  const elapsedMs = Date.now() - startedAt;
  elapsedEl.textContent = formatElapsed(elapsedMs);
  const cameraLabel = facing === "user" ? "Frontal" : "Traseira";
  statsEl.textContent = `Modo: ${mode} · Câmera: ${cameraLabel} · Chunks enviados: ${chunksSent} · Total enviado: ${formatBytes(totalBytesSent)}`;
  updateTransferStats();

  if (elapsedMs >= LANCE_MIN_MS) {
    if (lanceButtonEl.disabled) {
      lanceButtonEl.disabled = false;
      lanceButtonLabelEl.textContent = "Lance";
    }
  } else {
    const remaining = Math.ceil((LANCE_MIN_MS - elapsedMs) / 1000);
    lanceButtonLabelEl.textContent = `Lance em ${remaining}s`;
  }
}

function buildVideoConstraints(overrideDeviceId, { strictFrameRate = false } = {}) {
  const preset = QUALITY_PRESETS[quality];
  const base = {
    width: { ideal: preset.width },
    height: { ideal: preset.height },
    // "ideal" alone is just a soft hint — Chrome/Android has been observed
    // silently settling for a lower fps (e.g. staying at 30 when 60 was
    // requested) instead of honoring it. Forcing "min" makes it a real
    // requirement: either the device delivers it, or getUserMedia throws
    // OverconstrainedError and callers can react instead of getting an
    // unfulfilled request with no feedback.
    frameRate: strictFrameRate
      ? { min: preset.frameRate, ideal: preset.frameRate }
      : { ideal: preset.frameRate },
  };
  const targetDeviceId = overrideDeviceId || deviceId;
  return targetDeviceId
    ? { ...base, deviceId: { exact: targetDeviceId } }
    : { ...base, facingMode: { ideal: facing } };
}

async function requestVideoStream(overrideDeviceId) {
  try {
    return await navigator.mediaDevices.getUserMedia({
      video: buildVideoConstraints(overrideDeviceId, { strictFrameRate: true }),
      audio: false,
    });
  } catch (err) {
    if (err.name !== "OverconstrainedError") throw err;
    // The device genuinely can't hit that fps at this resolution — fall
    // back to the soft request so the switch still succeeds, just at
    // whatever fps the camera actually delivers.
    return navigator.mediaDevices.getUserMedia({
      video: buildVideoConstraints(overrideDeviceId, { strictFrameRate: false }),
      audio: false,
    });
  }
}

const FACING_LABEL_HINTS = {
  environment: ["back", "traseira", "rear", "environment"],
  user: ["front", "frontal", "user", "selfie"],
};

function matchesFacing(label, targetFacing) {
  const hints = FACING_LABEL_HINTS[targetFacing] || [];
  const lower = label.toLowerCase();
  return hints.some((hint) => lower.includes(hint));
}

const LENS_HINTS = [
  [/ultra.?wide|wide.?angle/, "grande angular"],
  [/tele/, "teleobjetiva"],
  [/macro/, "macro"],
];

function friendlyDeviceLabel(device, index, total) {
  const base = facing === "user" ? "Frontal" : "Traseira";
  const lower = (device.label || "").toLowerCase();
  const lensHint = LENS_HINTS.find(([pattern]) => pattern.test(lower));
  const suffix = lensHint ? ` (${lensHint[1]})` : "";
  return total > 1 ? `${base} ${index + 1}${suffix}` : `${base}${suffix}`;
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
    option.textContent = friendlyDeviceLabel(device, index, relevantDevices.length);
    if (device.deviceId === activeDeviceId) option.selected = true;
    select.appendChild(option);
  });

  select.addEventListener("change", () => {
    switchCamera(select.value).catch((err) => {
      statusEl.textContent = `erro ao trocar de lente: ${err.message}`;
      console.error(err);
    });
  });
}

const cameraInfoEl = document.getElementById("camera-info");

function updateCameraInfo(track) {
  if (!cameraInfoEl) return;
  const settings = track.getSettings();
  const width = settings.width || "?";
  const height = settings.height || "?";
  const fps = settings.frameRate ? Math.round(settings.frameRate) : null;
  let text = `Câmera ativa: ${width}×${height} @ ${fps ?? "?"}fps`;

  // Ground truth beats trusting the request: even a "min" (hard) frameRate
  // constraint isn't always honored by Android's camera stack — some
  // phones' default capture session caps fps below what the sensor can
  // technically do in its native camera app (that uses a different,
  // vendor-specific high-speed session the browser has no access to).
  // Surface the mismatch here instead of leaving it looking like a bug.
  const targetFps = QUALITY_PRESETS[quality].frameRate;
  if (fps && fps < targetFps - 2) {
    text += ` (pediu ${targetFps}fps, aparelho não entregou)`;
  }

  cameraInfoEl.textContent = text;
}

function refreshPreview() {
  const previewEl = document.getElementById("preview");
  // Reassigning to the exact same MediaStream object reference sometimes
  // doesn't repaint on Android WebViews after only the tracks changed
  // underneath it — force a clean re-attach instead of relying on it to
  // notice.
  previewEl.srcObject = null;
  previewEl.srcObject = mediaStream;
  return previewEl.play().catch(() => {
    // Autoplay can reject if the tab lost focus mid-switch; harmless, the
    // element still has the right stream attached.
  });
}

async function switchVideoTrack(overrideDeviceId, urlUpdates) {
  const oldVideoTrack = mediaStream.getVideoTracks()[0];
  const oldDeviceId = oldVideoTrack.getSettings().deviceId;

  // Release the current camera BEFORE requesting the new one. Phones with
  // multiple rear lenses (normal/wide/macro) typically share one hardware
  // pipeline and refuse to open a second stream while the first is still
  // active — that's the "Could not start video source" error seen on a
  // Galaxy S20 FE when this used to request-then-release.
  oldVideoTrack.stop();
  mediaStream.removeTrack(oldVideoTrack);

  let newVideoTrack;
  try {
    const newStream = await requestVideoStream(overrideDeviceId);
    newVideoTrack = newStream.getVideoTracks()[0];
  } catch (err) {
    // Couldn't get the requested lens — reopen the one we just released
    // instead of leaving the preview (and any in-progress recording) dead.
    const restoredStream = await navigator.mediaDevices.getUserMedia({
      video: buildVideoConstraints(oldDeviceId),
      audio: false,
    });
    mediaStream.addTrack(restoredStream.getVideoTracks()[0]);
    await refreshPreview();
    throw err;
  }

  mediaStream.addTrack(newVideoTrack);
  await refreshPreview();
  updateCameraInfo(newVideoTrack);

  const nextUrl = new URL(window.location.href);
  Object.entries(urlUpdates).forEach(([key, value]) => nextUrl.searchParams.set(key, value));
  window.history.replaceState({}, "", nextUrl.toString());
}

function switchCamera(newDeviceId) {
  return switchVideoTrack(newDeviceId, { device: newDeviceId });
}

qualitySelectEl.addEventListener("change", () => {
  quality = qualitySelectEl.value;
  const activeDeviceId = mediaStream.getVideoTracks()[0].getSettings().deviceId;
  switchVideoTrack(activeDeviceId, { quality }).catch((err) => {
    statusEl.textContent = `erro ao trocar qualidade: ${err.message}`;
    console.error(err);
  });
});

// Rolling buffer for "Lance" clips: a second MediaRecorder on the same
// stream, running back-to-back self-contained windows (each stop() yields
// a complete, independently playable webm — unlike the 30s chunks above,
// which are Matroska continuation clusters that only play when concatenated
// from part 1).
//
// Pressing "Lance" ends the CURRENT window right then — instead of handing
// over whatever window had already finished — so the clip always covers up
// to the exact moment of the click (never misses it), at the cost of a
// variable clip length: up to LANCE_WINDOW_MS if clicked right before a
// natural rollover, as little as a couple seconds if clicked right after a
// fresh window started. A fixed-length "always the last full window"
// version used to leave a gap between when that window ended and the
// actual click — this trades a predictable duration for never losing the
// moment itself. Still no exact "N seconds before" cut, and still no
// ffmpeg re-encoding on the Pi — see the design discussion for why.
const LANCE_WINDOW_MS = 10000;
let lanceRingRecorder = null;
let lanceRingTimeoutId = null;
let lanceRingChunks = [];

function startLanceRingWindow() {
  lanceRingChunks = [];
  lanceRingRecorder = new MediaRecorder(mediaStream, { mimeType: "video/webm;codecs=vp8" });
  lanceRingRecorder.ondataavailable = (event) => {
    if (event.data.size > 0) lanceRingChunks.push(event.data);
  };
  lanceRingRecorder.start();
  lanceRingTimeoutId = setTimeout(rolloverLanceRingWindow, LANCE_WINDOW_MS);
}

// Natural end of a window nobody clipped — just resets the clock so a
// window is never more than LANCE_WINDOW_MS long by the time it's used.
function rolloverLanceRingWindow() {
  if (!lanceRingRecorder || lanceRingRecorder.state !== "recording") return;
  lanceRingRecorder.onstop = () => {
    if (recorder && recorder.state === "recording") startLanceRingWindow();
  };
  lanceRingRecorder.stop();
}

// Ends the current window right now and starts the next one once it's
// done. Resolves with the finished clip, or null if there's no active
// window to capture from (e.g. called outside a recording session).
function captureLanceClip() {
  if (!lanceRingRecorder || lanceRingRecorder.state !== "recording") return Promise.resolve(null);

  clearTimeout(lanceRingTimeoutId);
  const recorderToStop = lanceRingRecorder;
  const chunksToKeep = lanceRingChunks;
  return new Promise((resolve) => {
    recorderToStop.onstop = () => {
      resolve(new Blob(chunksToKeep, { type: "video/webm" }));
      if (recorder && recorder.state === "recording") startLanceRingWindow();
    };
    recorderToStop.stop();
  });
}

function stopLanceRingWindow() {
  clearTimeout(lanceRingTimeoutId);
  if (lanceRingRecorder && lanceRingRecorder.state === "recording") {
    lanceRingRecorder.onstop = null;
    lanceRingRecorder.stop();
  }
  lanceRingRecorder = null;
  lanceRingChunks = [];
}

let mediaStream = null;
let recorder = null;
let lastUploadPromise = Promise.resolve();

function beginRecording() {
  totalBytesSent = 0;
  chunksSent = 0;
  startedAt = Date.now();
  lastUploadPromise = Promise.resolve();
  pendingUploads = 0;
  lastChunkConfirmedAt = null;
  lastUploadLatencyMs = null;
  lastUploadRateBytesPerSec = null;

  recorder = new MediaRecorder(mediaStream, { mimeType: "video/webm;codecs=vp8" });
  const sessionId = new Date().toISOString().replace(/[:.]/g, "-");
  let partNumber = 1;

  recorder.ondataavailable = (event) => {
    if (event.data.size === 0) return;
    const part = partNumber++;
    pendingUploads += 1;
    lastUploadPromise = lastUploadPromise.then(async () => {
      const uploadStartedAt = performance.now();
      await fetch(`/upload?camera=${cameraId}&session=${sessionId}&part=${part}`, {
        method: "POST",
        body: event.data,
      });
      const latencyMs = performance.now() - uploadStartedAt;

      pendingUploads -= 1;
      totalBytesSent += event.data.size;
      chunksSent += 1;
      lastChunkConfirmedAt = Date.now();
      lastUploadLatencyMs = latencyMs;
      lastUploadRateBytesPerSec = latencyMs > 0 ? (event.data.size / latencyMs) * 1000 : null;

      statusEl.textContent = `chunks: enviado parte ${part} (${formatBytes(event.data.size)})`;
      updateStats();
    });
  };

  recorder.start(30000);
  startLanceRingWindow();

  fetch(`/session-start?camera=${cameraId}&name=${encodeURIComponent(operatorName)}&quality=${quality}`, {
    method: "POST",
  });

  qualitySelectEl.disabled = true;
  recBadgeEl.hidden = false;
  recordToggleLabelEl.textContent = "Parar gravação";
  recordToggleEl.classList.add("recording");
  lanceButtonEl.hidden = false;
  lanceButtonEl.disabled = true;
  lanceButtonLabelEl.textContent = "Lance em 30s";
  statsTimer = setInterval(updateStats, 1000);
  updateStats();
}

function showSavedToast() {
  saveToastLabelEl.textContent = "Gravação salva no app";
  saveToastEl.classList.add("visible");
  setTimeout(() => saveToastEl.classList.remove("visible"), 3000);
}

async function endRecording() {
  recordToggleEl.disabled = true;
  stopLanceRingWindow();
  const stopped = new Promise((resolve) => {
    recorder.onstop = resolve;
  });
  recorder.stop();
  await stopped;
  await lastUploadPromise;
  await fetch(`/session-stop?camera=${cameraId}`, { method: "POST" });

  clearInterval(statsTimer);
  qualitySelectEl.disabled = false;
  recBadgeEl.hidden = true;
  deviceSelectEl.disabled = false;
  lanceButtonEl.hidden = true;
  recordToggleLabelEl.textContent = "Iniciar gravação";
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

async function applyDetectedQuality() {
  const activeTrack = mediaStream.getVideoTracks()[0];
  const capabilities = activeTrack.getCapabilities ? activeTrack.getCapabilities() : null;
  const supportedIds = supportedQualityIds(capabilities);
  const resolvedQuality = pickDefaultQuality(supportedIds);
  populateQualitySelect(supportedIds, resolvedQuality);

  if (resolvedQuality === quality) return;
  quality = resolvedQuality;
  await switchVideoTrack(activeTrack.getSettings().deviceId, { quality });
}

async function start() {
  await requestWakeLock();

  // Uses the strict (fps-enforcing) request from the very first capture —
  // otherwise the default quality already "matching" (hd60) meant
  // applyDetectedQuality's own strict re-request never even ran, and the
  // camera was left on whatever fps the soft initial request settled for.
  mediaStream = await requestVideoStream();
  document.getElementById("preview").srcObject = mediaStream;
  updateCameraInfo(mediaStream.getVideoTracks()[0]);
  await applyDetectedQuality();
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
  // Kicked off before anything else so the clip's cutoff is as close to the
  // actual click as possible, instead of waiting on the /events round trip.
  const clipPromise = captureLanceClip();
  try {
    const response = await fetch(`/events?camera=${cameraId}`, { method: "POST" });
    const event = await response.json();
    notifyLancePressed(`✅ ${event.nome} registrado`);

    const clipBlob = await clipPromise;
    if (clipBlob) {
      fetch(`/lance-clip?camera=${cameraId}&nome=${encodeURIComponent(event.nome)}`, {
        method: "POST",
        body: clipBlob,
      });
    }
  } catch (err) {
    notifyLancePressed(`erro ao registrar lance: ${err.message}`);
  }
});

start().catch((err) => {
  statusEl.textContent = `erro: ${err.message}`;
  console.error(err);
});
