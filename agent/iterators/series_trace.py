# agent/iterators/series_trace.py (带详细日志的稳定版)
# -*- coding: utf-8 -*-
import os, json, re
from typing import List, Dict, Any, Tuple
from agent.collectors.bilibili import fetch_comments, Video, get_video_details
from agent.miners.comments import analyze_comments_to_insight
from agent.iterators.delta_normalizer import normalize_to_visual_deltas
from agent.iterators.merge_policy import apply_deltas
from agent.prompt.schema_json import VideoPromptJSON
from agent.interactive.refiner import save_refined_version
from agent.reports.trace_report import save_trace_bundle

def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _select_visual_deltas_with_evidence(insight: Dict[str, Any], top_k: int = 3) -> List[Dict[str, Any]]:
    flat = []
    for t in insight.get("topics", []):
        label = t.get("label") or ""
        topic_quotes = t.get("key_quotes") or []
        for a in t.get("actions", []):
            sc = ((a.get("priority_ice") or {}).get("score") or 0.0)
            flat.append((float(sc), a, label, topic_quotes))
    flat.sort(key=lambda x: x[0], reverse=True)
    picked = []
    for _, action, label, quotes in flat:
        vis = normalize_to_visual_deltas([action], top_k=1)
        if not vis: continue
        delta = vis[0]
        picked.append({"delta": delta, "from_action_text": action.get("delta") or "", "topic_label": label, "supporting_quotes": list(quotes[:3])})
        if len(picked) >= top_k: break
    return picked

def iterate_series_with_trace(base_prompt_path: str, video_url: str,
                              max_comments: int = 200, top_deltas: int = 3) -> Tuple[str, str]:
    print("\n--- 开始单视频迭代流程 ---")
    base = _load_json(base_prompt_path)
    _ = VideoPromptJSON(**base)
    print(f"✅ 1. 成功加载基础Prompt: {base_prompt_path}")

    bvid_match = re.search(r'BV([a-zA-Z0-9_]+)', video_url)
    if not bvid_match: raise ValueError(f"无法从URL中提取有效的BVID: {video_url}")
    bvid = bvid_match.group(0)

    video = get_video_details(bvid)
    if not video: raise RuntimeError(f"无法获取视频详情: {video_url}")
    print(f"✅ 2. 成功获取视频详情: {video.title}")

    print(f"⏳ 3. 正在为 BVID:{video.bvid} 获取评论...")
    comments = fetch_comments(video.bvid, max_comments=max_comments)
    print(f"   - 获取到 {len(comments)} 条评论。")

    print("⏳ 4. 正在进行AI洞察分析...")
    insight = analyze_comments_to_insight(video, comments)
    print(f"   - AI分析完成，找到 {len(insight.get('topics', []))} 个主题。")

    print("⏳ 5. 正在从洞察中提取视觉修改建议...")
    vis_with_evd = _select_visual_deltas_with_evidence(insight, top_k=top_deltas)
    print(f"   - 提取到 {len(vis_with_evd)} 条有效的视觉修改建议。")

    trace_items = [{"video": vars(video), "comments_sampled_count": len(comments), "insight": insight, "adopted_deltas": vis_with_evd}]
    all_deltas = [item["delta"] for item in vis_with_evd]

    final_deltas = all_deltas[:top_deltas]
    print(f"⏳ 6. 准备应用 {len(final_deltas)} 条修改建议...")
    new_json = apply_deltas(base, final_deltas)

    print("⏳ 7. 正在保存新版本Prompt...")
    new_path = save_refined_version(new_json, base_json_path=base_prompt_path)
    print(f"✅ 8. 新版本已保存: {new_path}")

    print("⏳ 9. 正在生成溯源报告...")
    report_path = save_trace_bundle(
        base_prompt_path=base_prompt_path, new_prompt_path=new_path,
        space_url=video_url, filter_keyword="", trace_items=trace_items
    )
    print("--- 流程执行完毕 ---")
    return new_path, report_path