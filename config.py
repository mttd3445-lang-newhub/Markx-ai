"""config.py — ตั้งค่าทุกอย่างของบอท (อ่านจาก .env)"""
import os
from dotenv import load_dotenv

load_dotenv()


def _parse_int_list(s: str):
    return [int(x.strip()) for x in s.split(",") if x.strip().isdigit()]


# ---------- Discord ----------
DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")
COMMAND_PREFIX: str = os.getenv("COMMAND_PREFIX", "!")
USE_SLASH_COMMANDS: bool = os.getenv("USE_SLASH_COMMANDS", "true").lower() == "true"
OWNER_IDS = _parse_int_list(os.getenv("OWNER_IDS", ""))

# ---------- Z.ai API ----------
ZAI_API_KEY: str = os.getenv("ZAI_API_KEY", "")
ZAI_BASE_URL: str = os.getenv("ZAI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
ZAI_MODEL: str = os.getenv("ZAI_MODEL", "glm-4-plus")
ZAI_IMAGE_MODEL: str = os.getenv("ZAI_IMAGE_MODEL", "cogview-3-plus")

# ---------- Conversation ----------
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "30"))
AI_TIMEOUT_SEC = int(os.getenv("AI_TIMEOUT_SEC", "60"))
AI_MAX_RETRIES = int(os.getenv("AI_MAX_RETRIES", "2"))
AI_TEMPERATURE = float(os.getenv("AI_TEMPERATURE", "0.7"))

# ---------- Auto-respond ----------
AUTO_RESPOND_CHANNEL_IDS = _parse_int_list(os.getenv("AUTO_RESPOND_CHANNEL_IDS", ""))

# ---------- File attachments ----------
ALLOWED_FILE_EXTENSIONS = [
    ext.strip().lower()
    for ext in os.getenv(
        "ALLOWED_FILE_EXTENSIONS",
        ".py,.js,.ts,.tsx,.jsx,.txt,.md,.json,.csv,.tsv,.html,.css,"
        ".java,.cpp,.c,.h,.go,.rs,.rb,.php,.sh,.sql,.yml,.yaml,.xml,.env"
    ).split(",")
    if ext.strip()
]
MAX_FILE_SIZE_KB = int(os.getenv("MAX_FILE_SIZE_KB", "100"))

# ---------- Logging ----------
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE: str = os.getenv("LOG_FILE", "logs/bot.log")
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))

# ---------- Health check ----------
HEALTH_CHECK_ENABLED = os.getenv("HEALTH_CHECK_ENABLED", "true").lower() == "true"
HEALTH_CHECK_PORT = int(os.getenv("HEALTH_CHECK_PORT") or os.getenv("PORT", "8080"))

# ---------- Stats ----------
STATS_ENABLED = os.getenv("STATS_ENABLED", "true").lower() == "true"

# ---------- Persona ----------
DEFAULT_PERSONA: str = os.getenv("DEFAULT_PERSONA", "friendly")

# ---------- ข้อความสำเร็จ / แจ้งเตือน ----------
MSG_THINKING: str = "🤔 กำลังคิดอยู่ รอแป๊บนะครับ..."
MSG_ERROR: str = "❌ ขอโทษครับ เกิดข้อผิดพลาดในการเรียก AI ลองใหม่อีกครั้งนะครับ"
MSG_CLEARED: str = "🧹 ล้างประวัติการสนทนาในห้องนี้เรียบร้อยแล้วครับ!"
MSG_PONG: str = "🏓 ปิง! บอทออนไลน์อยู่ครับ"
MSG_NO_TOKEN: str = (
    "❌ ยังไม่พบ DISCORD_TOKEN — กรุณาสร้างไฟล์ .env จาก .env.example "
    "แล้วใส่ token ของบอทก่อนรัน"
)
MSG_NO_ZAI_KEY: str = (
    "❌ ยังไม่พบ ZAI_API_KEY — ขอ API key จาก https://open.bigmodel.cn/ "
    "แล้วใส่ใน .env ก่อนรัน"
)