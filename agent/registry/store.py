# -*- coding: utf-8 -*-
"""
版本注册索引：prompts/index.json
- 记录 name/path/series/topic/source/parent/created_at/status
- 便于 UI 列表、回滚
"""
import os, json
from typing import Dict, Any
from agent.utils.io import ensure_dir, write_json

INDEX_PATH = os.path.join("prompts", "index.json")

def _load_index() -> Dict[str, Any]:
    if not os.path.exists(INDEX_PATH):
        return {}
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        try:
            return json.load(f) or {}
        except:
            return {}

def _save_index(idx: Dict[str, Any]):
    ensure_dir(os.path.dirname(INDEX_PATH))
    write_json(INDEX_PATH, idx)

def register_prompt(obj: Dict[str, Any], file_path: str, status: str = "ready") -> None:
    idx = _load_index()
    pid = obj.get("name")
    meta = obj.get("meta", {})
    idx[pid] = {
        "name": obj.get("name"),
        "path": file_path.replace("\\", "/"),
        "series": meta.get("series"),
        "topic": meta.get("topic"),
        "source": meta.get("source"),
        "parent": meta.get("parent_prompt_id"),
        "created_at": meta.get("created_at"),
        "status": status,
    }
    _save_index(idx)

def list_prompts() -> Dict[str, Any]:
    return _load_index()
