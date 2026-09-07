"""bot.py — Telegram bot: thu thập input, đẩy job lên Kaggle, gửi video về.

Chạy:
    python -m telegram_bot.bot

Luồng: 2 ảnh (A/B) → tên A → tên B → giới thiệu A → giới thiệu B → chọn giọng
→ bot push notebook lên Kaggle (GPU + vieneu), poll, tải mp4, gửi cho user.
"""
import asyncio
import json
import uuid
from pathlib import Path

from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from telegram_bot import kaggle_client
from telegram_bot.config import (
    BOT_TOKEN,
    DRY_RUN,
    JOB_SERVER_PUBLIC_URL,
    JOB_TOKEN,
    JOBS_DIR,
    REPO_URL,
    VOICE_OPTIONS,
)

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)


class Job(StatesGroup):
    photo_a = State()
    photo_b = State()
    name_a = State()
    name_b = State()
    intro_a = State()
    intro_b = State()
    note = State()
    product_name = State()
    voice = State()


def _kb_voices() -> InlineKeyboardMarkup:
    rows = []
    for v in VOICE_OPTIONS:
        rows.append([InlineKeyboardButton(text=v, callback_data=f"voice:{v}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ============================== /start, /cancel ==============================

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(Job.photo_a)
    await message.answer(
        "Chào bạn! Bot sẽ tự sinh video so sánh A/B trên Kaggle.\n\n"
        "1️⃣ Gửi ảnh sản phẩm <b>A</b> <i>(ảnh đầu tiên)</i>"
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Đã hủy. Gõ /start để làm lại.")


# ============================== thu thập input ==============================

@router.message(Job.photo_a, F.photo)
async def on_photo_a(message: Message, state: FSMContext):
    await state.update_data(photo_a=message.photo[-1].file_id)
    await state.set_state(Job.photo_b)
    await message.answer("✅ Ảnh A xong. 2️⃣ Bây giờ gửi ảnh sản phẩm <b>B</b>.")


@router.message(Job.photo_a)
async def on_photo_a_bad(message: Message):
    await message.answer("Gửi <b>ảnh</b> sản phẩm A nhé (dạng ảnh, không phải file).")


@router.message(Job.photo_b, F.photo)
async def on_photo_b(message: Message, state: FSMContext):
    await state.update_data(photo_b=message.photo[-1].file_id)
    await state.set_state(Job.name_a)
    await message.answer("✅ Ảnh B xong. 3️⃣ Nhập <b>tên sản phẩm A</b> (vd: SH 350)")


@router.message(Job.photo_b)
async def on_photo_b_bad(message: Message):
    await message.answer("Gửi <b>ảnh</b> sản phẩm B nhé.")


@router.message(Job.name_a)
async def on_name_a(message: Message, state: FSMContext):
    await state.update_data(name_a=message.text.strip())
    await state.set_state(Job.name_b)
    await message.answer("✅ Tên A: xong. 4️⃣ Nhập <b>tên sản phẩm B</b> (vd: PG-1)")


@router.message(Job.name_b)
async def on_name_b(message: Message, state: FSMContext):
    await state.update_data(name_b=message.text.strip())
    await state.set_state(Job.intro_a)
    await message.answer("✅ Tên B: xong. 5️⃣ Nhập <b>giới thiệu vật A</b> (1–2 câu ngắn).\n"
                         "Ví dụ: xe ga tay lái cao, 150cc, xịn nhưng giá chát.")


@router.message(Job.intro_a)
async def on_intro_a(message: Message, state: FSMContext):
    await state.update_data(intro_a=message.text.strip())
    await state.set_state(Job.intro_b)
    await message.answer("✅ Giới thiệu A: xong. 6️⃣ Nhập <b>giới thiệu vật B</b> (1–2 câu ngắn).")


@router.message(Job.intro_b)
async def on_intro_b(message: Message, state: FSMContext):
    await state.update_data(intro_b=message.text.strip())
    await state.set_state(Job.note)
    await message.answer(
        "✅ Giới thiệu B xong. 7️⃣ (Tuỳ chọn) Nhập <b>chú ý/lưu ý</b> cho AI nội dung.\n"
        "Vd: nhấn mạnh giá, chê bai hàng nhái, thêm châm biếm về thương hiệu...\n"
        "Gõ <code>-</code> nếu không cần.")


@router.message(Job.note)
async def on_note(message: Message, state: FSMContext):
    note = "" if message.text.strip() == "-" else message.text.strip()
    await state.update_data(note=note)
    await state.set_state(Job.product_name)
    await message.answer(
        "✅ Chú ý xong. Nhập <b>tên sản phẩm</b> bạn muốn giới thiệu ở cuối video "
        "(sách, khoá học, app... hoặc gõ <code>-</code> nếu không cần)."
    )


@router.message(Job.product_name)
async def on_product_name(message: Message, state: FSMContext):
    product_name = "" if message.text.strip() == "-" else message.text.strip()
    await state.update_data(product_name=product_name)
    await state.set_state(Job.voice)
    await message.answer("✅ Tên sản phẩm xong. 8️⃣ Chọn <b>giọng đọc</b> (VieNeu-TTS):",
                         reply_markup=_kb_voices())


@router.callback_query(Job.voice)
async def on_voice(cb: CallbackQuery, state: FSMContext):
    voice = cb.data.split(":", 1)[1]
    data = await state.get_data()
    await state.clear()
    await cb.message.edit_text(f"⏳ Đang tạo video giọng <b>{voice}</b>… Render ~5–10 phút.")
    job_id = await _launch_job(cb.message, data, voice)
    if DRY_RUN:
        return
    asyncio.create_task(_finish_job(cb.message.bot, cb.message.chat.id, job_id))


# ============================== chạy job ==============================

async def _launch_job(message: Message, data: dict, voice: str) -> str:
    job_id = uuid.uuid4().hex[:8]
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    run_id = f"tg_{job_id}"
    meta = {
        "run_id": run_id,
        "name_a": data["name_a"], "name_b": data["name_b"],
        "intro_a": data["intro_a"], "intro_b": data["intro_b"],
        "note": data.get("note", ""),
        "product_name": data.get("product_name", ""),
        "voice": voice,
    }
    (job_dir / "metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8"
    )

    async def _save_photo(file_id: str, name: str):
        f = await bot.get_file(file_id)
        await bot.download(f, destination=job_dir / name)

    await _save_photo(data["photo_a"], "image_a.jpg")
    await _save_photo(data["photo_b"], "image_b.jpg")

    if not DRY_RUN:
        await kaggle_client.push_notebook(
            _build_notebook(job_id)
        )
    return job_id


def _build_notebook(job_id: str) -> dict:
    nb = json.loads((Path(__file__).parent
                     / "kaggle_job_template.ipynb").read_text(encoding="utf-8"))
    repl = {
        "@@REPO_URL@@": REPO_URL,
        "@@JOB_BASE_URL@@": JOB_SERVER_PUBLIC_URL,
        "@@RUN_ID@@": job_id,
        "@@JOB_TOKEN@@": JOB_TOKEN,
    }
    for cell in nb["cells"]:
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell["source"])
        for k, v in repl.items():
            source = source.replace(k, v)
        cell["source"] = [source]
    return nb


async def _finish_job(bot_: Bot, chat_id: int, job_id: str) -> None:
    job_dir = JOBS_DIR / job_id
    try:
        status = await kaggle_client.wait_until_complete()
        if status != "complete":
            await bot_.send_message(chat_id, f"❌ Kaggle render thất bại (status={status}).")
            return
        out_dir = await kaggle_client.download_output(job_dir)
        mp4s = sorted(out_dir.glob("*_final.mp4"))
        if not mp4s:
            await bot_.send_message(chat_id, "❌ Không thấy file video trong output Kaggle.")
            return
        await bot_.send_video(chat_id, FSInputFile(mp4s[0]), caption="Video so sánh A/B của bạn ✅")
    except Exception as e:
        await bot_.send_message(chat_id, f"⚠️ Lỗi: {e}")


async def main() -> None:
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())