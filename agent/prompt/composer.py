# -*- coding: utf-8 -*-
"""
agent/prompt/composer.py
---------------------------------------------------------
作用：
  - 生成一个最小可用的 v1 Prompt（用于“热点线”的初稿）
  - 提供 render_prompt()：把分块顺序拼成完整文本
后续我们会从热点/系列输入中自动填充这些槽位。
---------------------------------------------------------
"""
import time
from datetime import datetime
from typing import Dict
from agent.models import PromptSpec, PromptMeta, VeoParams, PromptBlocks
from agent.utils.io import write_yaml, ensure_dir

def slugify(s: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in s).strip("_")

def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")

def render_prompt(blocks: PromptBlocks, order=None) -> str:
    """
    把 Prompt 的各个分块按照指定顺序拼接为一个自然语言字符串。
    生成支线（文生图/文生视频）会直接拿这个字符串作为 prompt。
    """
    order = order or ["concept","shot","action","lighting","look","audio","timing","constraints"]
    parts = [getattr(blocks, k) for k in order if getattr(blocks, k, None)]
    return "。".join(p.strip().rstrip("。") for p in parts if p).strip() + "。"

def make_v1(topic: str, series: str, defaults: Dict) -> PromptSpec:
    """
    根据主题生成最小可用 v1 Prompt。
    后续我们会根据热点/专栏洞察自动填充更细的参数。
    """
    pb = PromptBlocks(
        concept=f"{topic}；整体画面治愈、干净",
        shot="macro close-up，中心构图，缓慢 dolly-in",
        action="逐步加压，在 3.2–4.0s 达到最大形变并短暂停留",
        lighting="顶部软光箱+侧边缘光，表面高光清晰，避免过曝",
        look="写实风格，高清微距，浅景深但接触面纹理清晰",
        audio="极轻微的 ASMR 细节声；无环境噪音或-20dB 轻音乐",
        timing="总时长 8s；0–1s 建立；1–4s 逐步按压；3.2–4.0s 0.5x 慢动作；4–7s 回弹；7–8s 收束",
        constraints="不出现文字水印/卡通渲染/模糊；保持材质透明度与细节"
    )
    name = f"deepseek_chat/{slugify(series)}/{time.strftime('%Y%m%d_%H%M')}_v1"
    spec = PromptSpec(
        name=name,
        meta=PromptMeta(source="hotspot", topic=topic, series=series, created_at=now_iso()),
        veo_params=VeoParams(
            aspect_ratio=defaults.get("prompt",{}).get("aspect_ratio","16:9"),
            person_generation=defaults.get("prompt",{}).get("person_generation","dont_allow"),
            negative_prompt=defaults.get("prompt",{}).get("negative_prompt","cartoon, drawing, low quality")
        ),
        prompt_blocks=pb
    )
    return spec

def save_prompt(spec: PromptSpec, base_dir="prompts"):
    """
    把 PromptSpec 保存为 YAML 文件，并返回文件路径。
    """
    path = "/".join([base_dir] + spec.name.split("/")) + ".yaml"
    write_yaml(path, spec.model_dump(exclude_none=True))
    return path
