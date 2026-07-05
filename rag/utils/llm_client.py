import hashlib
import os
import time
import uuid

import requests
from dotenv import load_dotenv

load_dotenv()


# ─── 蓝心鉴权工具函数 ──────────────────────────────────────
def _gen_vivo_headers(app_id: str, app_key: str) -> dict:
    """生成蓝心API所需的签名请求头"""
    timestamp = str(int(time.time() * 1000))  # 毫秒时间戳
    nonce = str(uuid.uuid4())  # 随机唯一字符串

    # 签名字符串：app_id + app_key + timestamp + nonce
    sign_str = f"{app_id}{app_key}{timestamp}{nonce}"
    signature = hashlib.md5(sign_str.encode("utf-8")).hexdigest()

    return {
        "app-id": app_id,
        "timestamp": timestamp,
        "nonce": nonce,
        "signature": signature,
        "Content-Type": "application/json"
    }


# ─── 通用调用函数 ───────────────────────────────────────────
def call_llm(user_prompt: str, system_prompt: str = "你是一个教育助手") -> str:
    """
    调用大模型，返回模型回复的文字内容。

    参数：
        user_prompt: 用户输入的内容
        system_prompt: 系统提示词，控制模型角色和行为
    返回：
        模型回复的字符串
    """
    base_url = os.environ.get("LLM_BASE_URL", "")
    model = os.environ.get("LLM_MODEL", "vivo-BlueLM-TB")
    app_id = os.environ.get("LLM_APP_ID", "")
    app_key = os.environ.get("LLM_APP_KEY", "")

    if not base_url:
        raise ValueError("缺少 LLM_BASE_URL 环境变量，请检查 .env 文件")

    # 构建请求体（OpenAI Chat格式）
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.3,  # 低温度 = 输出更稳定，生成JSON时推荐
        "max_tokens": 2000
    }

    # 根据是否有 APP_ID 判断用哪种鉴权
    if app_id and app_key:
        # 蓝心签名鉴权
        headers = _gen_vivo_headers(app_id, app_key)
    else:
        # 通用 Bearer Token 鉴权（用于 DeepSeek、智谱等）
        api_key = os.environ.get("LLM_API_KEY", "")
        if not api_key:
            raise ValueError("缺少 LLM_API_KEY 或 LLM_APP_ID，请检查 .env 文件")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    try:
        response = requests.post(base_url, headers=headers, json=body, timeout=60)
        response.raise_for_status()  # HTTP错误直接抛出
        result = response.json()
        return result["choices"][0]["message"]["content"]

    except requests.exceptions.Timeout:
        raise RuntimeError("API请求超时（60s），请检查网络或换个模型")
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"API返回HTTP错误 {e.response.status_code}：{e.response.text}")
    except (KeyError, IndexError):
        raise RuntimeError(f"模型返回格式异常，完整响应：{result}")


# ─── 快速测试入口 ──────────────────────────────────────────
if __name__ == "__main__":
    print("测试 call_llm ...")
    reply = call_llm("用一句话解释什么是Python")
    print("模型回复：", reply)