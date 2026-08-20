import ssl
from pathlib import Path

from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaRecorder

from server.events import record_event
from server.file_listing import list_directory
from server.monitor_status import read_latest_status
from server.storage import build_camera_dir

_active_connections: set[RTCPeerConnection] = set()


async def _handle_offer(request: web.Request) -> web.Response:
    camera_id = int(request.match_info["camera_id"])
    storage_root: Path = request.app["storage_root"]

    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    _active_connections.add(pc)

    camera_dir = build_camera_dir(storage_root, camera_id)
    recorder = MediaRecorder(str(camera_dir / "recording.webm"))

    @pc.on("track")
    def on_track(track):
        if track.kind == "video":
            recorder.addTrack(track)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        if pc.connectionState in ("failed", "closed"):
            await recorder.stop()
            await pc.close()
            _active_connections.discard(pc)

    await pc.setRemoteDescription(offer)
    await recorder.start()

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.json_response({"sdp": pc.localDescription.sdp, "type": pc.localDescription.type})


async def _handle_event(request: web.Request) -> web.Response:
    camera_id = request.query.get("camera", "?")
    events_file: Path = request.app["events_file"]
    event = record_event(events_file, camera_id)
    return web.json_response(event)


async def _handle_files_list(request: web.Request) -> web.Response:
    storage_root: Path = request.app["storage_root"]
    rel_path = request.query.get("path", "")
    try:
        entries = list_directory(storage_root, rel_path)
    except (ValueError, FileNotFoundError) as err:
        return web.Response(status=404, text=str(err))
    return web.json_response(entries)


async def _handle_monitor_status(request: web.Request) -> web.Response:
    monitor_csv: Path = request.app["monitor_csv"]
    try:
        status = read_latest_status(monitor_csv)
    except (ValueError, FileNotFoundError) as err:
        return web.Response(status=404, text=str(err))
    return web.json_response(status)


async def _on_shutdown(app: web.Application):
    for pc in list(_active_connections):
        await pc.close()
    _active_connections.clear()


def run(
    storage_root: Path,
    n_cameras: int,
    static_dir: Path,
    cert_path: Path,
    key_path: Path,
    events_file: Path,
    monitor_csv: Path,
    host: str = "0.0.0.0",
    port: int = 8443,
):
    storage_root.mkdir(parents=True, exist_ok=True)

    app = web.Application()
    app["storage_root"] = storage_root
    app["n_cameras"] = n_cameras
    app["events_file"] = events_file
    app["monitor_csv"] = monitor_csv
    app.router.add_post("/offer/{camera_id}", _handle_offer)
    app.router.add_post("/events", _handle_event)
    app.router.add_get("/files-list", _handle_files_list)
    app.router.add_get("/monitor-status", _handle_monitor_status)
    app.router.add_static("/files/", path=str(storage_root), name="files", show_index=True)
    app.router.add_static("/", path=str(static_dir), name="static")
    app.on_shutdown.append(_on_shutdown)

    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))

    print(f"[webrtc] listening on https://{host}:{port}, storage={storage_root}")
    web.run_app(app, host=host, port=port, ssl_context=ssl_context)
