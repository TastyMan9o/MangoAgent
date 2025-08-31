# -*- coding: utf-8 -*-
"""
cli/series_cli.py
===========================================================
作用：
  把“系列自动迭代”做成独立命令行入口，便于你直接跑：
  python -m cli.series_cli iterate_series --base <vN.json> --space_url <B站空间> --filter_keyword 猫 --limit_videos 3 --max_comments 100 --top_deltas 3
"""

import argparse
from agent.iterators.series import iterate_series_to_new_prompt

def cmd_iterate_series(args):
    # 路径建议用引号；Windows 下注意反斜杠
    newp = iterate_series_to_new_prompt(
        base_prompt_path=args.base,
        space_url=args.space_url,
        filter_keyword=args.filter_keyword or "",
        limit_videos=args.limit_videos,
        max_comments=args.max_comments,
        top_deltas=args.top_deltas
    )
    print("[OK] new prompt:", newp)

def main():
    p = argparse.ArgumentParser("series-iterator CLI")
    sub = p.add_subparsers(required=True)

    it = sub.add_parser("iterate_series", help="系列自动迭代：vN -> vN+1")
    it.add_argument("--base", required=True, help="已有 JSON Prompt 路径（vN.json）")
    it.add_argument("--space_url", required=True, help="B站空间链接，如 https://space.bilibili.com/8240530")
    it.add_argument("--filter_keyword", help="标题关键词过滤（可空）")
    it.add_argument("--limit_videos", type=int, default=3, help="选取最近几条视频")
    it.add_argument("--max_comments", type=int, default=120, help="每条视频最多拉取的评论数")
    it.add_argument("--top_deltas", type=int, default=3, help="最多合并的改动建议条数")
    it.set_defaults(func=cmd_iterate_series)

    args = p.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
