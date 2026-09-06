"""job_server.py — HTTP phục vụ ảnh/params job cho notebook Kaggle tải về.

Chạy:
    python -m telegram_bot.job_server

Endpoint:
    GET /jobs/{job_id}/{filename}?token=JOB_TOKEN
        Trả về file trong telegram_bot/jobs/{job_id}/. Token bắt buộc để Kaggle
        không thể tải job của nhau.
    GET /assets/{filename}?token=JOB_TOKEN
        Trả về asset tĩnh (background, character, ...) lưu sẵn trên VPS trong
        telegram_bot/assets/.
"""
import hmac
from pathlib import Path

from aiohttp import web

from telegram_bot.config import ASSETS_DIR, JOB_SERVER_PORT, JOB_TOKEN, JOBS_DIR

ROUTES = web.RouteTableDef()


def _authorized(request: web.Request) -> bool:
    token = request.query.get("token", "")
    return bool(JOB_TOKEN) and hmac.compare_digest(token, JOB_TOKEN)


def _serve_file(path: Path, root: Path) -> web.StreamResponse:
    path = path.resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise web.HTTPNotFound(text=f"File {path.name} không tồn tại.")
    return web.FileResponse(path)


@ROUTES.get("/jobs/{job_id}/{filename:.*}")
async def serve_job_file(request: web.Request) -> web.StreamResponse:
    if not _authorized(request):
        raise web.HTTPUnauthorized()

    job_id = request.match_info["job_id"]
    filename = request.match_info["filename"]
    if Path(job_id).name != job_id or "/" in job_id or ".." in filename:
        raise web.HTTPBadRequest()
    return _serve_file(JOBS_DIR / job_id / filename, JOBS_DIR)


@ROUTES.get("/assets/{filename}")
async def serve_asset(request: web.Request) -> web.StreamResponse:
    if not _authorized(request):
        raise web.HTTPUnauthorized()

    filename = request.match_info["filename"]
    if Path(filename).name != filename or "/" in filename or ".." in filename:
        raise web.HTTPBadRequest()
    return _serve_file(ASSETS_DIR / filename, ASSETS_DIR)


@ROUTES.get("/healthz")
async def healthz(request: web.Request) -> web.Response:
    return web.json_response({"ok": True})


def main() -> None:
    app = web.Application()
    app.add_routes(ROUTES)
    web.run_app(app, host="0.0.0.0", port=JOB_SERVER_PORT)


if __name__ == "__main__":
    main()