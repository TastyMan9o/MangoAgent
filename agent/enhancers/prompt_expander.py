from agent.utils.templates import load_template
# agent/enhancers/prompt_expander.py (可控版)
# -*- coding: utf-8 -*-
import os
import re
import json
from copy import deepcopy
from typing import List, Dict, Any, Optional, Tuple, Set

import google.generativeai as genai
from agent.interactive.refiner import _read_json
from agent.registry.store import register_prompt
from agent.utils.io import write_json, ensure_dir

DEFAULT_IMMUTABLE_PATH_PREFIXES: Set[Tuple[str, ...]] = {
    ('meta',), ('veo_params', 'aspect_ratio'), ('veo_params', 'person_generation'),
    ('prompt', 'shots'), ('prompt', 'timing'), ('prompt', 'style'), ('prompt', 'lighting')
}
DEFAULT_ALLOWED_PATH_PREFIXES: Set[Tuple[str, ...]] = {
    ('prompt', 'concept'), ('prompt', 'actions'), ('prompt', 'constraints')
}
CURRENT_ALLOWED_PATH_PREFIXES: Set[Tuple[str, ...]] = set(DEFAULT_ALLOWED_PATH_PREFIXES)
CURRENT_IMMUTABLE_PATH_PREFIXES: Set[Tuple[str, ...]] = set(DEFAULT_IMMUTABLE_PATH_PREFIXES)

def _init_gemini():
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key: raise ValueError("Please set GEMINI_API_KEY in environment.")
    genai.configure(api_key=gemini_key)
_init_gemini()

JSON_OBJ_FENCE = re.compile(r'\{.*\}', re.DOTALL)
def _extract_json_from_text(text: str) -> dict:
    text = text.strip()
    try: return json.loads(text)
    except Exception: pass
    m = JSON_OBJ_FENCE.search(text)
    if not m: raise ValueError("Model did not return a JSON object.")
    return json.loads(m.group(0))

def _collect_diffs(base: Any, new: Any, path: Tuple[str, ...] = ()) -> List[Tuple[str, Tuple[str, ...], Any]]:
    diffs = []
    if isinstance(base, dict) and isinstance(new, dict):
        base_keys, new_keys = set(base.keys()), set(new.keys())
        if base_keys != new_keys:
            diffs.append(('__KEYSET_CHANGED__', path, (base_keys, new_keys))); return diffs
        for k in base_keys:
            diffs.extend(_collect_diffs(base[k], new[k], path + (k,)))
    elif isinstance(base, list) and isinstance(new, list):
        if len(base) != len(new):
            diffs.append(('__LIST_LEN_CHANGED__', path, (len(base), len(new)))); return diffs
        for i, (bv, nv) in enumerate(zip(base, new)):
            diffs.extend(_collect_diffs(bv, nv, path + (str(i),)))
    elif base != new:
        diffs.append(('__VALUE_CHANGED__', path, (base, new)))
    return diffs

def _path_is_allowed(path: Tuple[str, ...]) -> bool:
    key_path = tuple(p for p in path if not p.isdigit())
    for imm in CURRENT_IMMUTABLE_PATH_PREFIXES:
        if len(key_path) >= len(imm) and key_path[:len(imm)] == imm:
            return False
    for allow in CURRENT_ALLOWED_PATH_PREFIXES:
        if len(key_path) >= len(allow) and key_path[:len(allow)] == allow:
            return True
    return False

def _gather_dynamic_policy(base_obj: dict) -> None:
    global CURRENT_ALLOWED_PATH_PREFIXES, CURRENT_IMMUTABLE_PATH_PREFIXES
    CURRENT_ALLOWED_PATH_PREFIXES = set(DEFAULT_ALLOWED_PATH_PREFIXES)
    CURRENT_IMMUTABLE_PATH_PREFIXES = set(DEFAULT_IMMUTABLE_PATH_PREFIXES)
    policy = base_obj.get('policy') or base_obj.get('_policy') or {}
    mutable = policy.get('mutable_paths') or []
    immutable = policy.get('immutable_paths') or []
    def to_tuple(path_str: str) -> Tuple[str, ...]:
        return tuple(seg.strip() for seg in path_str.split('.') if seg.strip())
    for p in mutable: CURRENT_ALLOWED_PATH_PREFIXES.add(to_tuple(p))
    for p in immutable: CURRENT_IMMUTABLE_PATH_PREFIXES.add(to_tuple(p))

