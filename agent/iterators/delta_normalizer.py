# -*- coding: utf-8 -*-
"""
agent/iterators/delta_normalizer.py
===========================================================
作用：
  把洞察里的 actions（仅限 type=prompt_delta）过滤并映射为“视觉专用”的结构化改动：
    - 只允许作用于以下字段：
      veo_params.*、
      prompt.{concept,shots,actions,lighting,style,audio,timing,constraints}
  非视觉域（封面/标题/互动/科普/开头解释等）一律丢弃。
"""

import re
from typing import List, Dict, Any

# 关键词黑名单（非视觉域）
_NON_VISUAL_PATTERNS = [
    r"封面", r"缩略图", r"thumbnail", r"title", r"标题",
    r"互动", r"评论区", r"引导.*关注", r"分享", r"转发", r"收藏",
    r"科普", r"开头解释", r"口播", r"简介", r"description\b", r"置顶评论",
]

# 视觉相关线索，用于简单映射
_VISUAL_HINTS = {
    "force_more": [r"按.*重", r"press.*hard", r"strong(er)? press", r"更用力", r"压力(更大|增强)"],
    "breed_ragdoll": [r"布偶猫", r"ragdoll"],
    "breed_british": [r"(英短|英国短毛猫|british short)"],
    "tempo_slow": [r"慢(一点|一些)|更慢|slow(er)?", r"放慢节奏"],
    "tempo_fast": [r"快(一点|一些)|更快|fast(er)?", r"加快节奏"],
    "lighting_soft": [r"柔(光|和的光)|soft light"],
    "lighting_rim": [r"轮廓光|rim light"],
    "macro_close": [r"微距|macro", r"特写", r"close[- ]?up"],
    "color_warm": [r"暖色|暖调|warm"],
    "color_cool": [r"冷色|冷调|cool"],
    "ar_916": [r"9[:：]16|竖屏|vertical"],
    "ar_169": [r"16[:：]9|横屏|horizontal"],
}

def _match_any(text: str, patterns: List[str]) -> bool:
    t = text.lower()
    for p in patterns:
        if re.search(p, t, flags=re.I):
            return True
    return False

def _any_from_dict(text: str, d: Dict[str, List[str]]) -> str:
    for key, pats in d.items():
        if _match_any(text, pats):
            return key
    return ""

def normalize_to_visual_deltas(actions: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
    """
    输入洞察里的 actions 列表，输出“视觉专用”的 delta（merge_policy 可直接应用）。
    - 仅接收 type=prompt_delta
    - 过滤非视觉域关键词
    - 依据简单规则映射到结构化 path/op/value
    """
    vis: List[Dict[str, Any]] = []
    # 先按 score 排序（如果有）
    sortable = []
    for a in actions:
        if (a.get("type") or "").lower() != "prompt_delta":
            continue
        delta = a.get("delta") or ""
        if _match_any(delta, _NON_VISUAL_PATTERNS):
            continue
        score = ((a.get("priority_ice") or {}).get("score") or 0.0)
        sortable.append((float(score), delta))
    sortable.sort(key=lambda x: x[0], reverse=True)

    for _, delta_text in sortable[:top_k]:
        key = _any_from_dict(delta_text, _VISUAL_HINTS)
        # 映射策略（可继续丰富）
        if key == "force_more":
            vis.append({"op":"append","path":"prompt.actions[]","value":"increase pressing force on slime","reason":"visual-only"})
        elif key == "breed_ragdoll":
            vis.append({"op":"append","path":"prompt.shots[]","value":{
                "camera":"macro close-up, gentle handheld",
                "composition":"centered, full paw in frame",
                "focal_subject":"ragdoll cat paw",
                "movement_speed":"slow"
            },"reason":"visual-only"})
        elif key == "breed_british":
            vis.append({"op":"append","path":"prompt.shots[]","value":{
                "camera":"macro close-up, gentle handheld",
                "composition":"rule of thirds, paw angled 30°",
                "focal_subject":"british shorthair cat paw",
                "movement_speed":"slow"
            },"reason":"visual-only"})
        elif key == "tempo_slow":
            vis.append({"op":"append","path":"prompt.actions[]","value":"slow down paw movement between 3-6s","reason":"visual-only"})
        elif key == "tempo_fast":
            vis.append({"op":"append","path":"prompt.actions[]","value":"add quick press at 2.0-2.5s for contrast","reason":"visual-only"})
        elif key == "lighting_soft":
            vis.append({"op":"set","path":"prompt.lighting","value":"soft key light with large diffuser, minimal specular","reason":"visual-only"})
        elif key == "lighting_rim":
            vis.append({"op":"append","path":"prompt.actions[]","value":"add subtle rim light on paw outline","reason":"visual-only"})
        elif key == "macro_close":
            vis.append({"op":"append","path":"prompt.shots[]","value":{
                "camera":"macro close-up, slow dolly-in",
                "composition":"tight frame, paw 70% area",
                "focal_subject":"cat paw and clear slime surface",
                "movement_speed":"slow"
            },"reason":"visual-only"})
        elif key == "color_warm":
            vis.append({"op":"append","path":"prompt.actions[]","value":"shift color temperature to warm tone (3200-3800K)","reason":"visual-only"})
        elif key == "color_cool":
            vis.append({"op":"append","path":"prompt.actions[]","value":"shift color temperature to cool tone (5200-6500K)","reason":"visual-only"})
        elif key == "ar_916":
            vis.append({"op":"set","path":"veo_params.aspect_ratio","value":"9:16","reason":"visual-only"})
        elif key == "ar_169":
            vis.append({"op":"set","path":"veo_params.aspect_ratio","value":"16:9","reason":"visual-only"})
        else:
            # 落到通用 actions，仍保持视觉语气
            vis.append({"op":"append","path":"prompt.actions[]","value":delta_text,"reason":"visual-only"})
    return vis