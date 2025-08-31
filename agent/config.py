# -*- coding: utf-8 -*-
import os, yaml
from typing import Any, Dict
from dotenv import load_dotenv

load_dotenv()

def load_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def get_env_required(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"缺少环境变量：{name}（请在 .env 中设置真实值）")
    return v

class Settings:
    def __init__(self, cfg_path: str = "config/default.yaml"):
        self.cfg = load_yaml(cfg_path)
        # 必填：后续会用到 LLM
        self.deepseek_api_key = get_env_required("DEEPSEEK_API_KEY")
        # 可选：B站访问更稳
        self.bili_cookie = os.getenv("BILI_COOKIE", "")

    def get(self, *keys, default=None):
        node = self.cfg
        for k in keys:
            if isinstance(node, dict) and k in node:
                node = node[k]
            else:
                return default
        return node
