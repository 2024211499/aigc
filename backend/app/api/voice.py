# -*- coding: utf-8 -*-
"""语音识别与合成接口"""
import os
import logging
import tempfile
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, Depends
from pydantic import BaseModel

from ..core.config import settings
from ..core.exceptions import NotFoundError

logger = logging.getLogger(__name__)
router = APIRouter()


class RerankRequest(BaseModel):
    query: str
    sentences: List[str]


@router.post("/text/rerank", summary="文本相似度排序")
def text_rerank(req: RerankRequest):
    """用 bge-reranker-large 计算 query 与各候选项的相似度，返回排序结果。"""
    from ..services.vivo_rerank import VivoReranker
    try:
        reranker = VivoReranker()
        results = reranker.rerank(req.query, req.sentences)
        return {"success": True, "results": [{"text": r[0], "score": r[1]} for r in results]}
    except Exception as e:
        logger.error("Rerank 失败: %s", e)
        return {"success": False, "error": str(e)}


class ImageGenRequest(BaseModel):
    prompt: str
    model: str = "Doubao-Seedream-5.0-lite"
    image: Optional[str] = None
    size: str = "1024x1024"
    num_images: int = 1


@router.post("/image/generate", summary="图片生成")
def image_generate(req: ImageGenRequest):
    """通过 vivo Doubao Seedream 模型生成图片。

    每天限制 50 次，总计 500 次。
    文生图：传 prompt
    图生图：传 prompt + image（URL 或 base64）
    """
    from ..services.vivo_image_gen import VivoImageGen
    try:
        gen = VivoImageGen()
        urls = gen.generate(
            prompt=req.prompt,
            model=req.model,
            image=req.image,
            size=req.size,
            num_images=req.num_images,
        )
        return {"success": True, "images": urls}
    except Exception as e:
        logger.error("图片生成失败: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}


@router.post("/voice/asr", summary="短语音识别（<60s）")
async def short_asr(
    audio: UploadFile = File(...),
    audio_format: str = Form("wav"),
):
    """上传一段短音频（<60s），返回识别文字。

    支持格式：wav, pcm, m4a, mp3, aac, ogg
    建议：WAV 16kHz 16bit 单声道
    """
    from ..services.vivo_asr import VivoShortASR

    audio_data = await audio.read()
    if not audio_data:
        return {"success": False, "error": "空音频"}

    try:
        # 如果是 WAV 格式，提取 PCM 数据
        if audio_format == "wav" or audio.filename.endswith(".wav"):
            import wave
            import io
            with wave.open(io.BytesIO(audio_data), "rb") as wf:
                if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getframerate() != 16000:
                    # 需要重采样或转格式，先简单尝试直接用
                    pcm_data = audio_data
                else:
                    pcm_data = wf.readframes(wf.getnframes())
        else:
            pcm_data = audio_data

        asr = VivoShortASR()
        text = asr.transcribe(pcm_data)
        return {"success": True, "text": text}
    except Exception as e:
        logger.error("语音识别失败: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}


@router.post("/voice/long-asr", summary="长语音转写（文件）")
async def long_asr(
    audio: UploadFile = File(...),
):
    """上传一个录音文件（最长 5 小时，<500MB），返回转写文字。

    支持格式：wav, pcm, m4a, mp3, aac, ogg, ogg_opus
    """
    from ..services.vivo_long_asr import VivoLongASR

    # 保存到临时文件
    suffix = Path(audio.filename or "audio.wav").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await audio.read())
        tmp_path = tmp.name

    try:
        asr = VivoLongASR()
        text = asr.transcribe_file(tmp_path)
        return {"success": True, "text": text}
    except Exception as e:
        logger.error("长语音转写失败: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


class SimilarityRequest(BaseModel):
    text_a: str
    text_b: str


@router.post("/text/similarity", summary="文本相似度计算")
def text_similarity(req: SimilarityRequest):
    """计算两段文本的语义相似度（0~1）。"""
    from ..services.text_similarity import compute_similarity
    score = compute_similarity(req.text_a, req.text_b)
    return {"success": True, "similarity": score}


class VideoGenRequest(BaseModel):
    prompt: str
    model: str = "Doubao-Seedance-2.0-fast"
    image_url: Optional[str] = None
    last_frame_url: Optional[str] = None
    ratio: str = "16:9"
    duration: int = 5
    wait: bool = True


@router.post("/video/generate", summary="视频生成（Doubao Seedance）")
def video_generate(req: VideoGenRequest):
    """生成视频。支持文生视频、图生视频（首帧/首尾帧）。

    每日限制 10 次，总计 200 个视频。
    模型可选：Doubao-Seedance-1.0-pro / 2.0 / 2.0-fast
    """
    from ..services.vivo_video_gen import VivoVideoGen
    try:
        gen = VivoVideoGen()
        result = gen.generate(
            prompt=req.prompt,
            model=req.model,
            image_url=req.image_url,
            last_frame_url=req.last_frame_url,
            ratio=req.ratio,
            duration=req.duration,
            poll=req.wait,
        )
        return {"success": True, **result}
    except Exception as e:
        logger.error("视频生成失败: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}


class VideoQueryRequest(BaseModel):
    task_id: str


@router.post("/video/query", summary="查询视频生成任务")
def video_query(req: VideoQueryRequest):
    """根据 task_id 查询视频生成进度和结果。"""
    from ..services.vivo_video_gen import VivoVideoGen
    try:
        gen = VivoVideoGen()
        result = gen.query_task(req.task_id)
        return {"success": True, **result}
    except Exception as e:
        return {"success": False, "error": str(e)}


class TranslateRequest(BaseModel):
    audio_format: str = "wav"
    target_lang: str = "en_cn"
    source_lang: str = "cn"


@router.post("/voice/translate", summary="同声传译（语音翻译）")
async def voice_translate(
    audio: UploadFile = File(...),
    audio_format: str = Form("wav"),
    source_lang: str = Form("cn"),
    target_lang: str = Form("en_cn"),
):
    """上传一段音频，进行同声传译。

    支持语种：cn（中文）、en（英文）、ja（日文）、ko（韩文）
    翻译方向：en_cn（英译中）、ja_cn（日译中）、ko_cn（韩译中）
    """
    from ..services.vivo_translate import VivoSimultaneousInterpreter

    audio_data = await audio.read()
    if not audio_data:
        return {"success": False, "error": "空音频"}

    try:
        # 提取 PCM
        if audio_format == "wav":
            import wave
            import io
            with wave.open(io.BytesIO(audio_data), "rb") as wf:
                if wf.getnchannels() == 1 and wf.getsampwidth() == 2:
                    pcm_data = wf.readframes(wf.getnframes())
                else:
                    pcm_data = audio_data
        else:
            pcm_data = audio_data

        interpreter = VivoSimultaneousInterpreter()
        text = interpreter.translate(
            pcm_data,
            target_lang=target_lang,
            source_lang=source_lang,
        )
        return {"success": True, "source_lang": source_lang, "target_lang": target_lang, "text": text}
    except Exception as e:
        logger.error("同声传译失败: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}
