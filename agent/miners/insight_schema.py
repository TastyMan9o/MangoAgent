# -*- coding: utf-8 -*-
"""
agent/miners/insight_schema.py
===========================================================
作用：
  定义“评论洞察”的结构（与之前你跑通的 JSON 结构一致/兼容），
  以便后续把你已有挖掘模块的输出直接喂给合并策略或 Graph。
"""

from typing import List, Dict
from pydantic import BaseModel, Field

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
