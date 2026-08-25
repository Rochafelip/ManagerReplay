"""Minimal HTTP redirect server for Wi-Fi captive-portal auto-open.

Listens on port 80 and answers every request with a 302 redirect to the
ManagerReplay app. Phones connecting to the hotspot probe well-known URLs
(e.g. /generate_204, /hotspot-detect.html, /connecttest.txt) expecting a
204/200 response; getting a redirect instead is what makes Android/iOS/
Windows pop up a browser automatically pointed at TARGET_URL.
"""
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

TARGET_URL = os.environ.get("MANAGERREPLAY_CAPTIVE_TARGET", "https://10.42.0.1:8443")


class RedirectHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(302)
        self.send_header("Location", TARGET_URL)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format, *args):
        pass


def main():
    HTTPServer(("0.0.0.0", 80), RedirectHandler).serve_forever()


if __name__ == "__main__":
    main()
