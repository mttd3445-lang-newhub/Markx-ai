"""attachments.py — ตัวอ่านไฟล์แนบใน Discord"""
import os
from typing import List

import discord

from config import ALLOWED_FILE_EXTENSIONS, MAX_FILE_SIZE_KB
from logger import setup_logger

log = setup_logger("attachments")


async def read_attachments(message: discord.Message) -> tuple[List[dict], List[str]]:
    """อ่านไฟล์แนบจาก message คืน (file_contents, skipped_files)"""
    if not message.attachments:
        return [], []

    file_contents = []
    skipped = []

    for att in message.attachments:
        name = att.filename.lower()
        ext = os.path.splitext(name)[1]

        if ext not in ALLOWED_FILE_EXTENSIONS:
            skipped.append(f"{att.filename} (นามสกุล {ext or 'ไม่มี'} ไม่รองรับ)")
            continue

        size_kb = att.size / 1024
        if size_kb > MAX_FILE_SIZE_KB:
            skipped.append(
                f"{att.filename} (ขนาด {size_kb:.1f}KB เกิน {MAX_FILE_SIZE_KB}KB)"
            )
            continue

        try:
            file_bytes = await att.read()
            try:
                file_text = file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                file_text = file_bytes.decode("latin-1", errors="replace")

            if len(file_text) > 10000:
                file_text = file_text[:10000] + "\n\n... [ไฟล์ถูกตัดเพราะยาวเกิน 10,000 ตัวอักษร]"

            lang = ext.lstrip(".")
            file_contents.append({
                "filename": att.filename,
                "language": lang,
                "content": file_text,
                "size_kb": round(size_kb, 1),
            })
            log.info("อ่านไฟล์แนบ: %s (%.1fKB)", att.filename, size_kb)
        except Exception as e:
            log.error("อ่านไฟล์แนบ %s ไม่ได้: %s", att.filename, e)
            skipped.append(f"{att.filename} (อ่านไม่ได้: {e})")

    return file_contents, skipped


def format_files_for_prompt(file_contents: List[dict]) -> str:
    """รวมไฟล์หลายไฟล์เป็นข้อความเดียวสำหรับส่งให้ AI"""
    parts = []
    for f in file_contents:
        parts.append(
            f"📎 **ไฟล์ `{f['filename']}`** ({f['size_kb']}KB)\n"
            f"```{f['language']}\n{f['content']}\n```"
        )
    return "\n\n".join(parts)