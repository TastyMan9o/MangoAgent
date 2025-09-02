# agent/miners/comments.py (稳定版)
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, json, re
from typing import List, Dict, Any, Optional, Union
from dotenv import load_dotenv
from openai import OpenAI
from agent.miners.insight_schema import InsightDoc
from agent.collectors.bilibili import Video

load_dotenv()

DEEPSEEK_MODEL = "deepseek-chat"

def _load_client() -> "OpenAI":
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key: raise RuntimeError("缺少 DEEPSEEK_API_KEY。")
    return OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

def _safe_load_json(s: str) -> Dict[str, Any]:
    s = re.sub(r"^```json\s*|\s*```$", "", s.strip(), flags=re.I).strip()
    try:
        return json.loads(s)
    except Exception as e:
        raise RuntimeError(f"模型未返回合法 JSON：\n{s[:1000]}") from e

def _post_validate(obj: Dict[str, Any]) -> Dict[str, Any]:
    def clip01(x: Any) -> float:
        try: f = float(x)
        except Exception: return 0.0
        return max(0.0, min(1.0, f))
    topics = obj.get("topics") or []
    for t in topics:
        sr = t.get("sentiment_ratio") or {}; acts = t.get("actions") or []
        for k in ("pos","neu","neg"):
            if k in sr: sr[k] = float(sr.get(k) or 0)
        for a in acts:
            ice = a.get("priority_ice") or {}
            for k in ("impact","confidence","effort"): ice[k] = clip01(ice.get(k))
            if "score" not in ice: ice["score"] = round((ice.get("impact",0) + ice.get("confidence",0) - ice.get("effort",0)) / 3, 2)
            a["priority_ice"] = ice
    obj["topics"] = topics
    obj.setdefault("global_recs", {"prompt_deltas": [], "thumbnails": [], "titles": []})
    return obj

def _build_messages(video: Video, sample_comments: List[str]) -> List[Dict[str, str]]:
    sys_prompt = ("You are a helpful assistant that analyzes Bilibili video comments and outputs STRICT JSON.")
    schema_hint = '''Return ONLY a JSON object like:
    { "topics": [ { "label": "...", "size": 12, "sentiment_ratio": {"pos": 0.55, "neu": 0.35, "neg": 0.10}, "key_quotes": ["..."], "insight": "...", "actions": [ {"type":"prompt_delta","delta":"...","priority_ice":{"impact":0.8,"confidence":0.7,"effort":0.3}} ] } ], "global_recs": {"prompt_deltas": [], "thumbnails": [], "titles": []} }'''
    user_prompt = (f"VIDEO:\n- title: {video.title}\n- url: {video.url}\n\nCOMMENTS (raw):\n" + "\n".join(f"- {c}" for c in sample_comments) + f"\n\n{schema_hint}")
    return [{"role":"system","content":sys_prompt}, {"role":"user","content":user_prompt}]

def analyze_comments_to_insight(video: Union[Video, Dict[str, Any]], comments: List[Dict[str, Any]], model: str = DEEPSEEK_MODEL, temperature: float = 0.2, client: Optional["OpenAI"] = None,) -> Dict[str, Any]:
    if not isinstance(video, Video):
        v = Video(bvid=video.get("bvid",""), title=video.get("title",""), url=video.get("url",""), pubdate=0, stats={})
    else:
        v = video

    texts = [str(c.get("text","")).strip() for c in comments if c.get("text")]
    uniq: Dict[str, int] = {}
    for c in comments:
        t = str(c.get("text","")).strip()
        if not t: continue
        like = int(c.get("like") or 0)
        uniq[t] = max(uniq.get(t, 0), like)
    ordered = sorted(uniq.items(), key=lambda kv: kv[1], reverse=True)
    sample = [t for t,_ in ordered[:200]] or texts[:200]

    if not sample:
        empty = {"topics": [], "global_recs": {"prompt_deltas": [], "thumbnails": [], "titles": []}}
        InsightDoc(**empty); return empty

    if client is None: client = _load_client()
    messages = _build_messages(v, sample)
    resp = client.chat.completions.create(model=model, messages=messages, temperature=temperature, response_format={"type":"json_object"})
    content = (resp.choices[0].message.content or "").strip()
    if not content: raise RuntimeError("模型未返回内容")

    obj = _safe_load_json(content)
    obj = _post_validate(obj)
    InsightDoc(**obj)
    return obj