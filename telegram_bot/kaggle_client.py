"""kaggle_client.py — điều khiển Kaggle qua HTTP API (không cần CLI).

Chịu trách nhiệm: push notebook (=> Kaggle tự chạy), poll trạng thái, tải
output về. Xác thực bằng HTTP Basic với Kaggle username + API key.
"""
import asyncio
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
        "newTitle": KAGGLE_SLUG,
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
        if body.get("error"):
            raise RuntimeError(f"Kaggle push từ chối: {body['error']}")


async def get_status() -> str:
    async with httpx.AsyncClient(auth=_auth(), timeout=30) as client:
        r = await client.get(
            f"{KAGGLE_API}/kernels/status",
            params={"userName": KAGGLE_OWNER, "kernelSlug": KAGGLE_SLUG},
        )
    if r.status_code == 404:
        return "no_run"
    r.raise_for_status()
    return r.json().get("status", "unknown")


async def download_output(dest: Path, retries: int = 5, retry_delay: int = 15) -> Path:
    """Tải output của kernel về dest.

    Kaggle API /kernels/output trả 1 JSON có field "files", mỗi phần tử gồm
    {"fileName": "...", "url": "https://..."}. Tìm file "*_final.mp4", rồi GET
    thẳng vào "url" (đã ký sẵn token) để tải nội dung file thật.
    """
    extract_dir = dest / "out"
    extract_dir.mkdir(parents=True, exist_ok=True)
    last_error = None

    for attempt in range(1, retries + 1):
        async with httpx.AsyncClient(auth=_auth(), timeout=300) as client:
            r = await client.get(
                f"{KAGGLE_API}/kernels/output",
                params={"userName": KAGGLE_OWNER, "kernelSlug": KAGGLE_SLUG},
            )
            r.raise_for_status()
            data = r.json()

        files = data.get("files") or []
        mp4_entry = next(
            (f for f in files if (f.get("fileName") or "").endswith("_final.mp4")),
            None,
        )

        if mp4_entry is None:
            last_error = (
                f"Lần {attempt}: chưa thấy file *_final.mp4 trong output "
                f"({len(files)} file có sẵn: {[f.get('fileName') for f in files][:10]})"
            )
            await asyncio.sleep(retry_delay)
            continue

        file_name = Path(mp4_entry["fileName"]).name
        file_url = mp4_entry["url"]

        async with httpx.AsyncClient(timeout=300) as client:
            fr = await client.get(file_url)
            fr.raise_for_status()

        mp4_path = extract_dir / file_name
        mp4_path.write_bytes(fr.content)
        return extract_dir

    raise RuntimeError(f"Tải output Kaggle thất bại sau {retries} lần thử. Lỗi cuối: {last_error}")


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