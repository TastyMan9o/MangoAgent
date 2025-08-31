# -*- coding: utf-8 -*-
"""
agent/iterators/merge_policy.py
===========================================================
作用：
  把“改动建议（deltas）”应用到我们的英文 JSON Prompt（VideoPromptJSON）。
  这是最小可用版本：支持常见字段的“替换/追加/设置”。

设计要点：
  - 小步快跑：默认不大改，只针对点状字段修改
  - 冲突策略：后选覆盖前选，或按优先级排序后应用（可扩展）
"""

import copy
from typing import Dict, Any, List

# delta 的最小格式约定（建议）：
# {
#   "op": "set|replace|append",
#   "path": "veo_params.aspect_ratio" 或 "prompt.lighting" 或 "prompt.actions[]",
#   "value": "9:16" 或 ["Add slow motion between 3.0-4.0s"] ...
#   "reason": "why"（可选，用于日志/UI 展示）
# }

def _get_by_path(obj: Dict[str, Any], path: str):
    """按路径读取（不创建）"""
    cur = obj
    keys = path.split(".")
    for k in keys:
        if k.endswith("[]"):
            k = k[:-2]
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur

def _ensure_list_field(obj: Dict[str, Any], path: str):
    """确保 path 指向的字段是 list（如果不存在则创建空列表）"""
    cur = obj
    keys = path.split(".")
    for i, k in enumerate(keys):
        is_list = k.endswith("[]")
        key = k[:-2] if is_list else k
        if i == len(keys) - 1:
            cur.setdefault(key, [] if is_list else None)
            return cur, key, is_list
        if key not in cur or not isinstance(cur[key], dict):
            cur[key] = {}
        cur = cur[key]
    return cur, keys[-1], False

def _ensure_field(obj: Dict[str, Any], path: str):
    """确保 path 指向字段存在（对象层级存在），返回父对象和最后一级 key"""
    cur = obj
    keys = path.split(".")
    for i, k in enumerate(keys):
        if i == len(keys) - 1:
            return cur, k
        if keys not in cur or not isinstance(cur[keys], dict):
            cur[keys] = {}
        cur = cur[keys]
    return cur, keys[-1]

def apply_deltas(base_json: Dict[str, Any], deltas: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    应用一组 delta 到 base_json，返回新的 JSON（深拷贝）。
    仅支持简单的 set/replace/append 语义，足以覆盖多数常见修改。
    """
    new_obj = copy.deepcopy(base_json)
    for d in deltas:
        op = (d.get("op") or "set").lower()
        path = d.get("path")
        value = d.get("value")
        if not path:
            continue

        if path.endswith("[]"):  # 追加到列表
            parent, key, is_list = _ensure_list_field(new_obj, path)
            if not isinstance(parent.get(key), list):
                parent[key] = []
            if isinstance(value, list):
                parent[key].extend(value)
            else:
                parent[key].append(value)
        else:
            parent, key = _ensure_field(new_obj, path)
            if op in ("set", "replace"):
                parent[key] = value
            elif op == "append":
                # 如果字段本身是字符串，可以拼接；若是 list，则追加
                current_val = parent.get(key)
                if isinstance(current_val, list):
                    if isinstance(value, list):
                        current_val.extend(value)
                    else:
                        current_val.append(value)
                elif isinstance(current_val, str) and isinstance(value, str):
                    # 改进：避免在空字符串前加空格
                    if current_val:
                        parent[key] = current_val + ". " + value.strip(".")
                    else:
                        parent[key] = value
                else:
                    # 类型不兼容，则直接覆盖
                    parent[key] = value
    return new_obj