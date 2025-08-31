# agent/prompt/composer_json.py (文件名简化版)
# -*- coding: utf-8 -*-
import os, json, math, re
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
        raise RuntimeError("缺少 DEEPSEEK_API_KEY，请在 .env 中设置你的真实 Key。")
    return OpenAI(api_key=key, base_url="https://api.deepseek.com")

SYSTEM_MSG = '''你是一个严格的 JSON 提示词生成器。
要求：
- 输出必须是一个合法的 JSON 对象，且完全符合给定的 JSON schema（字段、类型）。
- 所有文本字段一律使用英文。
- 合理补充必要的细节；保持安全、干净、无真人面孔。
'''
USER_TMPL = '''请基于以下输入，生成一个 VideoPromptJSON 对象（仅返回 JSON 本体）：
INPUT:
- TOPIC (English): {topic}
DEFAULTS: {defaults}
'''

def _ensure_defaults(obj: Dict[str, Any], topic: str, series: str, chinese_name: Optional[str] = None):
    obj.setdefault("meta", {})
    obj.setdefault("veo_params", {})
    obj.setdefault("prompt", {})

    # --- 核心修改：简化 name 字段 ---
    file_stem = chinese_name or _ts()
    obj.setdefault("name", f"{file_stem}_v1")

    obj["meta"]["series"] = obj["meta"].get("series") or series
    obj["meta"]["topic"] = obj["meta"].get("topic") or topic
    obj["meta"]["created_at"] = obj["meta"].get("created_at") or datetime.now().astimezone().isoformat(timespec="seconds")
    obj["meta"].setdefault("parent_prompt_id", None)
    # ... (后续兜底逻辑不变) ...
    vp = obj["veo_params"]; pr = obj["prompt"]
    vp.setdefault("aspect_ratio", "16:9")
    vp.setdefault("person_generation", "dont_allow")
    vp.setdefault("negative_prompt", "cartoon, drawing, low quality, overexposure, blurry")
    pr.setdefault("concept", topic if isinstance(topic, str) else "Video concept")
    pr.setdefault("shots", []); pr.setdefault("actions", [])
    pr.setdefault("lighting", "soft key light with gentle rim light")
    pr.setdefault("style", "photorealistic, macro, shallow depth of field")
    pr.setdefault("audio", "subtle ASMR bubble pops, low ambient")
    pr.setdefault("timing", {"duration_seconds": 60.0, "beats": []})
    pr.setdefault("constraints", ["No human faces", "No text watermarks", "Avoid cartoon rendering"])

# ... (所有 _normalize_xxx 函数保持不变) ...
def _coerce_shot(x: Any, default_subject: str) -> Dict[str, Any]:
    if isinstance(x, dict):
        return {"camera": x.get("camera") or "macro close-up", "composition": x.get("composition") or "centered", "focal_subject": x.get("focal_subject") or default_subject, "movement_speed": x.get("movement_speed") or "slow"}
    txt = str(x).strip()
    return {"camera": txt or "macro close-up", "composition": "centered", "focal_subject": default_subject, "movement_speed": "slow"}
def _normalize_shots(obj: Dict[str, Any]):
    pr = obj.get("prompt", {}); shots = pr.get("shots", []); subject = pr.get("concept") or "subject"
    if not isinstance(shots, list): shots = []
    pr["shots"] = [_coerce_shot(x, subject) for x in shots]
def _normalize_beats(obj: Dict[str, Any]):
    pr = obj.get("prompt", {}); timing = pr.get("timing", {}); duration = float(timing.get("duration_seconds") or 60.0); beats = timing.get("beats", [])
    if not isinstance(beats, list): beats = []
    if all(isinstance(b, dict) and "start_sec" in b and "end_sec" in b and "description" in b for b in beats):
        timing["beats"] = [{"start_sec": round(float(b["start_sec"]),3), "end_sec": round(max(float(b["start_sec"]),float(b["end_sec"])),3), "description": str(b["description"])} for b in beats]
    else: timing["beats"] = []
def _normalize_all(obj: Dict[str, Any], topic: str, series: str, source: str, chinese_name: Optional[str] = None):
    _ensure_defaults(obj, topic, series, chinese_name)
    _normalize_shots(obj); _normalize_beats(obj)
    obj.setdefault("meta", {})["source"] = source

def compose_v1_json(topic: str, series: str, defaults: Dict[str, Any], source: str = "hotspot", model: str = "deepseek-chat", chinese_name: Optional[str] = None) -> Dict[str, Any]:
    client = ds_client()
    user_msg = USER_TMPL.format(topic=topic, defaults=json.dumps(defaults, ensure_ascii=False))
    resp = client.chat.completions.create(model=model, messages=[{"role": "system", "content": SYSTEM_MSG}, {"role": "user", "content": user_msg}], temperature=0.2, response_format={"type": "json_object"})
    content = re.sub(r"^```json\s*|\s*```$", "", resp.choices[0].message.content.strip(), flags=re.I).strip()
    try: obj = json.loads(content)
    except Exception as e: raise RuntimeError(f"模型未返回合法 JSON") from e
    _normalize_all(obj, topic=topic, series=series, source=source, chinese_name=chinese_name)
    try: _ = VideoPromptJSON(**obj)
    except ValidationError as e: raise RuntimeError(f"生成的 JSON 不符合 schema: {e}") from e
    return obj

def save_v1_json(obj: Dict[str, Any]) -> str:
    '''
落盘
v1
JSON，返回文件路径
'''
    name = obj.get("name", "未命名_v1")
    # --- 核心修改：简化存储路径 ---
    path = os.path.join("prompts", "generated", f"{name}.json")
    ensure_dir(os.path.dirname(path))
    write_json(path, obj)
    return path