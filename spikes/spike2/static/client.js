const params = new URLSearchParams(window.location.search);
const mode = params.get("mode") || "chunks";
const cameraId = params.get("camera") || "1";
const facing = params.get("facing") || "environment";
const deviceId = params.get("device") || null;

const statusEl = document.getElementById("status");
const statsEl = document.getElementById("stats");
const pathEl = document.getElementById("save-path");
document.getElementById("mode-label").textContent = mode;
document.getElementById("camera-label").textContent = cameraId;
pathEl.textContent = `Salvando na Pi em: ~/highlightbox-spike2/${mode}/<n-cameras>/camera-${cameraId}/`;

const startedAt = Date.now();
let totalBytesSent = 0;
let chunksSent = 0;

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
  const elapsed = formatElapsed(Date.now() - startedAt);
  statsEl.textContent = `Tempo gravado: ${elapsed} · Chunks enviados: ${chunksSent} · Total enviado: ${formatBytes(totalBytesSent)}`;
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
  let sequence = 0;

  recorder.ondataavailable = async (event) => {
    if (event.data.size === 0) return;
    const seq = sequence++;
    await fetch(`/upload?camera=${cameraId}&seq=${seq}`, {
      method: "POST",
      body: event.data,
    });
    totalBytesSent += event.data.size;
    chunksSent += 1;
    statusEl.textContent = `chunks: enviado chunk ${seq} (${formatBytes(event.data.size)})`;
    updateStats();
  };

  recorder.start(7000);
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

start().catch((err) => {
  statusEl.textContent = `erro: ${err.message}`;
  console.error(err);
});
