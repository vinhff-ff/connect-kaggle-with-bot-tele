"""job_server.py — HTTP phục vụ ảnh/params job cho notebook Kaggle tải về.

Chạy:
    python -m telegram_bot.job_server

Endpoint:
    GET /jobs/{job_id}/{filename}?token=JOB_TOKEN
Trả về file trong telegram_bot/jobs/{job_id}/. Token bắt buộc để Kaggle không
thể tải job của nhau.
"""
import hmac
from pathlib import Path

from aiohttp import web

from telegram_bot.config import JOB_SERVER_PORT, JOB_TOKEN, JOBS_DIR

ROUTES = web.RouteTableDef()


def _authorized(request: web.Request) -> bool:
    token = request.query.get("token", "")
    return bool(JOB_TOKEN) and hmac.compare_digest(token, JOB_TOKEN)


@ROUTES.get("/jobs/{job_id}/{filename:.*}")
async def serve_job_file(request: web.Request) -> web.StreamResponse:
    if not _authorized(request):
        raise web.HTTPUnauthorized()

    job_id = request.match_info["job_id"]
    filename = request.match_info["filename"]
    if Path(job_id).name != job_id or "/" in job_id or ".." in filename:
        raise web.HTTPBadRequest()
    path = (JOBS_DIR / job_id / filename).resolve()
    if not path.is_relative_to(JOBS_DIR.resolve()) or not path.is_file():
        raise web.HTTPNotFound(text=f"File {filename} không tồn tại.")
    return web.FileResponse(path)


@ROUTES.get("/healthz")
async def healthz(request: web.Request) -> web.Response:
    return web.json_response({"ok": True})


def main() -> None:
    app = web.Application()
    app.add_routes(ROUTES)
    web.run_app(app, host="0.0.0.0", port=JOB_SERVER_PORT)


if __name__ == "__main__":
    main()