"""Local development SMTP sink. Never relays mail; listen on loopback only."""

import os
from datetime import UTC, datetime
from email import policy
from email.parser import BytesParser
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from socketserver import StreamRequestHandler, ThreadingTCPServer
from threading import Thread
from uuid import uuid4

MAIL = Path(
    os.environ.get(
        "MEMORA_MAIL_DIR", str(Path(__file__).resolve().parents[1] / ".memora/mail")
    )
).resolve()
SMTP_PORT = int(os.environ.get("MEMORA_SMTP_PORT", "1025"))
INBOX_PORT = int(os.environ.get("MEMORA_INBOX_PORT", "8025"))
MAIL.mkdir(parents=True, exist_ok=True)


class SMTP(StreamRequestHandler):
    def handle(self):
        self.request.settimeout(30)
        self.wfile.write(b"220 Memora local capture\r\n")
        while line := self.rfile.readline(65537):
            if len(line) > 65536:
                break
            command = line.split(b" ", 1)[0].strip().upper()
            if command == b"DATA":
                self.wfile.write(b"354 End with dot\r\n")
                data = bytearray()
                while line := self.rfile.readline(65537):
                    if line == b".\r\n":
                        break
                    data.extend(line[1:] if line.startswith(b"..") else line)
                    if len(data) > 10 * 1024 * 1024:
                        return
                (
                    MAIL / f"{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid4().hex}.eml"
                ).write_bytes(data)
                self.wfile.write(b"250 Captured locally\r\n")
            elif command == b"QUIT":
                self.wfile.write(b"221 Bye\r\n")
                return
            elif command in (b"EHLO", b"HELO", b"MAIL", b"RCPT", b"RSET", b"NOOP"):
                self.wfile.write(b"250 OK\r\n")
            else:
                self.wfile.write(b"502 Unsupported\r\n")


class Inbox(BaseHTTPRequestHandler):
    def do_GET(self):
        cards = []
        for path in sorted(MAIL.glob("*.eml"), reverse=True):
            msg = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
            body = (
                msg.get_body(preferencelist=("html", "plain"))
                if msg.is_multipart()
                else msg
            )
            text = body.get_content() if body else ""
            cards.append(
                f"<article><h2>{escape(str(msg['Subject']))}</h2><p>To: {escape(str(msg['To']))}</p><pre>{escape(str(text))}</pre></article>"
            )
        page = (
            '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Memora — capture email locale</title><style>body{font:16px system-ui;max-width:960px;margin:40px auto;padding:16px}article{border:1px solid #ddd;border-radius:12px;padding:20px;margin:20px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><h1>Emails capturés localement</h1><p>Aucun envoi externe. Actualisez pour lire les nouveaux messages.</p>'
            + "".join(cards)
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(page)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(page)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    ThreadingTCPServer.allow_reuse_address = True
    smtp = ThreadingTCPServer(("127.0.0.1", SMTP_PORT), SMTP)
    Thread(target=smtp.serve_forever, daemon=True).start()
    print(
        f"Local SMTP 127.0.0.1:{SMTP_PORT}; inbox http://127.0.0.1:{INBOX_PORT}",
        flush=True,
    )
    ThreadingHTTPServer(("127.0.0.1", INBOX_PORT), Inbox).serve_forever()
