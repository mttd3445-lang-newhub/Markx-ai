"""ai_client.py — เรียก Z.ai API พร้อม JWT auth + รองรับ image generation"""
import base64
import hashlib
import hmac
import json
import time
import urllib.request
import urllib.error
from typing import List, Dict

from config import (
    ZAI_API_KEY, ZAI_BASE_URL, ZAI_MODEL, ZAI_IMAGE_MODEL,
    AI_TIMEOUT_SEC, AI_MAX_RETRIES, AI_TEMPERATURE,
)


class AIClientError(Exception):
    pass


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _generate_zhipu_jwt(api_key: str) -> str:
    """แปลง Z.ai API key (id.secret) เป็น JWT token"""
    if "." not in api_key:
        return api_key
    try:
        api_id, api_secret = api_key.split(".", 1)
    except ValueError:
        return api_key

    header = {"alg": "HS256", "sign_type": "SIGN"}
    now = int(time.time())
    payload = {"api_key": api_id, "exp": now + 3600, "timestamp": now}

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}"
    sig = hmac.new(
        api_secret.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    sig_b64 = _b64url_encode(sig)
    return f"{header_b64}.{payload_b64}.{sig_b64}"


class AIClient:
    """Client สำหรับเรียก Z.ai GLM API (chat + image)"""

    def __init__(self, api_key=ZAI_API_KEY, base_url=ZAI_BASE_URL, model=ZAI_MODEL):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

        if not self.api_key:
            raise AIClientError("ไม่พบ ZAI_API_KEY")

    def _auth_token(self) -> str:
        return _generate_zhipu_jwt(self.api_key)

    def _post(self, endpoint: str, payload: dict, timeout: int = AI_TIMEOUT_SEC) -> dict:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self._auth_token()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def chat(self, messages: List[Dict[str, str]]) -> str:
        """เรียก chat completion → คืนเนื้อหาคำตอบ"""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": AI_TEMPERATURE,
            "top_p": 0.9,
        }

        last_error = None
        for attempt in range(1, AI_MAX_RETRIES + 1):
            try:
                data = self._post("chat/completions", payload)
                choices = data.get("choices") or []
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                    if content:
                        return content
                if "error" in data:
                    err = data["error"]
                    msg = err.get("message") if isinstance(err, dict) else str(err)
                    raise AIClientError(f"API error: {msg}")
                raise AIClientError("การตอบกลับจาก Z.ai ว่างเปล่า")

            except urllib.error.HTTPError as e:
                err_body = ""
                try:
                    err_body = e.read().decode("utf-8", errors="replace")
                    err_data = json.loads(err_body)
                    err_msg = err_data.get("error", {}).get("message", err_body)
                except (json.JSONDecodeError, Exception):
                    err_msg = err_body or str(e)
                last_error = AIClientError(f"HTTP {e.code}: {err_msg[:300]}")

            except urllib.error.URLError as e:
                last_error = AIClientError(f"network: {e.reason}")

            except TimeoutError:
                last_error = AIClientError(f"timeout {AI_TIMEOUT_SEC}s")

            except AIClientError as e:
                last_error = e

            if attempt < AI_MAX_RETRIES:
                time.sleep(1 * attempt)

        raise last_error or AIClientError("ไม่สามารถเรียก Z.ai ได้")

    def generate_image(self, prompt: str) -> str:
        """เรียก image generation API → คืน URL รูป"""
        payload = {"model": ZAI_IMAGE_MODEL, "prompt": prompt}
        try:
            data = self._post("images/generations", payload, timeout=180)
            images = data.get("data") or []
            if images:
                url = images[0].get("url", "")
                if url:
                    return url
            raise AIClientError("ไม่ได้รับ URL รูปกลับมา")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")[:300]
            raise AIClientError(f"image HTTP {e.code}: {err_body}")