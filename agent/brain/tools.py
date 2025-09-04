# agent/brain/tools.py (Corrected Final Version)
# -*- coding: utf-8 -*-
import glob
import os
import json
import requests
from typing import List, Dict, Any
from langchain_core.tools import tool

from agent.hotspot.finder import find_hotspots
from agent.enhancers.gemini_vision import analyze_video_and_generate_prompt
from agent.interactive.refiner import refine_prompt_json, save_refined_version
from agent.generators.veo_api import submit_veo_generation_task
from agent.config import Settings
from agent.iterators.series_trace import iterate_series_with_trace
from agent.tasks import flow_task_manager


@tool
def list_available_prompts() -> List[str]:
    """
    Lists all available prompt JSON files that can be used as a base for refinement or generation.
    Returns a list of file paths. Call this first if you need a `prompt_path` but don't know it.
    """
    print("🛠️ TOOL: Listing available prompts...")
    files = glob.glob(os.path.join("prompts", "generated", "*.json"), recursive=True)
    return [f.replace("\\", "/") for f in files]

@tool
def search_hotspot_videos(keywords: List[str]) -> List[Dict[str, Any]]:
    """
    Searches for popular videos on Bilibili based on a list of keywords.
    Returns a list of top video candidates with their titles, URLs, and stats.
    """
    print(f"🛠️ TOOL: Searching hotspots with keywords: {keywords}")
    s = Settings()
    weights = s.get("hotspot", "score_weights", default={"views":0.5,"likes":0.2,"comments":0.2,"danmaku":0.1})
    candidates = find_hotspots(keywords=keywords, top_k=5, weights=weights)
    return [vars(h) for h in candidates]

@tool
def analyze_video_from_url(video_url: str) -> Dict[str, Any]:
    """
    Analyzes a single video from a Bilibili URL and generates a new v1 prompt JSON file.
    Returns the path to the saved prompt file and a summary of the video.
    """
    print(f"🛠️ TOOL: Analyzing video from URL: {video_url}")
    hotspot = {"url": video_url, "title": "Direct URL Analysis"}
    series = "Agent Analysis Series"
    result = analyze_video_and_generate_prompt(hotspot, series)
    return result

@tool
def iterate_prompt_from_video_comments(base_prompt_path: str, video_url: str) -> Dict[str, Any]:
    """
    Automatically iterates a base prompt file using insights from the comments of a given Bilibili video URL.
    It fetches comments, analyzes them, and creates a new prompt version. Use this when a user asks to improve a prompt based on video feedback.
    """
    print(f"🛠️ TOOL: Iterating prompt '{base_prompt_path}' using comments from '{video_url}'")
    new_path, report_path = iterate_series_with_trace(
        base_prompt_path=base_prompt_path,
        video_url=video_url
    )
    return {"new_prompt_path": new_path, "report_path": report_path, "status": "success"}

@tool
def refine_existing_prompt(prompt_path: str, user_feedback: str) -> Dict[str, Any]:
    """
    Refines an existing prompt JSON file based on a user's specific natural language feedback.
    Use this when the user provides direct instructions like "make it more cinematic".
    """
    print(f"🛠️ TOOL: Refining prompt '{prompt_path}' with feedback: '{user_feedback}'")
    _, new_json, _ = refine_prompt_json(base_json_path=prompt_path, user_feedback=user_feedback)
    out_path = save_refined_version(new_json, base_json_path=prompt_path)
    return {"new_prompt_path": out_path, "status": "success"}

@tool
def submit_veo_generation(prompt_path: str) -> Dict[str, Any]:
    """
    Submits a generation task to the Veo 3 API using an existing prompt JSON file.
    """
    print(f"🛠️ TOOL: Submitting prompt '{prompt_path}' to Veo 3 API")
    import json
    with open(prompt_path, 'r', encoding='utf-8') as f:
        prompt_content = json.load(f)
    result = submit_veo_generation_task(prompt_content)
    return result

