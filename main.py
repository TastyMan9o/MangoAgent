# main.py (Final, Streaming & Parallel Version)
# -*- coding: utf-8 -*-
import sys
import asyncio
import os
import glob
import json
import traceback
import time
import logging
from typing import List, Dict, Any, Optional, Union

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import find_dotenv, set_key

# --- Project imports ---
from agent.generators.flow_automator import generate_video_in_flow
from agent.utils.cookie_loader import generate_qr_code_data, poll_qr_code_status
from agent.hotspot.finder import find_hotspots as find_hotspots_logic
from agent.enhancers.gemini_vision import analyze_video_and_generate_prompt
from agent.iterators.series_trace import iterate_series_with_trace
from agent.interactive.refiner import refine_prompt_json, save_refined_version, _json_diff
from agent.registry.store import register_prompt
from agent.config import Settings
from agent.enhancers.prompt_expander import expand_prompt
from agent.generators.veo_api import submit_veo_generation_task
from agent.brain.core import agent_brain
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage
from agent.tasks import flow_task_manager

# --- Logging & App Setup ---
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("videoagent")

app = FastAPI(title="VideoAgent API", version="3.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------- Pydantic Models --------------------
class ApiKeys(BaseModel):
    deepseek_api_key: Optional[str] = None
    gemini_api_keys: Optional[str] = None
    veo_api_key: Optional[str] = None

class UpdateApiKeysRequest(BaseModel):
    deepseek_api_key: Optional[str] = None
    gemini_api_keys: Optional[str] = None
    veo_api_key: Optional[str] = None

class Message(BaseModel):
    role: str
    content: Union[str, List[Any]]
    tool_calls: Optional[List[Dict[str, Any]]] = None

class AgentQuery(BaseModel):
    messages: List[Message]
    llm_provider: str
    model_name: str

class GenerateVideoRequest(BaseModel):
    prompt_content: str
    flow_url: Optional[str] = None
    debugging_port: Optional[int] = None

class HotspotRequest(BaseModel):
    keywords: List[str]
    weights: Dict[str, float]

class VeoGenerateRequest(BaseModel):
    prompt_content: Dict[str, Any]

class ManualLinkRequest(BaseModel):
    video_url: str
    series: str = "Manual Input Series"

class IterateRequest(BaseModel):
    base_prompt_path: str
    video_url: str

class RefineRequest(BaseModel):
    prompt_path: str
    feedback: str

class ExpandRequest(BaseModel):
    prompt_path: str
    num_expansions: int = 3
    user_hint: Optional[str] = None

# -------------------- Helpers --------------------
def mask_key(key: Optional[str]) -> Optional[str]:
    if not key or len(key) < 8:
        return key
    return f"{key[:5]}...{key[-4:]}"

def _safe_text_from_ai_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [c.get("text") for c in content if isinstance(c, dict) and isinstance(c.get("text"), str)]
        return "\n".join(parts) if parts else str(content)
    return str(content)

def convert_messages_to_langchain_format(messages: List[Message]) -> List[BaseMessage]:
    lc_messages: List[BaseMessage] = []
    system_prompt_content = "You are VideoAgent Brain. Answer concisely and call tools when necessary."
    system_prompt_path = os.path.join("agent", "brain", "system_prompt.md")
    try:
        if os.path.exists(system_prompt_path):
            with open(system_prompt_path, "r", encoding="utf-8") as f:
                system_prompt_content = f.read()
    except Exception as e:
        log.warning(f"system_prompt.md read failed: {e}")
    lc_messages.append(SystemMessage(content=system_prompt_content))
    for msg in messages:
        if msg.role == "user":
            lc_messages.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant" and isinstance(msg.content, str):
            lc_messages.append(AIMessage(content=msg.content))
    return lc_messages

# -------------------- API Endpoints --------------------
@app.get("/api/health")
async def health():
    return {"ok": True, "ts": time.time()}

@app.get("/api/auth/get-qr-code", tags=["Authentication"])
async def get_qr_code():
    try:
        data = generate_qr_code_data()
        return JSONResponse(content=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成二维码失败: {e}")

@app.get("/api/auth/poll-qr-code", tags=["Authentication"])
async def poll_qr_status(qrcode_key: str):
    try:
        data = poll_qr_code_status(qrcode_key)
        return JSONResponse(content=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"轮询状态失败: {e}")

@app.get("/api/keys/get", tags=["API Management"], response_model=ApiKeys)
async def get_api_keys():
    s = Settings()
    gemini_keys_str = os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", ""))
    return ApiKeys(
        deepseek_api_key=mask_key(s.deepseek_api_key),
        gemini_api_keys=gemini_keys_str,
        veo_api_key=mask_key(os.getenv("VEO_API_KEY"))
    )

@app.post("/api/keys/update", tags=["API Management"])
async def update_api_keys(keys: UpdateApiKeysRequest):
    try:
        dotenv_path = find_dotenv()
        if not dotenv_path:
            with open(".env", "w"):
                pass
            dotenv_path = find_dotenv()
        if keys.deepseek_api_key:
            set_key(dotenv_path, "DEEPSEEK_API_KEY", keys.deepseek_api_key)
        if keys.veo_api_key:
            set_key(dotenv_path, "VEO_API_KEY", keys.veo_api_key)
        if keys.gemini_api_keys is not None:
            key_list = [k.strip() for k in keys.gemini_api_keys.splitlines() if k.strip()]
            set_key(dotenv_path, "GEMINI_API_KEYS", ",".join(key_list))
            set_key(dotenv_path, "GEMINI_API_KEY", "")
        return {"success": True, "message": "API密钥已成功更新！"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新 .env 文件时出错: {e}")

@app.get("/api/prompt/list", tags=["Prompt Management"])
async def list_prompts():
    try:
        files = glob.glob(os.path.join("prompts", "**", "*.json"), recursive=True)
        files_with_mtime = []
        for f in files:
            try:
                files_with_mtime.append((f.replace("\\\\", "/"), os.path.getmtime(f)))
            except OSError:
                continue
        sorted_files = sorted(files_with_mtime, key=lambda x: x[1], reverse=True)
        return JSONResponse(content=[f[0] for f in sorted_files])
    except Exception as e:
        log.error(f"Error listing prompts: {e}")
        raise HTTPException(status_code=500, detail="Failed to list prompts.")

@app.delete("/api/prompt/delete", tags=["Prompt Management"])
async def delete_prompt(request: Request):
    try:
        body = await request.json()
        prompt_path = body.get("prompt_path")
        if not prompt_path:
            raise HTTPException(status_code=400, detail="未提供 prompt_path")
        base_path = os.path.abspath("prompts")
        target_path = os.path.abspath(prompt_path)
        if os.path.commonpath([base_path]) != os.path.commonpath([base_path, target_path]):
             raise HTTPException(status_code=403, detail="禁止删除该目录之外的文件")
        if os.path.exists(target_path):
            prompt_id_to_delete = None
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    prompt_data = json.load(f)
                    prompt_id_to_delete = prompt_data.get("name")
            except Exception:
                pass
            os.remove(target_path)
            index_path = os.path.join("prompts", "index.json")
            if os.path.exists(index_path):
                try:
                    with open(index_path, "r+", encoding="utf-8") as f:
                        index_data = json.load(f)
                        key_to_remove = None
                        if prompt_id_to_delete and prompt_id_to_delete in index_data:
                            key_to_remove = prompt_id_to_delete
                        else:
                            normalized_path = prompt_path.replace("\\\\", "/")
                            for key, value in index_data.items():
                                if value.get("path") == normalized_path:
                                    key_to_remove = key
                                    break
                        if key_to_remove in index_data:
                            del index_data[key_to_remove]
                            f.seek(0)
                            f.truncate()
                            json.dump(index_data, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    log.warning(f"从 index.json 更新失败: {e}")
            return JSONResponse(content={"success": True, "message": f"Prompt '{os.path.basename(target_path)}' 已被删除。"})
        else:
            raise HTTPException(status_code=404, detail="文件未找到")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/hotspot/search", tags=["Hotspot"])
async def search_hotspots(request: HotspotRequest):
    try:
        candidates = find_hotspots_logic(keywords=request.keywords, top_k=20, weights=request.weights)
        return JSONResponse(content=[vars(h) for h in candidates])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索热点时发生错误: {e}")

@app.post("/api/hotspot/generate-from-link", tags=["Hotspot"])
async def generate_from_link(request: ManualLinkRequest):
    try:
        hotspot = {"url": request.video_url, "title": "Manual Link"}
        result = analyze_video_and_generate_prompt(hotspot, request.series)
        return JSONResponse(content={"results": [result]})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理链接时发生错误: {e}")

@app.post("/api/iterate/from-video", tags=["Iteration"])
async def iterate_from_video(request: IterateRequest):
    try:
        base_content = json.load(open(request.base_prompt_path, 'r', encoding='utf-8'))
        new_path, report_path = iterate_series_with_trace(
            base_prompt_path=request.base_prompt_path, video_url=request.video_url
        )
        with open(new_path, 'r', encoding='utf-8') as f:
            new_content = json.load(f)
        diffs = _json_diff(base_content, new_content)
        return JSONResponse(
            content={"new_prompt_path": new_path, "report_path": report_path,
                     "new_content": new_content, "diffs": diffs}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"迭代视频时发生错误: {e}")

@app.post("/api/prompt/refine", tags=["Prompt Management"])
async def refine_prompt_endpoint(request: RefineRequest):
    try:
        old, new, diffs = refine_prompt_json(base_json_path=request.prompt_path, user_feedback=request.feedback)
        new_path = save_refined_version(new, base_json_path=request.prompt_path)
        register_prompt(new, new_path, status="ready")
        return JSONResponse(content={"new_prompt_path": new_path, "new_content": new, "diffs": diffs})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Refine失败: {e}")

@app.post("/api/prompt/expand", tags=["Prompt Management"])
async def expand_prompt_api(request: ExpandRequest):
    try:
        results = expand_prompt(prompt_path=request.prompt_path,
                                num_expansions=request.num_expansions,
                                user_hint=request.user_hint)
        return JSONResponse(content={"results": results})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创意扩展失败: {e}")

@app.post("/api/generate/video", tags=["Video Generation"])
async def generate_video(request: GenerateVideoRequest):
    try:
        result = await asyncio.to_thread(
            generate_video_in_flow,
            request.prompt_content,
            request.debugging_port,
            request.flow_url
        )
        if result.get("success"):
            return JSONResponse(content=result)
        raise HTTPException(status_code=500, detail=result.get("message", "未知错误"))
    except Exception as e:
        tb = traceback.format_exc(limit=3)
        log.error(f"generate_video failed: {e}\\n{tb}")
        return JSONResponse(status_code=500, content={"error": str(e), "traceback": tb})

@app.post("/api/generate/veo", tags=["Video Generation"])
async def generate_with_veo(request: VeoGenerateRequest):
    try:
        result = submit_veo_generation_task(request.prompt_content)
        if result["success"]:
            return JSONResponse(content=result)
        else:
            raise HTTPException(status_code=500, detail=result.get("message", "未知错误"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"调用 Veo 3 API 时发生错误: {e}")

@app.on_event("startup")
async def startup_event():
    log.info("Application startup: Starting FlowTaskManager worker...")
    flow_task_manager.start_worker()

@app.get("/api/flow/queue_status", tags=["Video Generation"])
async def get_flow_queue_status():
    """获取当前Flow任务队列的状态"""
    with flow_task_manager.lock:
        return {
            "queued_tasks": len(flow_task_manager.task_queue),
            "running_tasks": len(flow_task_manager.running_tasks),
            "running_tasks_details": list(flow_task_manager.running_tasks.values())
        }

@app.post("/api/agent/chat_stream", tags=["Agent Brain"])
async def agent_chat_stream(request: AgentQuery):
    """流式返回Agent的思考和工具调用过程"""
    async def stream_generator():
        try:
            lc_messages = convert_messages_to_langchain_format(request.messages)
            inputs = {
                "messages": lc_messages,
                "llm_provider": request.llm_provider,
                "model_name": request.model_name
            }
            log.info(f"STREAM /api/agent/chat_stream provider={request.llm_provider} model={request.model_name}")

            async for event in agent_brain.astream_events(inputs, version="v1"):
                kind = event["event"]

                if kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if chunk.content:
                        yield f"data: {json.dumps({'type': 'thought', 'content': chunk.content})}\\n\\n"

                elif kind == "on_tool_start":
                    tool_name = event["name"]
                    tool_args = event["data"].get("input", {})
                    yield f"data: {json.dumps({'type': 'tool_start', 'tool_name': tool_name, 'tool_args': tool_args})}\\n\\n"

                elif kind == "on_tool_end":
                    tool_name = event["name"]
                    tool_output = event["data"].get("output", "")
                    if not isinstance(tool_output, (str, int, float, bool, list, dict, type(None))):
                        tool_output = str(tool_output)
                    yield f"data: {json.dumps({'type': 'tool_end', 'tool_name': tool_name, 'output': tool_output})}\\n\\n"

            yield f"data: {json.dumps({'type': 'done'})}\\n\\n"

        except Exception as e:
            tb = traceback.format_exc(limit=3)
            log.error(f"agent_chat_stream failed: {e}\\n{tb}")
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\\n\\n"

    return StreamingResponse(stream_generator(), media_type="text/event-stream")
