import argparse
import sys
from pathlib import Path

# Allow running this file directly (e.g. `python3 server/app.py`) by putting
# the repo root (the directory containing `server/`) on sys.path — direct
# script execution only adds this file's own directory otherwise.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def parse_args():
    parser = argparse.ArgumentParser(description="ManagerReplay server")
    parser.add_argument("--mode", choices=["chunks", "webrtc"], required=True)
    parser.add_argument("--cameras", type=int, choices=[1, 2, 3, 4, 5], required=True)
    parser.add_argument("--cert", required=True, help="Path to mkcert-generated cert file")
    parser.add_argument("--key", required=True, help="Path to mkcert-generated key file")
    parser.add_argument("--storage-root", default="~/managerreplay/data/recordings")
    parser.add_argument("--events-file", default="~/managerreplay/data/events.jsonl")
    parser.add_argument("--admin-password-file", default="~/managerreplay/admin-password.txt")
    parser.add_argument("--version-file", default="~/managerreplay/VERSION")
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
    events_file = Path(args.events_file).expanduser()

    run_kwargs = dict(
        storage_root=storage_root,
        n_cameras=args.cameras,
        static_dir=static_dir,
        cert_path=cert_path,
        key_path=key_path,
        events_file=events_file,
        host=args.host,
        port=args.port,
    )

    if args.mode == "chunks":
        from server import chunks_receiver as receiver
        run_kwargs["admin_password_file"] = Path(args.admin_password_file).expanduser()
        run_kwargs["version_file"] = Path(args.version_file).expanduser()
    else:
        from server import webrtc_receiver as receiver

    receiver.run(**run_kwargs)


if __name__ == "__main__":
    main()
