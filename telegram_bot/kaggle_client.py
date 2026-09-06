"""kaggle_client.py — điều khiển Kaggle qua HTTP API (không cần CLI).

Chịu trách nhiệm: push notebook (=> Kaggle tự chạy), poll trạng thái, tải
output zip về. Xác thực bằng HTTP Basic với Kaggle username + API key.
"""
import base64
import json
import time
from pathlib import Path

import httpx

from telegram_bot.config import KAGGLE_KEY, KAGGLE_OWNER, KAGGLE_SLUG, KAGGLE_USERNAME

KAGGLE_API = "https://www.kaggle.com/api/v1"
POLL_INTERVAL_S = 30
MAX_WAIT_S = 40 * 60  # 40 phút tối đa


def _auth() -> httpx.BasicAuth:
    return httpx.BasicAuth(KAGGLE_USERNAME, KAGGLE_KEY)


async def push_notebook(notebook: dict) -> None:
    """Tạo/mở notebook trên Kaggle (bật GPU + internet) => bắt đầu chạy."""
    payload = {
        "newTitle": "AI-Video-Job",
        "slug": f"{KAGGLE_OWNER}/{KAGGLE_SLUG}",
        "oldTitle": None,
        "language": "python",
        "kernelType": "notebook",
        "isPrivate": True,
        "enableGpu": True,
        "enableInternet": True,
        "datasetDataSources": [],
        "competitionDataSources": [],
        "text": json.dumps(notebook),
    }
    async with httpx.AsyncClient(auth=_auth(), timeout=60) as client:
        r = await client.post(f"{KAGGLE_API}/kernels/push", json=payload)
        body = r.json()
        if r.status_code >= 400:
            raise RuntimeError(
                f"Kaggle push thất bại ({r.status_code}): "
                f"{body.get('message') or r.text}"
            )
        # API mới trả HTTP 200 kèm error (vd invalid slug/trùng title).
        if body.get("error"):
            raise RuntimeError(f"Kaggle push từ chối: {body['error']}")


async def get_status() -> str:
    async with httpx.AsyncClient(auth=_auth(), timeout=30) as client:
        r = await client.get(
            f"{KAGGLE_API}/kernels/status",
            params={"userName": KAGGLE_OWNER, "kernelSlug": KAGGLE_SLUG},
        )
    if r.status_code == 404:
        # Chưa có run nào (hoặc push chưa kịp đăng ký) → chờ tiếp.
        return "no_run"
    r.raise_for_status()
    return r.json().get("status", "unknown")


async def download_output(dest: Path) -> Path:
    """Tải output zip của kernel về dest rồi giải nén. Trả về thư mục đã giải nén."""
    zip_path = dest / f"{KAGGLE_SLUG}.zip"
    async with httpx.AsyncClient(auth=_auth(), timeout=300) as client:
        r = await client.get(
            f"{KAGGLE_API}/kernels/output",
            params={"userName": KAGGLE_OWNER, "kernelSlug": KAGGLE_SLUG},
        )
        r.raise_for_status()
    zip_path.write_bytes(r.content)
    import zipfile

    extract_dir = dest / "out"
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_dir)
    return extract_dir


async def wait_until_complete(callback=None) -> str:
    """Poll tới khi kernel 'complete' hoặc 'error'. callback(status) nếu cần báo."""
    waited = 0
    while waited < MAX_WAIT_S:
        status = await get_status()
        if callback:
            await callback(status)
        if status in ("complete", "error"):
            return status
        time.sleep(POLL_INTERVAL_S)
        waited += POLL_INTERVAL_S
    raise TimeoutError("Kaggle render quá lâu (>40 phút).")