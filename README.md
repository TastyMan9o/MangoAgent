# 🤖 VideoAgent: 自动化视频灵感助手

这是一个基于AI的自动化工具，旨在通过分析B站视频的热点和评论，智能生成和迭代用于文生视频模型的 Prompt。

## ✨ 核心功能

- **🧠 AI大脑**: 基于LangGraph的智能代理，支持Gemini和DeepSeek模型
- **🔥 热点发现**: 自动搜索B站热门视频，并采用可定制化的热度算法进行排序
- **🎬 AI视频分析**: 集成Gemini 1.5多模态模型，通过分析视频内容，自动生成高质量的英文Prompt和中文标题
- **💬 评论洞察与迭代**: 自动抓取指定视频的评论区，利用DeepSeek模型提炼视觉改进建议，实现Prompt的版本迭代
- **✍️ 交互式优化**: 通过自然语言反馈优化Prompt
- **💡 创意扩展**: 基于现有Prompt生成多个创意变体
- **🎬 视频生成**: 支持Flow浏览器自动化和Veo 3 API两种方式
- **⚙️ 端口设置**: 支持灵活配置API端口和代理设置，适配不同的网络环境
- **📋 批量生成**: 支持同时选择多个Prompt文件进行批量视频生成，提高工作效率
- **🔄 流式输出**: 实时显示AI思考过程和工具调用，支持详细/简洁模式切换

## 🧱 项目结构（标准化）

```text
MangoAgent/
  ├─ agent/                 # 业务核心代码（按领域分层）
  │   ├─ brain/             # Agent大脑与工具
  │   ├─ collectors/        # 外部数据采集
  │   ├─ enhancers/         # 能力增强模块（多模态、扩展）
  │   ├─ generators/        # 生成器（Flow、Veo等）
  │   ├─ graph/             # 流程图与状态管理
  │   ├─ hotspot/           # 热点发现逻辑
  │   ├─ interactive/       # 交互优化
  │   ├─ iterators/         # 版本迭代
  │   ├─ miners/            # 评论挖掘、洞察
  │   ├─ prompt/            # Prompt编排与Schema
  │   ├─ registry/          # 索引与注册
  │   ├─ reports/           # 报表输出
  │   └─ utils/             # 工具方法
  ├─ cli/                   # 命令行入口
  ├─ config/                # 配置（环境、日志）
  ├─ prompts/               # 生成产物与样例
  ├─ tests/                 # 单元/集成测试（新增）
  ├─ docs/                  # 文档（新增）
  ├─ scripts/               # 运维与启动脚本（新增）
  ├─ app.py                 # Streamlit 前端入口
  ├─ main.py                # FastAPI 后端入口
  ├─ pyproject.toml         # 统一工具链配置（新增）
  ├─ requirements.txt       # 运行依赖
  └─ README.md
```

> 本次标准化不移动现有模块，以零破坏为原则，仅新增通用工程文件与目录。

## 📚 文档

- [新功能说明](docs/NEW_FEATURES.md) - 端口设置和批量生成功能的详细说明
- [使用示例](docs/USAGE_EXAMPLES.md) - 实际使用场景和配置示例
- [流式输出说明](docs/STREAMING_OUTPUT.md) - AI思考过程实时展示功能详解
- [API文档](http://localhost:8001/docs) - 后端API接口文档（启动后端后访问）

## 🚀 如何启动

本项目包含一个后端API服务和一个前端UI，需要同时启动。

### 方式一：一键启动 (推荐)

直接双击项目根目录下的 `run_app.bat` 文件。

它会自动打开两个终端窗口，分别启动后端和前端服务。

### 方式二：手动启动

如果你想分别控制，可以打开两个终端窗口，按顺序执行以下命令。

**1. 在第一个终端启动后端服务:**
```powershell
# (可选) 为后端设置代理，用于访问Gemini2
$env:HTTPS_PROXY="[http://127.0.0.1:7890](http://127.0.0.1:7890)"

# 启动FastAPI服务于8001端口
uvicorn main:app --reload --port 8001
```

**2. 在第二个终端启动前端UI:**
```powershell
# 启动Streamlit应用
streamlit run app.py
```
启动后，浏览器会自动打开 `http://localhost:8501`。

## ⚙️ 技术栈

- **后端**: FastAPI, Uvicorn, LangGraph
- **前端**: Streamlit
- **AI模型**: Google Gemini 1.5, DeepSeek
- **数据采集**: requests, yt-dlp, browser-cookie3
- **核心库**: pandas, qrcode