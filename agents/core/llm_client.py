import os
import json
import re
import sys
from typing import Optional, Generator
from openai import OpenAI
from dotenv import load_dotenv

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(project_root, ".env"))

_api_key = os.getenv("OPENAI_API_KEY") or ""

client = OpenAI(
    api_key=_api_key or "missing-api-key",
    base_url=os.getenv("OPENAI_API_BASE", "https://api.deepseek.com/v1"),
)

DEFAULT_MODEL = os.getenv("LLM_MODEL_NAME", "deepseek-chat")


def call_llm(
    prompt: str,
    system_prompt: str = "",
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_retries: int = 3,
) -> str:
    if not _api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            if attempt == max_retries - 1:
                raise RuntimeError(f"LLM调用失败（已重试{max_retries}次）: {e}") from e


def call_llm_stream(
    prompt: str,
    system_prompt: str = "",
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_retries: int = 3,
    on_token=None,
) -> str:
    if not _api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                stream=True,
            )
            
            full_content = ""
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    full_content += token
                    if on_token:
                        on_token(token)
            
            return full_content.strip()
        except Exception as e:
            if attempt == max_retries - 1:
                raise RuntimeError(f"LLM调用失败（已重试{max_retries}次）: {e}") from e


def extract_json_from_response(text: str) -> Optional[dict]:
    json_match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_match = re.search(r'json\{([\s\S]*?)\}', text)
        if json_match:
            json_str = "{" + json_match.group(1) + "}"
        else:
            brace_count = 0
            start = -1
            for i, char in enumerate(text):
                if char == "{":
                    if brace_count == 0:
                        start = i
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                    if brace_count == 0 and start != -1:
                        json_str = text[start:i+1]
                        break
            else:
                return None

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None
