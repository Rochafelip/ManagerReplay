import argparse
import sys
from pathlib import Path

# Allow running this file directly (e.g. `python3 spikes/spike2/spike2_server.py`)
# by putting the package root (the directory containing `spikes/`) on sys.path —
# direct script execution only adds this file's own directory otherwise.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def parse_args():
    parser = argparse.ArgumentParser(description="ManagerReplay Spike 2 test server")
    parser.add_argument("--mode", choices=["chunks", "webrtc"], required=True)
    parser.add_argument("--cameras", type=int, choices=[1, 2], required=True)
    parser.add_argument("--cert", required=True, help="Path to mkcert-generated cert file")
    parser.add_argument("--key", required=True, help="Path to mkcert-generated key file")
    parser.add_argument("--storage-root", default="~/highlightbox-spike2")
    parser.add_argument("--static-dir", default=str(Path(__file__).parent / "static"))
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8443)
    return parser.parse_args()


def main():
    args = parse_args()
    storage_root = Path(args.storage_root).expanduser()
    static_dir = Path(args.static_dir).expanduser()
    cert_path = Path(args.cert).expanduser()
    key_path = Path(args.key).expanduser()

    if args.mode == "chunks":
        from spikes.spike2 import chunks_receiver as receiver
    else:
        from spikes.spike2 import webrtc_receiver as receiver

    receiver.run(
        storage_root=storage_root,
        n_cameras=args.cameras,
        static_dir=static_dir,
        cert_path=cert_path,
        key_path=key_path,
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    main()
