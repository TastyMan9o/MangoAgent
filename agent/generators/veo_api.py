# agent/generators/veo_api.py
# -*- coding: utf-8 -*-
import os
import time
import json
from typing import Dict, Any, Union

def submit_veo_generation_task(prompt_content: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    (模拟) 提交任务到 Veo 3 API。
    """
    api_key = os.getenv("VEO_API_KEY")
    if not api_key:
        raise ValueError("请在 .env 文件中设置 VEO_API_KEY")

    # 处理字符串输入
    if isinstance(prompt_content, str):
        try:
            prompt_content = json.loads(prompt_content)
        except json.JSONDecodeError:
            raise ValueError("Prompt内容不是有效的JSON格式")

    print(f"🚀 [Veo 3 API] 正在提交任务...")
    print(f"   Prompt 主题: {prompt_content.get('meta', {}).get('topic', 'N/A')}")

    # --- 模拟API调用 ---
    time.sleep(2) 
    task_id = f"veo_task_{int(time.time())}"
    print(f"✅ [Veo 3 API] 任务提交成功! 任务ID: {task_id}")

    return {
        "success": True,
        "message": f"成功提交到 Veo 3 API！任务ID为 {task_id}，请稍后查看结果。",
        "task_id": task_id
    }
