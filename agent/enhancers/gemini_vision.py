from agent.utils.templates import load_template
# agent/enhancers/gemini_vision.py (带摘要版)
# -*- coding: utf-8 -*-
import os, re, time, hashlib, subprocess, json
from pathlib import Path
from typing import Dict, Any

import google.generativeai as genai
from agent.prompt.composer_json import compose_v1_json, save_v1_json
from agent.registry.store import register_prompt
from agent.config import Settings

def _init_gemini():
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        raise ValueError("请在 .env 文件中设置 GEMINI_API_KEY")
    genai.configure(api_key=gemini_key)

_init_gemini()

def download_video(url: str, output_dir: str = "outputs/videos") -> Path:
    # ... 此函数逻辑不变 ...
    print(f"📥 准备下载视频: {url}")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    bvid_match = re.search(r'(BV[a-zA-Z0-9_]+)', url)
    if not bvid_match: bvid = hashlib.md5(url.encode()).hexdigest()[:10]
    else: bvid = bvid_match.group(1)
    video_file = output_path / f"{bvid}.mp4"
    if video_file.exists() and video_file.stat().st_size > 1024 * 10:
        print(f"✅ 视频已存在: {video_file}"); return video_file
    bili_cookie = os.getenv("BILI_COOKIE", "")
    command = [
        "yt-dlp", "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best", "--merge-output-format", "mp4",
        "--add-header", f"Cookie: {bili_cookie}", "--add-header", "Referer: https://www.bilibili.com/",
        "--output", str(video_file), url
    ]
    print(f"⚙️ 正在执行下载命令: {' '.join(command)}")
    try:
        subprocess.run(command, check=True, capture_output=True)
        print(f"✅ 视频下载成功: {video_file}"); return video_file
    except subprocess.CalledProcessError as e:
        try: error_message = e.stderr.decode('gbk')
        except UnicodeDecodeError: error_message = e.stderr.decode('utf-8', errors='ignore')
        print(f"❌ 视频下载失败. yt-dlp 真实报错:\n--- \n{error_message}\n---")
        if "ffmpeg" in error_message.lower(): print("🚨 错误提示中包含 'ffmpeg'，请务必确认已正确安装并配置 FFmpeg。")
        raise RuntimeError(f"无法下载视频: {url}")
    except FileNotFoundError: raise RuntimeError("找不到 yt-dlp 命令。")

def analyze_video_and_generate_prompt(hotspot: Dict[str, Any], series: str) -> Dict[str, Any]:
    video_url = hotspot.get("url")
    if not video_url: raise ValueError("热点数据缺少 'url' 字段")

    video_path = download_video(video_url)
    print(f"🧠 正在使用 Gemini 分析视频: {video_path.name}...")
    model = genai.GenerativeModel('models/gemini-1.5-flash')
    video_file_obj = genai.upload_file(path=video_path)

    # --- 升级 Gemini Prompt，要求返回中文摘要 ---
    prompt_text = load_template("gemini_vision_system.txt", hotspot_title=hotspot.get("title", "N/A"))

    print("⏳ 等待 Gemini 文件处理完成..."); time.sleep(2)
    while video_file_obj.state.name == "PROCESSING":
        print('.', end='', flush=True); time.sleep(5)
        video_file_obj = genai.get_file(video_file_obj.name)

    if video_file_obj.state.name == "FAILED":
         raise ValueError(f"Gemini 文件处理失败: {video_file_obj.state}")
    print("\n✅ Gemini 文件处理完成，状态: ACTIVE")

    response = model.generate_content([prompt_text, video_file_obj], generation_config={"response_mime_type": "application/json"})
    gemini_result = json.loads(response.text)

    english_description = gemini_result.get("english_description", "No description provided.")
    chinese_title = gemini_result.get("chinese_title", "未命名视频")
    video_summary = gemini_result.get("video_summary", "无摘要信息。")

    print(f"\n📝 Gemini 分析结果 -> 中文摘要: {video_summary}")

    s = Settings()
    prompt_obj = compose_v1_json(
        topic=english_description, series=series, defaults=s.cfg,
        source="hotspot", chinese_name=chinese_title
    )
    prompt_obj["meta"]["video_summary"] = video_summary

    saved_path = save_v1_json(prompt_obj)
    register_prompt(prompt_obj, saved_path, status="ready")
    print(f"🚀 已根据 Gemini 分析结果生成 v1 Prompt: {saved_path}")

    return {"saved_path": saved_path, "prompt_content": prompt_obj, "video_summary": video_summary}