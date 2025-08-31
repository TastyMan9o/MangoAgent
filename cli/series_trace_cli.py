# cli/series_trace_cli.py (完整替换)
# -*- coding: utf-8 -*-
"""
cli/series_trace_cli.py (修改为支持单个视频URL)
===========================================================
作用：
  提供“带溯源的系列迭代”命令行入口，针对单个视频URL：
    python -m cli.series_trace_cli iterate_series_trace --base <vN.json> --video_url <B站视频链接>
"""

import argparse
from agent.iterators.series_trace import iterate_series_with_trace

def cmd_iter(args):
    newp, report = iterate_series_with_trace(
        base_prompt_path=args.base,
        video_url=args.video_url,
        max_comments=args.max_comments,
        top_deltas=args.top_deltas
    )
    print(f"[OK] New prompt: {newp}")
    print(f"[OK] Trace report: {report}")

def main():
    p = argparse.ArgumentParser("series iteration with trace CLI")
    sub = p.add_subparsers(required=True)

    it = sub.add_parser("iterate_series_trace", help="针对单个视频进行迭代（含评论→改动溯源报告）")
    it.add_argument("--base", required=True, help="已有 JSON Prompt 路径（vN.json）")
    it.add_argument("--video_url", required=True, help="B站视频链接，如 https://www.bilibili.com/video/BV1Epg7zoEqJ/")
    # 移除 --filter_keyword 和 --limit_videos
    it.add_argument("--max_comments", type=int, default=120, help="最多拉取的评论数")
    it.add_argument("--top_deltas", type=int, default=3, help="最多合并的改动条数")
    it.set_defaults(func=cmd_iter)

    args = p.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()