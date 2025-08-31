# -*- coding: utf-8 -*-
"""
agent/graph/pipeline_series.py
===========================================================
作用：
  Graph 第三条线（series）：把“系列自动迭代”封装成一个可编排的图节点。
  设计最小：一个节点调用 iterate_series_to_new_prompt，后续容易插入更多细粒度节点。
"""

from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional

class SeriesState(TypedDict, total=False):
    base_json_path: str
    space_url: str
    filter_keyword: Optional[str]
    limit_videos: int
    max_comments: int
    top_deltas: int
    new_json_path: Optional[str]

# 直接复用我们现有的系列逻辑
from agent.iterators.series import iterate_series_to_new_prompt

def node_series_iter(state: SeriesState) -> SeriesState:
    """单节点完成：读取 vN -> 采集 -> 洞察 -> 合并 -> 写 vN+1"""
    newp = iterate_series_to_new_prompt(
        base_prompt_path=state["base_json_path"],
        space_url=state["space_url"],
        filter_keyword=state.get("filter_keyword") or "",
        limit_videos=state.get("limit_videos", 3),
        max_comments=state.get("max_comments", 120),
        top_deltas=state.get("top_deltas", 3),
    )
    state["new_json_path"] = newp
    return state

def build_series_graph():
    """构建并编译“系列自动迭代”的图"""
    g = StateGraph(SeriesState)
    g.add_node("series_iter", node_series_iter)
    g.set_entry_point("series_iter")
    g.add_edge("series_iter", END)
    return g.compile()
