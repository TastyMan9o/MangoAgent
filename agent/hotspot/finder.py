# agent/hotspot/finder.py (缩进修正版)
# -*- coding: utf-8 -*-
import re
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any

# --- 优化：导入公共函数 search_by_keyword ---
from agent.collectors.bilibili import search_by_keyword, BILI_COOKIE

@dataclass
class Hotspot:
    title: str
    url: str
    bvid: str
    pubdate: int = 0
    tags: List[str] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)
    score: float = 0.0

def _score(stats: Dict[str, Any], pubdate: int, weights: Dict[str, float]) -> float:
    '''
    高级热度分计算函数 (类似Hacker News热度算法)
    Score = P / (T + 2)^G
    '''
    # --- 以下为修正缩进的代码块 ---
    p = (
        float(stats.get("likes", 0)) * weights.get("likes", 1.0) +
        float(stats.get("favorites", 0)) * weights.get("favorites", 1.2) +
        float(stats.get("shares", 0)) * weights.get("shares", 1.5) +
        float(stats.get("comments", 0)) * weights.get("comments", 0.8) +
        float(stats.get("danmaku", 0)) * weights.get("danmaku", 0.5) +
        float(stats.get("views", 0)) * weights.get("views", 0.1)
    )
    t = (time.time() - pubdate) / 3600.0
    g = weights.get("gravity", 1.8)
    score = p / pow(t + 2, g)
    return score

def find_hotspots(keywords: List[str], top_k: int, weights: Dict[str, float]) -> List[Hotspot]:
    # --- 以下为修正缩进的代码块 ---
    if not BILI_COOKIE:
        print("[⚠️ 警告] .env 文件中缺少 BILI_COOKIE，热点发现功能可能受限或失败。")

    print(f"🔍 正在为关键词 {keywords} 搜索真实热点视频...")
    pool: List[Hotspot] = []

    for kw in keywords:
        # --- 优化：调用公共函数 ---
        search_result = search_by_keyword(kw)
        try:
            video_list = search_result.get("data", {}).get("result", [])
            for v_data in video_list:
                if v_data.get("type") == "video":
                    stats = {
                        "views": v_data.get("play", 0),
                        "likes": v_data.get("like", 0),
                        "comments": v_data.get("review", 0),
                        "danmaku": v_data.get("danmaku", 0),
                        "favorites": v_data.get("collect", 0),
                        "shares": v_data.get("share", 0)
                    }
                    clean_title = re.sub(r'<em class="keyword">|</em>', '', v_data.get("title", ""))

                    hotspot = Hotspot(
                        title=clean_title,
                        url=v_data.get("arcurl", ""),
                        bvid=v_data.get("bvid", ""),
                        pubdate=v_data.get("pubdate", int(time.time())),
                        stats=stats,
                        tags=v_data.get("tag", "").split(",")
                    )
                    pool.append(hotspot)
        except Exception as e:
            print(f"❌ 解析关键词 '{kw}' 的搜索结果时出错: {e}")
            continue

    dedup: Dict[str, Hotspot] = {}
    for h in pool:
        if h.bvid and h.bvid not in dedup:
            dedup[h.bvid] = h
    unique_pool = list(dedup.values())

    for h in unique_pool:
        h.score = _score(h.stats, h.pubdate, weights)

    ranked = sorted(unique_pool, key=lambda x: x.score, reverse=True)

    print(f"✅ 找到 {len(unique_pool)} 个不重复的视频，返回前 {top_k} 个。")
    return ranked[:top_k]