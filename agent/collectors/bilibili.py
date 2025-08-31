# agent/collectors/bilibili.py (稳定版)
# -*- coding: utf-8 -*-
import os
import re
import time
import json
import hashlib
import requests
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from urllib.parse import urlencode
from dotenv import load_dotenv
from agent.utils.cookie_loader import get_bili_cookie

load_dotenv()
DEBUG = os.getenv('BILI_DEBUG','') == '1'
BILI_COOKIE = get_bili_cookie() or os.getenv("BILI_COOKIE", "")
if not BILI_COOKIE:
    raise RuntimeError("‼️ [严重错误] 所有Cookie获取方式均失败，程序无法继续。请检查网络或在.env中提供有效的BILI_COOKIE。")
UA = os.getenv("BILI_UA", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA})
if BILI_COOKIE:
    SESSION.headers.update({"Cookie": BILI_COOKIE})

@dataclass
class Video:
    bvid: str
    title: str
    url: str
    pubdate: int
    stats: Dict[str, Any]

def _safe_get(url: str, params: Dict[str, Any] = None, timeout: int = 8) -> Dict[str, Any]:
    for _ in range(2):
        try:
            r = SESSION.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                try: return r.json()
                except: return {"_text": r.text}
            elif r.status_code in (403, 412):
                print(f"[warn] HTTP {r.status_code} {url}")
                return {}
        except Exception:
            time.sleep(0.7)
    return {}

def _bvid_to_aid(bvid: str) -> Optional[int]:
    url = "https://api.bilibili.com/x/web-interface/view"
    data = _safe_get(url, params={"bvid": bvid})
    try: return int(data["data"]["aid"])
    except Exception: return None

def fetch_comments(bvid: str, max_comments: int = 200) -> List[Dict[str, Any]]:
    '''抓取视频评论（x/v2/reply），返回评论列表。'''
    aid = _bvid_to_aid(bvid)
    if not aid:
        print(f"  - ❌ 诊断日志: 无法将 BVID '{bvid}' 转换为 AID。")
        return []
    print(f"  - ✅ 诊断日志: BVID '{bvid}' 成功转换为 AID: {aid}。")
    comments = []
    page = 1
    page_size = 20 # 适配B站API新规，降低页面大小
    while len(comments) < max_comments:
        url = "https://api.bilibili.com/x/v2/reply"
        params = {"oid": aid, "type": 1, "pn": page, "ps": page_size, "sort": 2}
        print(f"  - ➡️ 诊断日志: 正在请求第 {page} 页评论...")
        data = _safe_get(url, params=params)
        if not data:
            print("  - ❌ 诊断日志: 对B站评论API的请求失败，没有返回任何数据。")
            break
        if data.get("code", 0) != 0:
            print("  - ❌ 诊断日志: B站API返回了明确的错误码！")
            print(f"  - 错误码 (Code): {data.get('code')}, Message: {data.get('message')}")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            break
        try:
            if "data" not in data or "replies" not in data.get("data", {}) or data["data"].get("replies") is None:
                 print("  - ❌ 诊断日志: API响应中未找到 'data.replies' 键。")
                 print(json.dumps(data, indent=2, ensure_ascii=False))
                 break
            replies = data["data"]["replies"]
            if not replies:
                print(f"  - ✅ 诊断日志: 第 {page} 页没有更多评论了，获取结束。")
                break
            for r in replies:
                content = r.get("content", {})
                comments.append({"text": content.get("message", ""),"like": int(r.get("like") or 0),"ctime": int(r.get("ctime") or 0)})
            print(f"  - ✅ 诊断日志: 成功解析 {len(replies)} 条评论，当前总数: {len(comments)}")
            if data["data"].get("cursor", {}).get("is_end") or len(comments) >= max_comments:
                print("  - ✅ 诊断日志: 已到达评论末尾或达到数量上限，获取结束。")
                break
            page += 1
            time.sleep(0.5)
        except Exception as e:
            print(f"  - ❌ 诊断日志: 解析评论数据时发生意外错误: {e}")
            break
    return comments[:max_comments]

# --- 后续所有其他函数保持原样，无需修改 ---
# 为了脚本完整性，将所有函数都包含进来
def get_video_details(bvid: str) -> Optional[Video]:
    url = "https://api.bilibili.com/x/web-interface/view"
    data = _safe_get(url, params={"bvid": bvid})
    try:
        d = data["data"]
        stats_data = d.get("stat", {})
        converted_stats = {"views": stats_data.get("view", 0), "likes": stats_data.get("like", 0), "comments": stats_data.get("reply", 0), "danmaku": stats_data.get("danmaku", 0), "favorites": stats_data.get("favorite", 0), "shares": stats_data.get("share", 0)}
        return Video(bvid=d["bvid"], title=d["title"], url=f"https://www.bilibili.com/video/{d['bvid']}", pubdate=d["pubdate"], stats=converted_stats)
    except Exception: return None

def search_by_keyword(keyword: str, page: int = 1) -> Dict[str, Any]:
    url = "https://api.bilibili.com/x/web-interface/search/type"
    params = {"search_type": "video", "keyword": keyword, "page": page}
    return _safe_get(url, params=params)