"""health.py — HTTP health check สำหรับ uptime monitoring + stats"""
import json
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

from config import HEALTH_CHECK_PORT, HEALTH_CHECK_ENABLED
from logger import setup_logger

log = setup_logger("health")


class HealthHandler(BaseHTTPRequestHandler):
    bot_status = {
        "started_at": time.time(),
        "last_message_at": None,
        "messages_processed": 0,
        "ai_calls": 0,
        "ai_errors": 0,
        "guilds": 0,
        "users": 0,
        "persona_default": "friendly",
    }

    def do_GET(self):
        if self.path == "/health" or self.path == "/":
            uptime = int(time.time() - self.bot_status["started_at"])
            self._respond(200, {
                "status": "ok",
                "uptime_sec": uptime,
                "uptime_human": _human_time(uptime),
            })
        elif self.path == "/status":
            self._respond(200, self.bot_status)
        else:
            self._respond(404, {"error": "not found", "path": self.path})

    def _respond(self, code, data):
        body = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def _human_time(sec):
    d, sec = divmod(sec, 86400)
    h, sec = divmod(sec, 3600)
    m, sec = divmod(sec, 60)
    if d:
        return f"{d}d {h}h {m}m"
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {sec}s"
    return f"{sec}s"


def start_health_server():
    """เปิด HTTP server ใน background thread"""
    if not HEALTH_CHECK_ENABLED:
        return None
    try:
        server = HTTPServer(("0.0.0.0", HEALTH_CHECK_PORT), HealthHandler)
        threading.Thread(
            target=server.serve_forever, daemon=True, name="health-server"
        ).start()
        log.info("🏥 Health check: http://0.0.0.0:%d/health", HEALTH_CHECK_PORT)
        return server
    except Exception as e:
        log.warning("เปิด health server ไม่ได้: %s", e)
        return None


def update_status(**kwargs):
    """อัปเดตสถานะบอท"""
    HealthHandler.bot_status.update(kwargs)