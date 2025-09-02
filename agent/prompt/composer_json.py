# agent/prompt/composer_json.py (最终稳定版)
# -*- coding: utf-8 -*-
import os, json, re
from datetime import datetime
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import ValidationError
from agent.prompt.schema_json import VideoPromptJSON
from agent.utils.io import write_json, ensure_dir

load_dotenv()


def _ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M")


def ds_client() -> OpenAI:
    key = os.getenv("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError("缺少 DEEPSEEK_API_KEY")
    return OpenAI(api_key=key, base_url="https://api.deepseek.com")


SYSTEM_MSG = '''你是一个严格的 JSON 提示词生成器。
要求：
- 输出必须是一个合法的 JSON 对象，且完全符合给定的 JSON schema。
- 所有文本字段一律使用英文。
- 根据TOPIC合理补充必要的细节；保持安全、干净、无真人面孔。
'''
USER_TMPL = '''请基于以下输入，生成一个 VideoPromptJSON 对象（仅返回 JSON 本体）：
INPUT:
- TOPIC (English): {topic}
'''


def _ensure_defaults(obj: Dict[str, Any], topic: str, series: str, chinese_name: Optional[str] = None):
    obj.setdefault("meta", {})
    obj.setdefault("veo_params", {})
    obj.setdefault("prompt", {})

    file_stem = chinese_name or _ts()
    obj.setdefault("name", f"{file_stem}_v1")

    obj["meta"]["series"] = series
    obj["meta"]["topic"] = topic
    obj["meta"]["created_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    obj["meta"].setdefault("parent_prompt_id", None)

    vp = obj["veo_params"]
    pr = obj["prompt"]
    vp.setdefault("aspect_ratio", "16:9")
    vp.setdefault("person_generation", "dont_allow")
    vp.setdefault("negative_prompt", "cartoon, drawing, low quality, overexposure, blurry")
    pr.setdefault("concept", topic)
    pr.setdefault("shots", [])
    pr.setdefault("actions", [])
    pr.setdefault("lighting", "soft key light with gentle rim light")
    pr.setdefault("style", "photorealistic, macro, shallow depth of field")
    pr.setdefault("audio", "subtle ASMR, low ambient")
    pr.setdefault("timing", {"duration_seconds": 60.0, "beats": []})
    pr.setdefault("constraints", ["No human faces", "No text watermarks", "Avoid cartoon rendering"])


def _normalize_all(obj: Dict[str, Any], topic: str, series: str, source: str, chinese_name: Optional[str] = None):
    _ensure_defaults(obj, topic, series, chinese_name)
    obj.setdefault("meta", {})["source"] = source


def compose_v1_json(topic: str, series: str, defaults: Dict[str, Any], source: str = "hotspot",
                    model: str = "deepseek-chat", chinese_name: Optional[str] = None) -> Dict[str, Any]:
    client = ds_client()
    user_msg = USER_TMPL.format(topic=topic)

    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": SYSTEM_MSG}, {"role": "user", "content": user_msg}],
        temperature=0.2,
        response_format={"type": "json_object"}
    )
    content = (resp.choices[0].message.content or "").strip()

    try:
        obj = json.loads(content)
    except Exception as e:
        raise RuntimeError(f"模型未能正确返回JSON: {e}")

    # --- 新增：健壮性检查 ---
    # 如果模型返回的不是字典（比如只是一个字符串），则进行修正
    if not isinstance(obj, dict):
        print(f"⚠️ 警告: DeepSeek模型未返回JSON对象，而是返回了: {type(obj).__name__}。将基于此内容创建最小框架。")
        # 将模型返回的任何非字典内容作为核心 concept
        obj = {
            "prompt": {
                "concept": str(obj) if obj else topic
            }
        }
    # -------------------------

    _normalize_all(obj, topic=topic, series=series, source=source, chinese_name=chinese_name)

    try:
        _ = VideoPromptJSON(**obj)
    except ValidationError as e:
        raise RuntimeError(f"生成的 JSON 不符合 schema: {e}") from e
    return obj


def save_v1_json(obj: Dict[str, Any]) -> str:
    name = obj.get("name", "未命名_v1")
    path = os.path.join("prompts", "generated", f"{name}.json")
    ensure_dir(os.path.dirname(path))
    write_json(path, obj)
    return path