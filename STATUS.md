# 项目进度表（持续更新）

| 模块 | 路径 | 状态 |
|---|---|---|
| 工程骨架（基础） | 多处 | ✅ |
| 配置加载（.env+YAML） | `agent/config.py` | ✅ |
| 工具 IO | `agent/utils/io.py` | ✅ |
| 英文 JSON Prompt 标准 | `agent/prompt/schema_json.py` | ✅ |
| v1 生成（小模型） | `agent/prompt/composer_json.py` | ✅ |
| 本地人工迭代（refine） | `agent/interactive/refiner.py` | ✅ |
| 热点发现（auto/manual） | `agent/hotspot/finder.py` | ✅（示例数据） |
| 版本注册索引 | `agent/registry/store.py` | ✅ |
| CLI（compose_json/hotspot/refine） | `cli/agent.py` | ✅ |
| Graph 编排 | `agent/graph/*` | ⏳ |
| B站采集器（三层降级） | `agent/collectors/bilibili.py` | ⏳ |
| 评论挖掘/合并策略 | `agent/miners/*`, `agent/iterators/*` | ⏳ |
| REST 接口 / UI | 待定 | ⏳ |

| **Graph 编排（两条线）** | `agent/graph/*` | ✅（本轮新增） |
| **Graph CLI** | `cli/agent_graph.py` | ✅（本轮新增） |
| 迭代合并策略（基础） | `agent/iterators/merge_policy.py` | ✅（本轮新增） |
| 洞察 Schema（对接你现有挖掘） | `agent/miners/insight_schema.py` | ✅（本轮新增） |

| B 站采集器（三层降级+Cookie） | `agent/collectors/bilibili.py` | ✅ 本轮新增 |
| 评论挖掘（抓评→LLM 严格 JSON 洞察） | `agent/miners/comments.py` | ✅ 本轮新增 |
| 系列迭代（采集→洞察→合并→vN+1） | `agent/iterators/series.py` | ✅ 本轮新增 |
| 依赖升级（langgraph==0.6.6） | `requirements.txt` | ✅ 已升级 |

| 系列自动迭代（独立 CLI） | `cli/series_cli.py` | ✅ 新增 |
| 系列自动迭代（Graph 第三条线） | `agent/graph/pipeline_series.py`, `cli/agent_graph_series.py` | ✅ 新增 |

| 系列迭代（带溯源报告） | `agent/iterators/series_trace.py`, `agent/reports/trace_report.py`, `cli/series_trace_cli.py` | ✅ 新增 |
