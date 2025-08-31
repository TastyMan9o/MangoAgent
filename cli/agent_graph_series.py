# -*- coding: utf-8 -*-
"""
cli/agent_graph_series.py
===========================================================
作用：
  Graph 入口（第三条线）：series 自动迭代
  用法：
    python -m cli.agent_graph_series graph_series_iter --base <vN.json> --space_url <B站空间> --filter_keyword 猫 --limit_videos 3 --max_comments 100 --top_deltas 3
"""

import argparse
from agent.graph.pipeline_series import build_series_graph

def cmd_graph_series_iter(args):
    app = build_series_graph()
    state = {
        "base_json_path": args.base,
        "space_url": args.space_url,
        "filter_keyword": args.filter_keyword,
        "limit_videos": args.limit_videos,
        "max_comments": args.max_comments,
        "top_deltas": args.top_deltas,
    }
    result = app.invoke(state)
    print("=== RESULT ===")
    print("new_json_path:", result.get("new_json_path"))

def main():
    p = argparse.ArgumentParser("video-agent GRAPH (series)")
    sub = p.add_subparsers(required=True)

    s = sub.add_parser("graph_series_iter", help="Graph：系列自动迭代 vN -> vN+1")
    s.add_argument("--base", required=True, help="已有 JSON Prompt 路径（vN.json）")
    s.add_argument("--space_url", required=True, help="B站空间链接，如 https://space.bilibili.com/8240530")
    s.add_argument("--filter_keyword", help="标题关键词过滤（可空）")
    s.add_argument("--limit_videos", type=int, default=3)
    s.add_argument("--max_comments", type=int, default=120)
    s.add_argument("--top_deltas", type=int, default=3)
    s.set_defaults(func=cmd_graph_series_iter)

    args = p.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
