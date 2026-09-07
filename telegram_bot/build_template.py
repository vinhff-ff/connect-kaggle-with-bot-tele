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

import numpy as _np_live
print('numpy LIVE trong kernel chính (dùng cho pipeline/LLM/ffmpeg):', _np_live.__version__)

TTS_VENV = '/kaggle/working/tts_env'
MARKER = f'{TTS_VENV}/.setup_ok'

if os.path.exists(TTS_VENV) and not os.path.exists(MARKER):
    import shutil
    print('tts_env dở dang từ lần trước, xóa và tạo lại...')
    shutil.rmtree(TTS_VENV)

if not os.path.exists(TTS_VENV):
    ret = os.system(f'python3 -m venv --without-pip {TTS_VENV}')
    if ret != 0:
        raise SystemExit('Tạo venv tts_env THẤT BẠI.')

    ret = os.system('curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py')
    if ret != 0:
        raise SystemExit('Tải get-pip.py THẤT BẠI (kiểm tra mạng/DNS).')

    ret = os.system(f'{TTS_VENV}/bin/python3 /tmp/get-pip.py --no-warn-script-location')
    if ret != 0:
        raise SystemExit('Cài pip vào tts_env bằng get-pip.py THẤT BẠI.')

    PIP = f'{TTS_VENV}/bin/pip'

    ret = os.system(f'{PIP} install -q "torch==2.5.1" --index-url https://download.pytorch.org/whl/cu121')
    if ret != 0:
        raise SystemExit('Cài torch cho tts_env THẤT BẠI.')

    ret = os.system(f'{PIP} install -q --no-deps vieneu')
    if ret != 0:
        raise SystemExit('Cài vieneu (--no-deps) cho tts_env THẤT BẠI.')

    ret = os.system(
        f'{PIP} install -q "numpy<2.3" scipy transformers safetensors '
        f'gradio huggingface_hub kaldi-native-fbank librosa onnxruntime '
        f'PyYAML sea-g2p soundfile soxr tokenizers'
    )
    if ret != 0:
        raise SystemExit('Cài dependency còn lại cho tts_env THẤT BẠI.')

    open(MARKER, 'w').close()
    print('tts_env cài đặt xong, đã đánh dấu marker.')
else:
    print('tts_env đã cài đặt sẵn (marker OK), bỏ qua bước cài.')

check = os.popen(
    f'{TTS_VENV}/bin/python -c "import torch; print(torch.__version__, torch.cuda.get_device_capability(0) if torch.cuda.is_available() else \'NO GPU\')"'
).read()
print('tts_env torch check:', check.strip())

ret = os.system('pip install -q --no-input edge-tts playwright huggingface-hub ddgs ffmpeg-python')
if ret != 0:
    raise SystemExit('pip install pipeline deps THẤT BẠI.')

os.system('python -m playwright install chromium')
os.system('apt-get update -qq && apt-get install -y -qq libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libxcb1 libxext6 libasound2 libnss3 libnspr4 libatspi2.0-0 libcairo2 libpango-1.0-0 libx11-xcb1 > /dev/null')
os.system('pip install -q --no-input --force-reinstall --no-cache-dir llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124')

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
    product_name=meta.get('product_name', ''),
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