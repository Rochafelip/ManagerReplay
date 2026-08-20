const params = new URLSearchParams(window.location.search);
const mode = params.get("mode") || "chunks";
const cameraId = params.get("camera") || "1";
const facing = params.get("facing") || "environment";

const statusEl = document.getElementById("status");
document.getElementById("mode-label").textContent = mode;
document.getElementById("camera-label").textContent = cameraId;

document.getElementById("switch-camera").addEventListener("click", () => {
  const nextFacing = facing === "environment" ? "user" : "environment";
  const nextUrl = new URL(window.location.href);
  nextUrl.searchParams.set("facing", nextFacing);
  window.location.href = nextUrl.toString();
});

const constraints = {
  video: {
    width: { ideal: 1280 },
    height: { ideal: 720 },
    frameRate: { ideal: 30 },
    facingMode: { ideal: facing },
  },
  audio: false,
};

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
    statusEl.textContent = `chunks: enviado chunk ${seq} (${event.data.size} bytes)`;
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

async function start() {
  const stream = await navigator.mediaDevices.getUserMedia(constraints);
  document.getElementById("preview").srcObject = stream;

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
