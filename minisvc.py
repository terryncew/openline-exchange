#!/usr/bin/env python3
# stdlib microservice: GET /by-root/<hex>.json -> store/<hex>.json
from http.server import BaseHTTPRequestHandler, HTTPServer
import os, json, urllib.parse, pathlib

ROOT = pathlib.Path(__file__).resolve().parent
STORE = ROOT / "store"

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        p = urllib.parse.urlparse(self.path).path
        if p.startswith("/by-root/") and p.endswith(".json"):
            hexf = p.split("/by-root/")[1]
            f = STORE / hexf
            if f.is_file():
                j = json.dumps(json.loads(f.read_text()), separators=(",",":")).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.send_header("Content-Length", str(len(j)))
                self.end_headers()
                self.wfile.write(j); return
        self.send_response(404); self.end_headers()

def main():
    os.makedirs(STORE, exist_ok=True)
    port = int(os.environ.get("PORT","8080"))
    HTTPServer(("0.0.0.0", port), H).serve_forever()

if __name__ == "__main__":
    main()
