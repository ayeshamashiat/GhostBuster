"""Local web demo:  python -m petnihunter.app   ->  http://127.0.0.1:8780
POST /api/ask {"q": "..."} -> {"raw": <base model answer>, "guard": <PetniHunter result>}
Uses only the standard library for serving. Binds to localhost only."""
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from petnihunter import answer
from petnihunter.llm import complete, translate

HERE = os.path.dirname(__file__)
POOL = ThreadPoolExecutor(4)
MAX_Q = 300


# --- abuse protection: the Tinker key costs real money, so cap usage per IP and per day ---
LIMIT_IP = int(os.environ.get("LIMIT_PER_IP_HOUR", 30))
LIMIT_DAY = int(os.environ.get("LIMIT_PER_DAY", 400))
_hits = {}
_day = {"d": None, "n": 0}
_lk = threading.Lock()


def allowed(ip):
    import time
    now = time.time()
    with _lk:
        today = time.strftime("%Y-%m-%d")
        if _day["d"] != today:
            _day.update(d=today, n=0)
        recent = [t for t in _hits.get(ip, []) if now - t < 3600]
        if len(recent) >= LIMIT_IP or _day["n"] >= LIMIT_DAY:
            _hits[ip] = recent
            return False
        recent.append(now)
        _hits[ip] = recent
        _day["n"] += 1
        return True


def ask(q):
    raw_f = POOL.submit(lambda: complete(q, max_tokens=200))
    guard_f = POOL.submit(answer, q)
    raw_en = ""
    try:
        raw = raw_f.result(90)
        try:
            raw_en = translate(raw)
        except Exception:
            raw_en = ""
    except Exception as e:
        raw = f"[মডেল উত্তর দেয়নি: {type(e).__name__}]"
    try:
        guard = guard_f.result(90)
    except Exception as e:
        guard = {"action": "error", "text": f"যাচাই করা যায়নি: {type(e).__name__}"}
    return {"raw": raw, "raw_en": raw_en, "guard": guard}


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            with open(os.path.join(HERE, "static", "index.html"), "rb") as f:
                self._send(200, f.read(), "text/html; charset=utf-8")
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if self.path != "/api/ask":
            return self._send(404, b"not found", "text/plain")
        try:
            n = min(int(self.headers.get("Content-Length", 0)), 4096)
            q = json.loads(self.rfile.read(n)).get("q", "").strip()[:MAX_Q]
        except Exception:
            return self._send(400, b'{"error":"bad request"}', "application/json")
        if not q:
            return self._send(400, b'{"error":"empty question"}', "application/json")
        ip = self.headers.get("X-Forwarded-For", self.client_address[0]).split(",")[0].strip()
        if not allowed(ip):
            return self._send(429, b'{"error":"rate limit reached, try again later"}', "application/json")
        self._send(200, json.dumps(ask(q), ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8780))
    # Hosts like Render set PORT and need 0.0.0.0; local runs stay on localhost unless HOST says otherwise.
    host = os.environ.get("HOST") or ("0.0.0.0" if os.environ.get("PORT") else "127.0.0.1")
    print(f"PetniHunter demo on http://{host}:{port}", flush=True)
    ThreadingHTTPServer((host, port), H).serve_forever()
