# agent/utils/templates.py
    # -*- coding: utf-8 -*-
    import os

    TEMPLATE_DIR = os.path.join("prompts", "system_templates")

    def load_template(template_name: str, **kwargs) -> str:
file_path = os.path.join(TEMPLATE_DIR, template_name)
if not os.path.exists(file_path):
    raise FileNotFoundError(f"模板文件未找到: {file_path}")

with open(file_path, 'r', encoding='utf-8') as f:
    template_str = f.read()

if kwargs:
    return template_str.format(**kwargs)
return template_str