const params = new URLSearchParams(window.location.search);
const mode = params.get("mode") || "chunks";
const cameraId = params.get("camera") || "1";
const facing = params.get("facing") || "environment";
const deviceId = params.get("device") || null;

const statusEl = document.getElementById("status");
const statsEl = document.getElementById("stats");
const pathEl = document.getElementById("save-path");
const elapsedEl = document.getElementById("elapsed");
pathEl.textContent = `Salvando na Pi em: ~/managerreplay-data/recordings/${mode}/<n-cameras>/camera-${cameraId}/`;

const startedAt = Date.now();
let totalBytesSent = 0;
let chunksSent = 0;

const LANCE_MIN_MS = 30000;
const lanceButtonEl = document.getElementById("lance-button");
lanceButtonEl.disabled = true;
lanceButtonEl.textContent = "⚡ Lance em 30s";

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

setInterval(updateStats, 1000);
updateStats();

const constraints = {
  video: deviceId
    ? {
        deviceId: { exact: deviceId },
        width: { ideal: 1280 },
        height: { ideal: 720 },
        frameRate: { ideal: 30 },
      }
    : {
        width: { ideal: 1280 },
        height: { ideal: 720 },
        frameRate: { ideal: 30 },
        facingMode: { ideal: facing },
      },
  audio: false,
};

async function populateDeviceSelect(activeStream) {
  const select = document.getElementById("camera-device");
  const devices = await navigator.mediaDevices.enumerateDevices();
  const videoDevices = devices.filter((d) => d.kind === "videoinput");

  const activeTrack = activeStream.getVideoTracks()[0];
  const activeDeviceId = activeTrack ? activeTrack.getSettings().deviceId : null;

  select.innerHTML = "";
  videoDevices.forEach((device, index) => {
    const option = document.createElement("option");
    option.value = device.deviceId;
    option.textContent = device.label || `Câmera ${index + 1}`;
    if (device.deviceId === activeDeviceId) option.selected = true;
    select.appendChild(option);
  });

  select.addEventListener("change", () => {
    const nextUrl = new URL(window.location.href);
    nextUrl.searchParams.set("device", select.value);
    nextUrl.searchParams.delete("facing");
    window.location.href = nextUrl.toString();
  });
}

async function startChunksMode(stream) {
  const recorder = new MediaRecorder(stream, { mimeType: "video/webm;codecs=vp8" });
  const sessionId = new Date().toISOString().replace(/[:.]/g, "-");
  let partNumber = 1;

  recorder.ondataavailable = async (event) => {
    if (event.data.size === 0) return;
    const part = partNumber++;
    await fetch(`/upload?camera=${cameraId}&session=${sessionId}&part=${part}`, {
      method: "POST",
      body: event.data,
    });
    totalBytesSent += event.data.size;
    chunksSent += 1;
    statusEl.textContent = `chunks: enviado parte ${part} (${formatBytes(event.data.size)})`;
    updateStats();
  };

  recorder.start(30000);
}

async function startWebrtcMode(stream) {
  const pc = new RTCPeerConnection();
  stream.getTracks().forEach((track) => pc.addTrack(track, stream));

  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);

  const response = await fetch(`/offer/${cameraId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sdp: pc.localDescription.sdp, type: pc.localDescription.type }),
  });
  const answer = await response.json();
  await pc.setRemoteDescription(answer);

  pc.onconnectionstatechange = () => {
    statusEl.textContent = `webrtc: ${pc.connectionState}`;
  };
}

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

  const stream = await navigator.mediaDevices.getUserMedia(constraints);
  document.getElementById("preview").srcObject = stream;
  await populateDeviceSelect(stream);

  if (mode === "chunks") {
    await startChunksMode(stream);
  } else {
    await startWebrtcMode(stream);
  }
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
