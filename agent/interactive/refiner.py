# agent/interactive/refiner.py (最终稳定版)
# -*- coding: utf-8 -*-
import os, json, re, copy
from datetime import datetime
from typing import Tuple, Dict, Any, List
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import ValidationError
from agent.prompt.schema_json import VideoPromptJSON
from agent.utils.io import write_json, ensure_dir
from agent.registry.store import register_prompt

load_dotenv()


def deepseek_client() -> OpenAI:
    key = os.getenv("DEEPSEEK_API_KEY")
    if not key: raise RuntimeError("缺少 DEEPSEEK_API_KEY")
    return OpenAI(api_key=key, base_url="https://api.deepseek.com")


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _version_bump_name(base_name: str) -> str:
    m = re.search(r"(.*)_v(\d+)$", base_name)
    if not m: return base_name + "_v2"
    prefix, n = m.group(1), int(m.group(2))
    return f"{prefix}_v{n + 1}"


def _json_diff(old: Dict[str, Any], new: Dict[str, Any], path="$") -> List[str]:
    diffs = []
    if type(old) != type(new): diffs.append(f"{path}: type {type(old).__name__} -> {type(new).__name__}"); return diffs
    if isinstance(old, dict):
        keys = set(old) | set(new)
        for k in sorted(keys):
            p = f"{path}.{k}"
            if k not in old:
                diffs.append(f"{p}: <added>")
            elif k not in new:
                diffs.append(f"{p}: <removed>")
            else:
                diffs.extend(_json_diff(old[k], new[k], p))
    elif isinstance(old, list):
        if len(old) != len(new): diffs.append(f"{path}: list len {len(old)} -> {len(new)}")
    elif old != new:
        diffs.append(f"{path}: '{old}' -> '{new}'")
    return diffs


def _overlay_allowed(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(old)
    if "veo_params" in new and isinstance(new["veo_params"], dict):
        out.setdefault("veo_params", {})
        for k in ["aspect_ratio", "person_generation", "negative_prompt"]:
            if k in new["veo_params"]: out["veo_params"][k] = new["veo_params"][k]
    if "prompt" in new and isinstance(new["prompt"], dict):
        out.setdefault("prompt", {})
        for k in ["concept", "shots", "actions", "lighting", "style", "audio", "timing", "constraints"]:
            if k in new["prompt"]: out["prompt"][k] = new["prompt"][k]
    return out


REFINE_SYSTEM = "你是严格的“视觉域 JSON 提示词改写器”。只允许更新这些字段：veo_params.{aspect_ratio,person_generation,negative_prompt}；prompt.{concept,shots,actions,lighting,style,audio,timing,constraints}。禁止添加/修改与封面(thumbnail)、标题(title)、互动(engagement)、描述(description)有关的任何内容。最终必须输出严格 JSON（英文）。"
REFINE_USER_TMPL = '''CURRENT_PROMPT_JSON:\n{current_json}\n\nUSER_FEEDBACK (may be CN/EN; keep only VISUAL changes):\n{feedback}\n\nRULES:\n- Update ONLY visual fields listed in system instruction.\n- Ignore any packaging/thumbnail/title/engagement suggestions.\n- Keep schema valid; keep other fields identical.\n- Return JSON object ONLY (no explanation).'''


def refine_prompt_json(base_json_path: str, user_feedback: str, model: str = "deepseek-chat") -> Tuple[
    Dict[str, Any], Dict[str, Any], List[str]]:
    old_obj = _read_json(base_json_path)
    _ = VideoPromptJSON(**old_obj)
    client = deepseek_client()
    user_msg = REFINE_USER_TMPL.format(current_json=json.dumps(old_obj, ensure_ascii=False, indent=2),
                                       feedback=user_feedback)
    resp = client.chat.completions.create(model=model, messages=[{"role": "system", "content": REFINE_SYSTEM},
                                                                 {"role": "user", "content": user_msg}],
                                          temperature=0.2, response_format={"type": "json_object"})
    content = resp.choices[0].message.content.strip()
    try:
        new_obj = json.loads(content)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"返回不是合法 JSON：\\n{content}") from e
    filtered_obj = _overlay_allowed(old_obj, new_obj)
    try:
        _ = VideoPromptJSON(**filtered_obj)
    except ValidationError as e:
        raise RuntimeError(f"改写后的 JSON 不符合 schema：{e}")
    diffs = _json_diff(old_obj, filtered_obj, "$")
    return old_obj, filtered_obj, diffs


def save_refined_version(new_json: Dict[str, Any], base_json_path: str) -> str:
    name = new_json.get("name") or "未命名_v1"
    new_name = _version_bump_name(name)
    new_json["name"] = new_name

    if "meta" in new_json and isinstance(new_json["meta"], dict):
        new_json["meta"]["created_at"] = _now_iso()
        base_name = os.path.splitext(os.path.basename(base_json_path))[0]
        new_json["meta"]["parent_prompt_id"] = base_name

    out_path = os.path.join("prompts", "generated", f"{new_name}.json")
    ensure_dir(os.path.dirname(out_path))
    write_json(out_path, new_json)
    return out_path