def enforce_policy_or_raise(base_obj: dict, new_obj: dict, max_allowed_value_changes: int = 5) -> None:
    diffs = _collect_diffs(base_obj, new_obj)
    for kind, path, payload in diffs:
        if kind in ('__KEYSET_CHANGED__', '__LIST_LEN_CHANGED__'):
            raise ValueError(f"Structure violation: {kind} at {'.'.join(path)} → {payload}")
    value_changes = [d for d in diffs if d[0] == '__VALUE_CHANGED__']
    if len(value_changes) > max_allowed_value_changes:
        raise ValueError(f"Too many value changes: {len(value_changes)} > {max_allowed_value_changes}")
    for _, path, (old, new) in value_changes:
        if not _path_is_allowed(path):
            raise ValueError(f"Out-of-bounds change: {'.'.join(path)} from {old!r} to {new!r}")

def _construct_expansion_prompt(base_prompt_str: str, user_hint: Optional[str] = None) -> str:
    hint_block = f'USER_HINT: "{user_hint}"' if user_hint else "USER_HINT: (none)"
    # 生成允许和不允许修改的路径列表，供模型参考
    allowed_paths_str = ", ".join(".".join(p) for p in CURRENT_ALLOWED_PATH_PREFIXES)
    immutable_paths_str = ", ".join(".".join(p) for p in CURRENT_IMMUTABLE_PATH_PREFIXES)
    return load_template("prompt_expander_system.txt", hint_block=f\'USER_HINT: "{user_hint}"\' if user_hint else "USER_HINT: (none)", allowed_paths_str=", ".join(".".join(p) for p in CURRENT_ALLOWED_PATH_PREFIXES), immutable_paths_str=", ".join(".".join(p) for p in CURRENT_IMMUTABLE_PATH_PREFIXES), base_prompt_str=base_prompt_str)

def expand_prompt(prompt_path: str, num_expansions: int, user_hint: Optional[str] = None) -> List[Dict[str, Any]]:
    print(f"🚀 开始可控式创意扩展，基础Prompt: {prompt_path}, 数量: {num_expansions}")
    base_prompt_obj = _read_json(prompt_path)

    # 每次调用时都从基础Prompt中收集动态策略
    _gather_dynamic_policy(base_prompt_obj)

    model = genai.GenerativeModel('models/gemini-1.5-flash')
    generated_prompts = []

    for i in range(num_expansions):
        print(f"  - 正在生成第 {i+1}/{num_expansions} 个变体...")
        prompt_text = _construct_expansion_prompt(json.dumps(base_prompt_obj, ensure_ascii=False, indent=2), user_hint)

        try:
            response = model.generate_content(prompt_text) # 移除了response_mime_type，让模型自由生成
            new_prompt_obj_raw = _extract_json_from_text(response.text)

            # 创建一个副本用于检查，避免修改原始基础对象
            base_copy = deepcopy(base_prompt_obj)
            enforce_policy_or_raise(base_copy, new_prompt_obj_raw)

            original_name_stem = re.sub(r'_v\d+$', '', base_prompt_obj.get("name", "untitled"))
            new_name = f"{original_name_stem}_expanded_{i+1}"
            new_prompt_obj_raw["name"] = new_name

            save_path = os.path.join("prompts", "generated", f"{new_name}.json")
            ensure_dir(os.path.dirname(save_path))
            write_json(save_path, new_prompt_obj_raw)
            register_prompt(new_prompt_obj_raw, save_path, status="ready")

            generated_prompts.append({
                "saved_path": save_path,
                "prompt_content": new_prompt_obj_raw
            })
            print(f"  - ✅ 已保存变体 (通过策略检查): {save_path}")

        except Exception as e:
            print(f"  - ❌ 第 {i+1} 个变体生成失败或未通过策略检查: {e}")
            continue

    return generated_prompts