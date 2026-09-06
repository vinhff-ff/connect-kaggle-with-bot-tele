"""Build notebook/kaggle_job_template.ipynb từ các cell code dưới đây.

Placeholder được thay lúc bot push (xem bot.py), giữ trong cell bằng "@@...@@".
Chạy: python -m telegram_bot.build_template
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "kaggle_job_template.ipynb"

SETUP = r'''
import os, glob, json
os.chdir('/kaggle/working')
REPO_URL = "@@REPO_URL@@"
if not os.path.exists('pipeline/.git'):
    os.system(f'git clone {REPO_URL} pipeline')
os.chdir('pipeline')
print("cwd:", os.getcwd())

# Pin numpy TRƯỚC khi cài vieneu/transformers.
# scipy (mà vieneu/transformers kéo theo) vẫn gọi numpy._core._multiarray_umath._blas_supports_fpe,
# nhưng numpy>=2.4 đã bỏ hàm này → ràng buộc numpy xuống 2.3.x để pip không tự nâng lên 2.4.
os.system('pip install -q --no-cache-dir "numpy>=2.2,<2.4"')

os.system('pip install -q --no-input edge-tts playwright huggingface-hub ddgs ffmpeg-python vieneu')
os.system('python -m playwright install chromium')
os.system('apt-get update -qq && apt-get install -y -qq libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libxcb1 libxext6 libasound2 libnss3 libnspr4 libatspi2.0-0 libcairo2 libpango-1.0-0 libx11-xcb1 > /dev/null')
os.system('pip install -q --no-input --force-reinstall --no-cache-dir llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124')

import numpy
print('numpy', numpy.__version__)
print('SETUP DONE')
'''

FETCH = r'''
import os, json
import httpx

BASE  = "@@JOB_BASE_URL@@"
RUN_ID = "@@RUN_ID@@"
TOKEN = {"token": "@@JOB_TOKEN@@"}
ASSETS = ["background.jpg", "character.png", "character_confused.png", "character_cart.png"]

os.chdir('/kaggle/working/pipeline')
assets_dir = 'assets'
os.makedirs(assets_dir, exist_ok=True)

cli = httpx.Client(timeout=120)
meta = cli.get(f'{BASE}/jobs/{RUN_ID}/metadata.json', params=TOKEN).json()
print('meta:', meta)

open(f'{assets_dir}/A.jpg', 'wb').write(cli.get(f'{BASE}/jobs/{RUN_ID}/image_a.jpg', params=TOKEN).content)
open(f'{assets_dir}/B.jpg', 'wb').write(cli.get(f'{BASE}/jobs/{RUN_ID}/image_b.jpg', params=TOKEN).content)

# Asset tĩnh (background + 3 nhân vật) được phục vụ ngay từ VPS qua job_server.
for name in ASSETS:
    open(os.path.join(assets_dir, name), 'wb').write(
        cli.get(f'{BASE}/assets/{name}', params=TOKEN).content)
print('ASSETS OK:', sorted(os.listdir(assets_dir)))
'''

RUN = r'''
# ==== Check sớm xung đột numpy/scipy ====
import numpy as np
import numpy._core._multiarray_umath as _mumath
if not hasattr(_mumath, '_blas_supports_fpe'):
    # scipy < 1.18 gọi _blas_supports_fpe lúc import; numpy>=2.4 đã bỏ.
    # Khat giúp pipeline chạy tiếp + cảnh báo để biết nguyên nhân.
    _mumath._blas_supports_fpe = lambda x: False
    print('[WARN] numpy thiếu _blas_supports_fpe — đã inject shim (scipy<1.18 + numpy>=2.4)')
try:
    import scipy
    import transformers
except Exception as e:
    raise SystemExit(f'ENV INCOMPATIBLE: {type(e).__name__}: {e}. '
                     'Chạy lại cell SETUP (pip install "numpy>=2.2,<2.4") rồi RESTART kernel.') from e
print('numpy', np.__version__, '| scipy', scipy.__version__, '| transformers', transformers.__version__)

import sys
sys.path.insert(0, 'src')
from pipeline import generate_video_phase3

assets = {
    'background': 'assets/background.jpg',
    'character':  'assets/character.png',
    'character_confused': 'assets/character_confused.png',
    'character_cart': 'assets/character_cart.png',
    'image_a':    'assets/A.jpg',
    'image_b':    'assets/B.jpg',
}

result = await generate_video_phase3(
    topic_a=meta['name_a'],
    topic_b=meta['name_b'],
    name_a=meta['name_a'],
    name_b=meta['name_b'],
    intro_a=meta['intro_a'],
    intro_b=meta['intro_b'],
    note=meta.get('note', ''),
    assets=assets,
    run_id=meta['run_id'],
    engine='vieneu',
    voice=meta['voice'],
    research=False,
)
print('RESULT:', result)
'''

OUTPUT = r'''
import os, shutil, glob
out_dir = '/kaggle/working/output'
os.makedirs(out_dir, exist_ok=True)
dst = os.path.join(out_dir, meta['run_id'] + '_final.mp4')
shutil.copy(result, dst)
for f in glob.glob(out_dir + '/*'):
    print('OUTFILE', f, os.path.getsize(f))
print('JOB_DONE')
'''


def main() -> None:
    cells = [
        {"cell_type": "markdown", "metadata": {}, "source": [
            "**AI Video Job** — render so sánh A/B trên Kaggle GPU (vieneu).\n"
        ]},
        {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": SETUP.splitlines(keepends=True)},
        {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": FETCH.splitlines(keepends=True)},
        {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": RUN.splitlines(keepends=True)},
        {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": OUTPUT.splitlines(keepends=True)},
    ]
    nb = {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    OUT.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
    print("Wrote", OUT)


if __name__ == "__main__":
    main()