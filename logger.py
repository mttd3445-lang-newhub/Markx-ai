"""logger.py — ตั้งค่า logging แบบ rotation ลงไฟล์ + console"""
import logging
import os
from logging.handlers import RotatingFileHandler

from config import LOG_LEVEL, LOG_FILE, LOG_MAX_BYTES, LOG_BACKUP_COUNT


def setup_logger(name: str = "z-bot") -> logging.Logger:
    """สร้าง logger ที่เขียนทั้ง console และไฟล์ (rotate)"""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    if LOG_FILE:
        log_dir = os.path.dirname(LOG_FILE) or "."
        os.makedirs(log_dir, exist_ok=True)
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)

    return logger