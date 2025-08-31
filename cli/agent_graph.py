# -*- coding: utf-8 -*-
"""
cli/agent_graph.py
===========================================================
作用：
  LangGraph 编排的命令行入口（不覆盖原有 cli/agent.py）：
  - graph_hotspot ：热点 → 选择（自动/人工）→ 批量生成 v1（英文 JSON）
  - graph_refine  ：把 vN + 反馈 → vN+1（英文 JSON）

说明：
  Windows 友好，所有参数单行可传；反馈建议用 --feedback_file。
"""

import argparse, json
from agent.graph.pipeline import build_graph

def cmd_graph_hotspot(args):
    app = build_graph(mode="hotspot")
    state = {
        "mode": "hotspot",
        "series": args.series,
        "manual": args.manual,
        "keywords": args.keywords,
        "lookback_days": args.lookback_days,
        "top_k": args.top_k,
    }
    if args.select_indexes:
        # 允许直接传选中编号（1-based），跳过交互
        try:
            idxs = [int(x) for x in args.select_indexes.split(",")]
            state["select_indexes"] = idxs
            state["manual"] = True
        except:
            pass
    result = app.invoke(state)
    print("=== RESULT ===")
    print("generated_paths:", result.get("generated_paths"))

def cmd_graph_refine(args):
    app = build_graph(mode="refine")
    feedback = args.feedback
    if args.feedback_file and not feedback:
        with open(args.feedback_file, "r", encoding="utf-8") as f:
            feedback = f.read()
    state = {
        "mode": "refine",
        "base_json_path": args.base,
        "feedback_text": feedback,
    }
    result = app.invoke(state)
    print("=== RESULT ===")
    print("new_json_path:", result.get("new_json_path"))
    diffs = result.get("diffs") or []
    for d in diffs[:50]:
        print("-", d)
    if len(diffs) > 50:
        print(f"... 其余 {len(diffs)-50} 项已省略")

def main():
    p = argparse.ArgumentParser("video-agent GRAPH CLI")
    sub = p.add_subparsers(required=True)

    p_hot = sub.add_parser("graph_hotspot", help="热点 → 选择（自动/人工）→ 批量生成 v1（英文 JSON）")
    p_hot.add_argument("--series", default="Hot Series")
    p_hot.add_argument("--manual", action="store_true", help="人工模式；若配合 --select_indexes 可跳过交互")
    p_hot.add_argument("--keywords", nargs="*", help="覆盖默认关键词，如：--keywords cat ASMR slime")
    p_hot.add_argument("--lookback_days", type=int, help="回看天数（默认 7）")
    p_hot.add_argument("--top_k", type=int, help="候选上限（默认 5）")
    p_hot.add_argument("--select_indexes", help="人工选择编号列表，如 1,3 或 2,4")
    p_hot.set_defaults(func=cmd_graph_hotspot)

    p_ref = sub.add_parser("graph_refine", help="把 vN + 反馈 → vN+1（英文 JSON）")
    p_ref.add_argument("--base", required=True, help="已有 JSON Prompt（vN）路径")
    p_ref.add_argument("--feedback", help="反馈文本（建议英文；中文也可，会转英文输出）")
    p_ref.add_argument("--feedback_file", help="包含反馈文本的文件路径")
    p_ref.set_defaults(func=cmd_graph_refine)

    args = p.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
