# -*- coding: utf-8 -*-
"""
命令行入口（JSON Prompt 版）：
  - compose_json：主题 -> 英文 JSON v1
  - hotspot：热点发现 -> 选择 -> 批量产 v1
  - refine：本地人工迭代（vN -> vN+1）
"""
import argparse, os
from agent.config import Settings
from agent.prompt.composer_json import compose_v1_json, save_v1_json
from agent.registry.store import register_prompt
from agent.hotspot.finder import find_hotspots, manual_select
from agent.interactive.refiner import refine_prompt_json, save_refined_version

def cmd_compose_json(args):
    s = Settings()
    obj = compose_v1_json(topic=args.topic, series=args.series, defaults=s.cfg, source="manual")
    path = save_v1_json(obj)
    register_prompt(obj, path, status="ready")
    print(f"[OK] v1 saved -> {path}")

def cmd_hotspot(args):
    s = Settings()
    keywords = args.keywords or s.get("hotspot", "keywords", default=["cat","ASMR"])
    lookback = args.lookback_days or s.get("hotspot", "lookback_days", default=7)
    top_k = args.top_k or s.get("hotspot", "top_k", default=5)
    weights = s.get("hotspot", "score_weights", default={"views":0.5,"likes":0.2,"comments":0.2,"danmaku":0.1})
    cands = find_hotspots(keywords=keywords, lookback_days=lookback, top_k=top_k, weights=weights)
    picks = manual_select(cands) if args.manual else cands
    if not picks:
        print("[WARN] 没有候选。")
        return
    for h in picks:
        obj = compose_v1_json(topic=h.title, series=args.series, defaults=s.cfg, source="hotspot")
        path = save_v1_json(obj)
        register_prompt(obj, path, status="ready")
        print(f"[OK] v1 saved -> {path}")

def cmd_refine(args):
    if not args.base.endswith(".json"):
        raise RuntimeError("请提供 .json 的 Prompt 文件")
    feedback_text = args.feedback
    if args.feedback_file:
        with open(args.feedback_file, "r", encoding="utf-8") as f:
            feedback_text = f.read()
    if not feedback_text:
        raise RuntimeError("请使用 --feedback 或 --feedback_file 提供反馈内容")
    old_json, new_json, diffs = refine_prompt_json(base_json_path=args.base, user_feedback=feedback_text, model=args.model)
    out_path = save_refined_version(new_json, base_json_path=args.base)
    print(f"[OK] refined -> {out_path}")
    print("---- 变更概览 ----")
    for d in diffs[:50]:
        print("-", d)
    if len(diffs) > 50:
        print(f"... 其余 {len(diffs)-50} 项已省略")

def main():
    p = argparse.ArgumentParser("video-agent CLI")
    sub = p.add_subparsers(required=True)

    p_cj = sub.add_parser("compose_json", help="根据主题生成英文 JSON v1")
    p_cj.add_argument("--topic", required=True, help="主题文本（中英均可）")
    p_cj.add_argument("--series", default="Cat Healing", help="系列名")
    p_cj.set_defaults(func=cmd_compose_json)

    p_hot = sub.add_parser("hotspot", help="热点发现 -> 选择 -> 批量生成 v1（英文 JSON）")
    p_hot.add_argument("--series", default="Hot Series", help="系列名")
    p_hot.add_argument("--manual", action="store_true", help="人工选择模式（不加则自动）")
    p_hot.add_argument("--keywords", nargs="*", help="覆盖默认关键词")
    p_hot.add_argument("--lookback_days", type=int, help="回看天数")
    p_hot.add_argument("--top_k", type=int, help="候选上限")
    p_hot.set_defaults(func=cmd_hotspot)

    p_ref = sub.add_parser("refine", help="本地人工迭代：vN.json -> vN+1.json")
    p_ref.add_argument("--base", required=True, help="已有 JSON Prompt 路径")
    p_ref.add_argument("--feedback", help="反馈文本（英文/中文均可）")
    p_ref.add_argument("--feedback_file", help="包含反馈文本的文件路径")
    p_ref.add_argument("--model", default="deepseek-chat", help="小模型名称")
    p_ref.set_defaults(func=cmd_refine)

    args = p.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
