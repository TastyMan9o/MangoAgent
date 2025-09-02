from agent.utils.key_rotator import get_next_gemini_key
# agent/brain/core.py (Hardened)
# -*- coding: utf-8 -*-
import os
import operator
from typing import TypedDict, Annotated, List
from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_deepseek import ChatDeepSeek
from agent.brain.tools import available_tools

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    llm_provider: str
    model_name: str

tool_node = ToolNode(available_tools)

def call_model(state: AgentState):
    provider = state["llm_provider"]
    model_name = state["model_name"]

    if provider == "Gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key: raise ValueError("GEMINI_API_KEY is not set")
        llm = ChatGoogleGenerativeAI(model=model_name, temperature=0, google_api_key=api_key)
    elif provider == "DeepSeek":
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key: raise ValueError("DEEPSEEK_API_KEY is not set")
        llm = ChatDeepSeek(model=model_name, temperature=0, api_key=api_key)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")

    llm_with_tools = llm.bind_tools(available_tools or [])
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}

def should_continue(state: AgentState):
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "continue"
    return "end"

graph = StateGraph(AgentState)
graph.add_node("agent", call_model)
graph.add_node("action", tool_node)
graph.set_entry_point("agent")
graph.add_conditional_edges("agent", should_continue, {"continue": "action", "end": END})
graph.add_edge("action", "agent")
agent_brain = graph.compile()