@tool
def generate_video_with_browser_automation(prompt_path: str, debugging_port: int = 9222, flow_url: str = "") -> Dict[str, Any]:
    """
    Submits a prompt from a file to the Flow web UI using browser automation.
    This is a NON-BLOCKING tool. It adds the task to a background queue and returns immediately.
    Use this to start the actual video generation.
    Args:
        prompt_path (str): The local path to the prompt JSON file.
        debugging_port (int): The port for the Chrome DevTools protocol. Defaults to 9222.
        flow_url (str, optional): The URL of the Flow page. If provided, a new tab will be opened. Defaults to "".
    """
    print(f"🛠️ TOOL: Submitting prompt '{prompt_path}' to the Flow generation queue...")
    
    # 验证文件路径
    if not os.path.exists(prompt_path):
        error_msg = f"Error: Prompt file not found at '{prompt_path}'"
        print(f"❌ {error_msg}")
        return {"success": False, "message": error_msg}
    
    try:
        # 读取并验证JSON文件
        print(f"📖 Reading prompt file: {prompt_path}")
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt_obj = json.load(f)

        # 验证JSON结构
        if not isinstance(prompt_obj, dict):
            error_msg = "Error: Invalid JSON structure - expected object"
            print(f"❌ {error_msg}")
            return {"success": False, "message": error_msg}

        prompt_text = json.dumps(prompt_obj, indent=2, ensure_ascii=False)
        print(f"📝 Prompt content length: {len(prompt_text)} characters")

        # 检查FlowTaskManager是否已初始化
        if not hasattr(flow_task_manager, 'task_queue'):
            error_msg = "Error: FlowTaskManager not properly initialized"
            print(f"❌ {error_msg}")
            return {"success": False, "message": error_msg}

        # 提交任务到队列
        print(f"📥 Adding task to Flow queue...")
        task_id = flow_task_manager.add_task(
            prompt_content=prompt_text,
            debugging_port=debugging_port,
            flow_url=flow_url
        )
        print(f"✅ Task added successfully with ID: {task_id}")

        return {
            "success": True,
            "message": f"✅ 任务已成功提交到后台队列！任务ID: {task_id}. The video is being generated in the background.",
            "task_id": task_id,
            "prompt_path": prompt_path,
            "status": "queued"
        }
    except json.JSONDecodeError as e:
        error_msg = f"Error: Invalid JSON in prompt file: {e}"
        print(f"❌ {error_msg}")
        return {"success": False, "message": error_msg}
    except Exception as e:
        error_msg = f"Error submitting task to Flow queue: {e}"
        print(f"❌ {error_msg}")
        print(f"🔍 Exception type: {type(e).__name__}")
        import traceback
        print(f"📋 Traceback: {traceback.format_exc()}")
        return {"success": False, "message": error_msg}

@tool
def get_flow_generation_status() -> Dict[str, Any]:
    """
    Checks the status of the background Flow video generation queue.
    Returns the number of tasks currently queued and running.
    Use this when the user asks about the progress of video generation.
    """
    print("🛠️ TOOL: Checking Flow generation status...")
    try:
        # 尝试从环境变量获取API端口，如果没有设置则使用默认值8001
        api_port = os.getenv("API_PORT", "8001")
        
        # 构建API URL
        api_url = f"http://127.0.0.1:{api_port}/api/flow/queue_status"
        print(f"🔗 Checking Flow status at: {api_url}")
        
        response = requests.get(api_url, 
                              proxies={"http": None, "https": None}, 
                              timeout=10)
        response.raise_for_status()
        
        status_data = response.json()
        print(f"📊 Flow status response: {status_data}")
        return status_data
        
    except requests.exceptions.Timeout:
        error_msg = "Timeout: API server not responding"
        print(f"❌ {error_msg}")
        return {"success": False, "message": error_msg}
    except requests.exceptions.ConnectionError:
        error_msg = f"Connection Error: Cannot connect to API server at port {api_port}"
        print(f"❌ {error_msg}")
        return {"success": False, "message": error_msg}
    except Exception as e:
        error_msg = f"Error fetching queue status: {e}"
        print(f"❌ {error_msg}")
        return {"success": False, "message": error_msg}

available_tools = [
    list_available_prompts,
    search_hotspot_videos,
    analyze_video_from_url,
    iterate_prompt_from_video_comments,
    refine_existing_prompt,
    submit_veo_generation,
    generate_video_with_browser_automation,
    get_flow_generation_status,
]
