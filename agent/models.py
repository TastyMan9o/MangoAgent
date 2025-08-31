# -*- coding: utf-8 -*-
"""
agent/models.py
---------------------------------------------------------
用 Pydantic 定义本项目的核心数据结构：
  - Prompt 规范（PromptSpec）
  - 洞察文档（InsightDoc）
  - Delta/ICE 等
这是一个“类型声明 + 约束”的地方，方便我们在 IDE 中获得补全与校验。
---------------------------------------------------------
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Optional

class PromptBlocks(BaseModel):
    """
    Prompt 的分块（为了便于“局部 delta 合并”）
    """
    concept: str
    shot: str
    action: str
    lighting: str
    look: str
    audio: str
    timing: str
    constraints: str

class PromptMeta(BaseModel):
    source: str = Field(..., description="hotspot | series_iteration")
    topic: str
    series: Optional[str] = None
    created_at: str
    parent_prompt_id: Optional[str] = None
    notes: Optional[str] = None

class VeoParams(BaseModel):
    aspect_ratio: str = "16:9"
    person_generation: str = "dont_allow"
    negative_prompt: str

class PromptSpec(BaseModel):
    """
    一个完整的 Prompt 规范（文件会保存为 YAML）
    """
    name: str
    meta: PromptMeta
    veo_params: VeoParams
    prompt_blocks: PromptBlocks
    render: Dict[str, List[str]] = {"order": ["concept","shot","action","lighting","look","audio","timing","constraints"]}

# 以下是评论洞察侧的数据模型（后续会被 miners/comments.py 使用）
class PriorityICE(BaseModel):
    impact: float
    confidence: float
    effort: float
    score: float

class ActionDelta(BaseModel):
    type: str
    delta: str
    priority_ice: PriorityICE

class TopicInsight(BaseModel):
    label: str
    size: int
    sentiment_ratio: Dict[str, float]
    key_quotes: List[str]
    insight: str
    actions: List[ActionDelta]

class InsightDoc(BaseModel):
    topics: List[TopicInsight]
    global_recs: Dict[str, List[str]]
