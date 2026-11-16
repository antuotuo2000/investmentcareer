#!/usr/bin/env python3
"""Serve the portal and discover local Components reports without dependencies."""
import hashlib
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
import webbrowser
from build_snapshot import build_snapshot

DOCS = Path(__file__).resolve().parent / "docs"


def catalog():
    entries = []
    for path in sorted((DOCS / "Components").iterdir(), key=lambda p: p.name.casefold()):
        if path.is_file() and not path.is_symlink() and path.suffix.lower() in (".html", ".htm"):
            stat = path.stat()
            entries.append({"fileName": path.name, "modified": stat.st_mtime_ns,
                            "lastModified": stat.st_mtime * 1000, "size": stat.st_size})
    return entries


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DOCS), **kwargs)

    def do_GET(self):
        if urlsplit(self.path).path == "/components-index.json":
            try:
                data = json.dumps(catalog(), ensure_ascii=False).encode("utf-8")
            except OSError:
                self.send_error(503, "Components directory is unavailable")
                return
            tag = '"' + hashlib.sha256(data).hexdigest() + '"'
            if self.headers.get("If-None-Match") == tag:
                self.send_response(304)
                self.send_header("ETag", tag)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")
            self.send_header("ETag", tag)
            self.end_headers()
            self.wfile.write(data)
            return
        super().do_GET()

    def end_headers(self):
        if urlsplit(self.path).path != "/components-index.json":
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()


def main():
    build_snapshot()
    try:
        server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    except OSError as error:
        raise SystemExit("无法启动本地服务（8765 端口可能已被使用）：" + str(error))
    url = "http://127.0.0.1:8765/"
    print("财报主页：" + url + "\n新增 HTML 请放入：" + str(DOCS / "Components") + "\n保持此窗口开启，按 Ctrl+C 停止。", flush=True)
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
