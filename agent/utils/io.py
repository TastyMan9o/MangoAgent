# -*- coding: utf-8 -*-
import os, json, yaml
from typing import Any, Dict

def ensure_dir(d: str):
    os.makedirs(d, exist_ok=True)

def write_json(path: str, data: Any):
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def write_yaml(path: str, data: Dict[str, Any]):
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
