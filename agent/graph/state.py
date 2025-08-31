# -*- coding: utf-8 -*-
"""
agent/graph/state.py
===========================================================
作用：
  定义 LangGraph 的“共享状态”结构（简明 TypedDict），
  各节点通过该状态传值，避免耦合。
"""

from typing import TypedDict, Optional, Dict, List, Any

class GraphState(TypedDict, total=False):
    # 模式选择
    mode: str                       # "hotspot" | "refine" | "series"（series 预留）

    # 热点线输入/输出
    series: Optional[str]           # 系列名
    keywords: Optional[List[str]]   # 热点关键词
    lookback_days: Optional[int]
    top_k: Optional[int]
    manual: Optional[bool]          # True=人工勾选，False/None=自动
    select_indexes: Optional[List[int]]  # 人工模式下，外部可直接传选中的编号（1-based）
    hotspot_candidates: Optional[List[Dict[str, Any]]]  # 候选热点（字典列表）
    generated_paths: Optional[List[str]]  # 生成的 v1.json 文件路径列表

    # 本地 refine 线输入/输出
    base_json_path: Optional[str]   # vN.json 路径
    feedback_text: Optional[str]    # 用户反馈
    new_json_path: Optional[str]    # vN+1.json 路径

    # 系列迭代（预留）
    series_url: Optional[str]
    filter_keyword: Optional[str]
    limit_videos: Optional[int]
    insights_path: Optional[str]    # 评论洞察 JSON 路径（预留）
