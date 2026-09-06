"""Config: đọc biến môi trường từ .env, cung cấp hằng số toàn cục."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(Path(__file__).resolve().parent / ".env")
load_dotenv(BASE_DIR / ".env")


def _required(name: str) -> str:
    val = os.getenv(name, "").strip()
    if not val:
        raise SystemExit(f"Thiếu biến môi trường bắt buộc: {name} (xem telegram_bot/env.example)")
    return val


BOT_TOKEN = _required("BOT_TOKEN")
KAGGLE_USERNAME = _required("KAGGLE_USERNAME")
KAGGLE_KEY = _required("KAGGLE_KEY")
KAGGLE_OWNER = _required("KAGGLE_OWNER").strip().lower()
KAGGLE_SLUG = _required("KAGGLE_KERNEL_SLUG").strip().lower()

JOB_SERVER_PUBLIC_URL = os.getenv("JOB_SERVER_PUBLIC_URL", "http://127.0.0.1:8787").rstrip("/")
JOB_SERVER_PORT = int(os.getenv("JOB_SERVER_PORT", "8787"))
JOB_TOKEN = os.getenv("JOB_TOKEN", "")
ASSET_DATASET = os.getenv("ASSET_DATASET", "")
REPO_URL = os.getenv("REPO_URL", "https://github.com/vinhff-ff/ai-video-comparison-tool.git")
DEFAULT_VOICE = os.getenv("DEFAULT_VOICE", "Adam")
DRY_RUN = os.getenv("DRY_RUN", "0") == "1"

BASE_DIR = Path(__file__).resolve().parent.parent
JOBS_DIR = BASE_DIR / "telegram_bot" / "jobs"

# Giọng cho user chọn (engine vieneu — subset phổ biến)
VOICE_OPTIONS = [
    "Adam",
    "Phạm Tuyên",
    "Minh Đức",
    "Lê Nguyên",
    "Trần Long",
]