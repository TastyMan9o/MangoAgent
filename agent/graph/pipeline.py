# -*- coding: utf-8 -*-
"""
agent/graph/pipeline.py (升级版)
===========================================================
作用：
  - 热点线: 热点 -> 选择 -> 下载 -> Gemini分析 -> v1
  - Refine线: vN -> vN+1
"""

from typing import Literal, Dict, Any, List
from langgraph.graph import StateGraph, END

from agent.graph.state import GraphState
from agent.config import Settings

# 热点候选与选择
from agent.hotspot.finder import find_hotspots, manual_select
# 本地 refine
from agent.interactive.refiner import refine_prompt_json, save_refined_version

# --- 引入新的 Gemini 增强器 ---
from agent.enhancers.gemini_vision import analyze_video_and_generate_prompt


# ---------------- 节点实现 ----------------

def node_hotspot_find(state: GraphState) -> GraphState:
    """根据关键词/窗口/权重，找到热点候选列表，写回 state['hotspot_candidates']。"""
    s = Settings()
    keywords = state.get("keywords") or s.get("hotspot", "keywords", default=["cat", "ASMR", "slime"])
    lookback = state.get("lookback_days") or s.get("hotspot", "lookback_days", default=7)
    top_k = state.get("top_k") or s.get("hotspot", "top_k", default=10)  # 增加候选数量
    weights = s.get("hotspot", "score_weights", default={"views": 0.5, "likes": 0.2, "comments": 0.2, "danmaku": 0.1})
    cands = find_hotspots(keywords=keywords, lookback_days=lookback, top_k=top_k, weights=weights)
    state["hotspot_candidates"] = [vars(x) for x in cands]
    return state


def node_hotspot_select(state: GraphState) -> GraphState:
    """
    选择候选：支持自动或人工模式。
    结果列表保存在 state['hotspot_candidates']（被截断为所选）
    """
    manual = bool(state.get("manual"))
    cands = state.get("hotspot_candidates") or []
    if not cands:
        state["hotspot_candidates"] = []
        return state

    # 为 dataclass 转来的 dict 补充 score
    for c in cands:
        if "score" not in c: c["score"] = 0

    if manual:
        from agent.hotspot.finder import Hotspot
        objs = [Hotspot(**c) for c in cands]
        picked_objs = manual_select(objs)
        state["hotspot_candidates"] = [vars(x) for x in picked_objs]
    else:
        # 自动模式：默认取分数最高的top_k个
        top_k_auto = state.get("top_k") or 1
        state["hotspot_candidates"] = cands[:top_k_auto]

    return state


# --- 新增节点：使用 Gemini 分析并生成 Prompt ---
def node_analyze_and_generate(state: GraphState) -> GraphState:
    """
    遍历已选择的热点，下载视频，用 Gemini 分析，并生成 v1 Prompt。
    """
    series = state.get("series") or "Gemini Hotspot Series"
    selected_hotspots = state.get("hotspot_candidates") or []
    generated_paths: List[str] = []

    if not selected_hotspots:
        print("⚠️ 没有选择任何热点，流程结束。")
        return state

    for hotspot in selected_hotspots:
        try:
            path = analyze_video_and_generate_prompt(hotspot, series)
            generated_paths.append(path)
        except Exception as e:
            print(f"❌ 处理热点 '{hotspot.get('title')}' 时发生错误: {e}")
            continue

    state["generated_paths"] = generated_paths
    return state


def node_refine_once(state: GraphState) -> GraphState:
    """
    本地人工 refine 一次：把 base_json_path + feedback_text 生成 vN+1，并登记。
    """
    base = state.get("base_json_path")
    fb = state.get("feedback_text")
    if not base or not fb:
        return state
    old_json, new_json, diffs = refine_prompt_json(base_json_path=base, user_feedback=fb, model="deepseek-chat")
    out_path = save_refined_version(new_json, base_json_path=base)
    from agent.registry.store import register_prompt
    register_prompt(new_json, out_path, status="ready")
    state["new_json_path"] = out_path
    state["diffs"] = diffs
    return state


# ---------------- 构图函数 (已更新) ----------------

def build_graph(mode: str = "hotspot"):
    """
    构建并编译图：
      - mode="hotspot"：热点 -> 选择 -> Gemini分析&生成 -> END
      - mode="refine"  ：vN + 反馈 -> vN+1 -> END
    """
    g = StateGraph(GraphState)

    if mode == "refine":
        g.add_node("refine_once", node_refine_once)
        g.set_entry_point("refine_once")
        g.add_edge("refine_once", END)
    else:
        # --- 更新后的热点线工作流 ---
        g.add_node("hotspot_find", node_hotspot_find)
        g.add_node("hotspot_select", node_hotspot_select)
        g.add_node("analyze_and_generate", node_analyze_and_generate)  # 新节点

        g.set_entry_point("hotspot_find")
        g.add_edge("hotspot_find", "hotspot_select")
        g.add_edge("hotspot_select", "analyze_and_generate")  # 连接到新节点
        g.add_edge("analyze_and_generate", END)

    return g.compile()