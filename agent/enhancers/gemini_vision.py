# agent/enhancers/gemini_vision.py (v2 - Robust Error Handling)
# -*- coding: utf-8 -*-
import os
import re
import time
import hashlib
import subprocess
import json
from pathlib import Path
from typing import Dict, Any

import google.generativeai as genai
from agent.prompt.composer_json import compose_v1_json, save_v1_json
from agent.registry.store import register_prompt
from agent.config import Settings


def _init_gemini():
    from agent.utils.key_rotator import get_next_gemini_key
    gemini_key = get_next_gemini_key()
    if not gemini_key:
        raise ValueError("GEMINI_API_KEYS not set in .env file")
    genai.configure(api_key=gemini_key)


_init_gemini()


def download_video(url: str, output_dir: str = "outputs/videos") -> Path:
    """使用 yt-dlp 下载视频，并返回文件路径"""
    # ... (此函数保持不变)
    print(f"📥 准备下载视频: {url}")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    bvid_match = re.search(r'(BV[a-zA-Z0-9_]+)', url)
    bvid = bvid_match.group(1) if bvid_match else hashlib.md5(url.encode()).hexdigest()[:10]
    video_file = output_path / f"{bvid}.mp4"
    if video_file.exists() and video_file.stat().st_size > 1024 * 10:
        print(f"✅ 视频已存在: {video_file}")
        return video_file
    bili_cookie = os.getenv("BILI_COOKIE", "")
    command = ["yt-dlp", "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best", "--merge-output-format", "mp4",
               "--add-header", f"Cookie:{bili_cookie}", "--add-header", "Referer:https://www.bilibili.com/", "--output",
               str(video_file), url]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"✅ 视频下载成功: {video_file}")
        return video_file
    except subprocess.CalledProcessError as e:
        print(f"❌ 视频下载失败. yt-dlp 报错:\n--- \n{e.stderr}\n---")
        raise RuntimeError(f"无法下载视频: {url}")
    except FileNotFoundError:
        raise RuntimeError("找不到 yt-dlp 命令。请确保已安装。")


def analyze_video_and_generate_prompt(hotspot: Dict[str, Any], series: str) -> Dict[str, Any]:
    video_url = hotspot.get("url")
    if not video_url:
        raise ValueError("热点数据缺少 'url' 字段")

    video_path = download_video(video_url)
    print(f"🧠 正在使用 Gemini 分析视频: {video_path.name}...")
    model = genai.GenerativeModel('models/gemini-2.5-flash')

    video_file_obj = genai.upload_file(path=video_path)

    prompt_text = f'''
    Analyze the provided video. Return a JSON object with three keys: "english_description", "chinese_title", and "video_summary".
    - "english_description": A rich, descriptive paragraph in English about the video's visual elements.
    - "chinese_title": A short, descriptive, filename-friendly title in Chinese, under 15 characters.
    - "video_summary": A concise, one-sentence summary of the video's content in Chinese.
    Original video title for context: "{hotspot.get('title', 'N/A')}"
    '''

    print("⏳ 等待 Gemini 文件处理完成...")
    while video_file_obj.state.name == "PROCESSING":
        time.sleep(5)
        video_file_obj = genai.get_file(video_file_obj.name)

    if video_file_obj.state.name == "FAILED":
        raise ValueError(f"Gemini 文件处理失败: {video_file_obj.state}")
    print("\n✅ Gemini 文件处理完成，状态: ACTIVE")

    response = model.generate_content([prompt_text, video_file_obj],
                                      generation_config={"response_mime_type": "application/json"})

    # --- 这里是关键的健壮性修改 ---
    try:
        gemini_result = json.loads(response.text)
    except json.JSONDecodeError as e:
        print(f"❌ Gemini 返回的不是有效的JSON！错误: {e}")
        print("--- Gemini 原始回复 ---")
        print(response.text)
        print("-----------------------")
        # 返回一个清晰的错误信息，而不是让整个工具崩溃
        return {"error": "Gemini did not return valid JSON.", "raw_response": response.text}
    # ---------------------------

    english_description = gemini_result.get("english_description", "No description provided.")
    chinese_title = gemini_result.get("chinese_title", "未命名视频")
    video_summary = gemini_result.get("video_summary", "无摘要信息。")

    print(f"\n📝 Gemini 分析结果 -> 中文摘要: {video_summary}")

    s = Settings()
    prompt_obj = compose_v1_json(
        topic=english_description,
        series=series,
        defaults=s.cfg,
        source="hotspot",
        chinese_name=chinese_title
    )
    prompt_obj["meta"]["video_summary"] = video_summary

    saved_path = save_v1_json(prompt_obj)
    register_prompt(prompt_obj, saved_path, status="ready")
    print(f"🚀 已根据 Gemini 分析结果生成 v1 Prompt: {saved_path}")

    return {"saved_path": saved_path, "prompt_content": prompt_obj, "video_summary": video_summary}