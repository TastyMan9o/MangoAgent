# agent/enhancers/prompt_expander.py (最终稳定版)
# -*- coding: utf-8 -*-
import os
import re
import json
from typing import List, Dict, Any, Optional

import google.generativeai as genai
from agent.interactive.refiner import _read_json
from agent.registry.store import register_prompt
from agent.utils.io import write_json, ensure_dir


def _init_gemini():
    from agent.utils.key_rotator import get_next_gemini_key
    gemini_key = get_next_gemini_key()
    if not gemini_key:
        raise ValueError("GEMINI_API_KEYS not set in .env file")
    genai.configure(api_key=gemini_key)


_init_gemini()


def _construct_expansion_prompt(base_prompt_str: str, user_hint: Optional[str] = None) -> str:
    common_instructions =f"""
You are a controlled prompt editor. Your task is to generate ONE subtle variation of the following JSON prompt.

# RULES
- The variation must stay **faithful to the original structure and concept**.
- You may only change **theme** (e.g. color scheme, atmosphere keywords within the same category) 
  or **characters/subjects** (e.g. replacing a cat with another cat breed, or replacing a person/animal with a similar role).
- Do NOT change the overall style, mood, camera setup, lighting scheme, or scene composition.
- Do NOT add or remove fields. The JSON structure and key names must remain exactly the same.
- Modify at most **2–3 small details**. Changes must be minimal but distinct (e.g. change subject type, adjust palette accent, swap object variant).
- If a requested change would violate these constraints, skip it and keep the original value.

# OUTPUT
- You MUST return ONLY the raw JSON object, without any explanation, text, or markdown fences.

BASE PROMPT:
{base_prompt_str}
"""

    if user_hint:
        return f'''{common_instructions}

        Generate a new creative variation based on this specific user hint: "{user_hint}"
        '''
    else:
        return f'''{common_instructions}

        Generate a new creative variation with a significantly different visual style, subject, or mood. Be imaginative.
        '''


def expand_prompt(
        prompt_path: str,
        num_expansions: int,
        user_hint: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    对一个基础Prompt进行N次创意扩展。
    """
    print(f"🚀 开始创意扩展任务，基础Prompt: {prompt_path}, 扩展数量: {num_expansions}")
    base_prompt_obj = _read_json(prompt_path)
    base_prompt_str = json.dumps(base_prompt_obj, ensure_ascii=False, indent=2)

    model = genai.GenerativeModel('models/gemini-2.5-flash')
    generated_prompts = []

    for i in range(num_expansions):
        print(f"  - 正在生成第 {i + 1}/{num_expansions} 个变体...")
        prompt_text = _construct_expansion_prompt(base_prompt_str, user_hint)

        try:
            response = model.generate_content(
                prompt_text,
                generation_config={"response_mime_type": "application/json"}
            )
            new_prompt_obj = json.loads(response.text)

            # --- 文件名处理 ---
            original_name_stem = re.sub(r'_v\d+$', '', base_prompt_obj.get("name", "untitled"))
            new_name = f"{original_name_stem}_expanded_{i + 1}"
            new_prompt_obj["name"] = new_name

            # --- 保存与注册 ---
            save_path = os.path.join("prompts", "generated", f"{new_name}.json")
            ensure_dir(os.path.dirname(save_path))
            write_json(save_path, new_prompt_obj)
            register_prompt(new_prompt_obj, save_path, status="ready")

            generated_prompts.append({
                "saved_path": save_path,
                "prompt_content": new_prompt_obj
            })
            print(f"  - ✅ 已保存变体: {save_path}")

        except Exception as e:
            print(f"  - ❌ 生成第 {i + 1} 个变体时失败: {e}")
            continue

    return generated_prompts