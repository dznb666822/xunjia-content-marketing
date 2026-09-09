# -*- coding: utf-8 -*-
"""CosyVoice 本地 TTS 服务（供智能混剪配音调用）

- /list_spks            返回预置音色列表
- /inference_sft        用预置音色合成语音，返回 WAV
- /inference_zero_shot  用参考音频零样本克隆音色后合成，返回 WAV
"""
import os
import sys
import io
import wave
import logging
import tempfile

logging.getLogger('matplotlib').setLevel(logging.WARNING)

from fastapi import FastAPI, Form, UploadFile, File
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(ROOT_DIR)
sys.path.append(os.path.join(ROOT_DIR, 'third_party', 'Matcha-TTS'))

from cosyvoice.cli.cosyvoice import AutoModel  # noqa: E402

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

cosyvoice = None


def _pcm_to_wav(pcm: bytes, sample_rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # int16
        w.setframerate(int(sample_rate))
        w.writeframes(pcm)
    return buf.getvalue()


def _collect_pcm(model_output) -> bytes:
    chunks = []
    for item in model_output:
        speech = item['tts_speech']
        if hasattr(speech, 'numpy'):
            speech = speech.numpy()
        chunks.append((speech * (2 ** 15)).astype('int16').tobytes())
    return b''.join(chunks)


@app.get('/list_spks')
async def list_spks():
    return {
        'sample_rate': cosyvoice.sample_rate,
        'spks': cosyvoice.list_available_spks(),
    }


@app.get('/inference_sft')
@app.post('/inference_sft')
async def inference_sft(
    tts_text: str = Form(...),
    spk_id: str = Form(...),
    speed: float = Form(1.0),
):
    model_output = cosyvoice.inference_sft(tts_text, spk_id, speed=speed)
    wav = _pcm_to_wav(_collect_pcm(model_output), cosyvoice.sample_rate)
    return Response(content=wav, media_type='audio/wav')


@app.get('/inference_zero_shot')
@app.post('/inference_zero_shot')
async def inference_zero_shot(
    tts_text: str = Form(...),
    prompt_text: str = Form(...),
    speed: float = Form(1.0),
    prompt_wav: UploadFile = File(...),
):
    # 参考音频保存为临时文件；inference_zero_shot 内部需要按路径多次读取
    suffix = os.path.splitext(prompt_wav.filename or '')[-1] or '.wav'
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(prompt_wav.file.read())
            tmp_path = tmp.name
        model_output = cosyvoice.inference_zero_shot(
            tts_text, prompt_text, tmp_path, speed=speed
        )
        wav = _pcm_to_wav(_collect_pcm(model_output), cosyvoice.sample_rate)
        return Response(content=wav, media_type='audio/wav')
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=50000)
    parser.add_argument('--model_dir', type=str,
                        default=os.path.join(ROOT_DIR, 'pretrained_models', 'CosyVoice-300M-SFT'))
    args = parser.parse_args()
    cosyvoice = AutoModel(model_dir=args.model_dir)
    uvicorn.run(app, host='0.0.0.0', port=args.port)
