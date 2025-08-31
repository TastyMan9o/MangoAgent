# main.py (带创意扩展API)
# -*- coding: utf-8 -*-
import os, glob, json, re
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

# ... (大部分import保持不变) ...
from agent.enhancers.gemini_vision import analyze_video_and_generate_prompt
from agent.enhancers.prompt_expander import expand_prompt # <-- 新增导入
# ...

app = FastAPI(title="VideoAgent API", version="2.1.0")

# --- Pydantic 模型定义 ---
class ExpandRequest(BaseModel):
    prompt_path: str
    num_expansions: int = 3
    user_hint: Optional[str] = None

# ... (其他模型定义保持不变) ...
class HotspotRequest(BaseModel): keywords: List[str]; weights: Dict[str, float]
class GeminiGenerateRequest(BaseModel): hotspots: List[Dict[str, Any]]; series: str
class ManualLinkRequest(BaseModel): video_url: str; series: str
class IterateRequest(BaseModel): base_prompt_path: str; video_url: str; max_comments: int = 120; top_deltas: int = 3
class RefineRequest(BaseModel): prompt_path: str; feedback: str; model: str = "deepseek-chat"

# --- API Endpoints ---
@app.get("/", tags=["General"])
async def read_root(): return {"message": "Welcome to VideoAgent API!"}

# ... (认证, 热点, 迭代, Refine API保持不变) ...
from agent.utils.cookie_loader import generate_qr_code_data, poll_qr_code_status
from agent.hotspot.finder import find_hotspots as find_hotspots_logic
from agent.iterators.series_trace import iterate_series_with_trace
from agent.interactive.refiner import refine_prompt_json, save_refined_version, _json_diff
from agent.registry.store import register_prompt
@app.get("/api/auth/get-qr-code", tags=["Authentication"])
async def get_qr_code():
    try: data = generate_qr_code_data(); return JSONResponse(content=data)
    except Exception as e: raise HTTPException(status_code=500, detail=f"生成二维码失败: {e}")
@app.get("/api/auth/poll-qr-code", tags=["Authentication"])
async def poll_qr_status(qrcode_key: str):
    try: data = poll_qr_code_status(qrcode_key); return JSONResponse(content=data)
    except Exception as e: raise HTTPException(status_code=500, detail=f"轮询状态失败: {e}")
@app.post("/api/hotspot/search", tags=["Hotspot"])
async def search_hotspots(request: HotspotRequest):
    try:
        candidates = find_hotspots_logic(keywords=request.keywords, top_k=20, weights=request.weights)
        return JSONResponse(content=[vars(h) for h in candidates])
    except Exception as e: raise HTTPException(status_code=500, detail=f"搜索热点时发生错误: {e}")
@app.post("/api/hotspot/generate", tags=["Hotspot"])
async def generate_from_hotspot(request: GeminiGenerateRequest):
    results = []
    for hotspot in request.hotspots:
        try: results.append(analyze_video_and_generate_prompt(hotspot, request.series))
        except Exception as e: print(f"处理热点 '{hotspot.get('title')}' 失败: {e}")
    return JSONResponse(content={"results": results})
@app.post("/api/hotspot/generate-from-link", tags=["Hotspot"])
async def generate_from_link(request: ManualLinkRequest):
    try:
        hotspot = {"url": request.video_url, "title": "Manual Link"}
        result = analyze_video_and_generate_prompt(hotspot, request.series)
        return JSONResponse(content={"results": [result]})
    except Exception as e: raise HTTPException(status_code=500, detail=f"处理链接时发生错误: {e}")
@app.post("/api/iterate/from-video", tags=["Iteration"])
async def iterate_from_video(request: IterateRequest):
    try:
        new_path, report_path = iterate_series_with_trace(
            base_prompt_path=request.base_prompt_path, video_url=request.video_url,
            max_comments=request.max_comments, top_deltas=request.top_deltas
        )
        with open(new_path, 'r', encoding='utf-8') as f: new_content = json.load(f)
        return JSONResponse(content={"new_prompt_path": new_path, "report_path": report_path, "new_content": new_content})
    except Exception as e: raise HTTPException(status_code=500, detail=f"迭代视频时发生错误: {e}")
@app.get("/api/prompt/list", tags=["Prompt Management"])
async def list_prompts():
    files = glob.glob(os.path.join("prompts", "**", "*.json"), recursive=True); files = [f.replace("\\", "/") for f in files]
    return JSONResponse(content=sorted(files, reverse=True))
@app.post("/api/prompt/refine", tags=["Prompt Management"])
async def refine_prompt(request: RefineRequest):
    try:
        old, new, diffs = refine_prompt_json(base_json_path=request.prompt_path, user_feedback=request.feedback)
        new_path = save_refined_version(new, base_json_path=request.prompt_path)
        register_prompt(new, new_path, status="ready")
        return JSONResponse(content={"new_prompt_path": new_path, "new_content": new, "diffs": diffs})
    except Exception as e: raise HTTPException(status_code=500, detail=f"Refine失败: {e}")

# --- 新增：创意扩展 API ---
@app.post("/api/prompt/expand", tags=["Prompt Management"])
async def expand_prompt_api(request: ExpandRequest):
    '''对指定的Prompt进行创意扩展。'''
    try:
        results = expand_prompt(
            prompt_path=request.prompt_path,
            num_expansions=request.num_expansions,
            user_hint=request.user_hint
        )
        return JSONResponse(content={"results": results})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创意扩展失败: {e}")