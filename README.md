# 🤖 MangoAgent

AI 驱动的 B 站热点分析与评论洞察系统，自动生成与迭代适配文生视频（Text-to-Video）的高质量 Prompt。内置 FastAPI 后端与 Streamlit 控制台，支持 Gemini 与 DeepSeek，提供一键启动与标准化工程结构。

> **English TL;DR**: AI-powered Bilibili hotspot mining + comment insights → generate/iterate production-ready prompts for text-to-video workflows. FastAPI backend + Streamlit console, with big-tech style project scaffolding.

---

## ✨ 核心功能

### 🔥 热点发现与视频分析
- **智能热点搜索**：按关键词抓取 B 站热门视频，采用可调权重的热度公式排序
- **多模态视频分析**：集成 **Gemini 2.5 Flash** 模型，自动分析视频内容并生成英文 Prompt 与中文标题
- **评论挖掘与迭代**：从评论区提炼视觉优化建议，使用 **DeepSeek** 模型产出新版本 Prompt

### 🧠 AI 大脑与工具调用
- **智能代理系统**：基于 LangGraph 构建的 AI 大脑，支持 Gemini 和 DeepSeek 模型
- **流式思考过程**：实时显示 AI 的思考过程和工具调用，支持详细/简洁模式切换
- **多工具集成**：支持热点搜索、Prompt 生成、视频生成等多种工具调用

### ✍️ Prompt 优化与扩展
- **交互式优化**：基于用户反馈优化现有 Prompt
- **创意扩展**：基于基础 Prompt 生成多个创意变体
- **版本迭代**：支持 Prompt 的版本管理和迭代追踪

### 🎬 视频生成
- **Flow 浏览器自动化**：支持 Google Flow 的浏览器自动化生成
- **Veo 3 API 集成**：支持 Veo 3 API 的视频生成
- **批量生成**：支持同时选择多个 Prompt 进行批量视频生成

### 🔧 系统特性
- **端口灵活配置**：支持自定义 API 端口和代理设置
- **B 站授权登录**：扫码登录获取 B 站数据访问权限
- **实时队列监控**：Flow 任务队列状态实时监控
- **标准化工程结构**：完整的项目脚手架和开发工具链

---

## 🏗️ 项目架构

```
MangoAgent/
├─ agent/                    # 核心业务逻辑
│   ├─ brain/               # AI 大脑与工具系统
│   │   ├─ core.py         # LangGraph 代理核心
│   │   ├─ tools.py        # 可用工具定义
│   │   └─ system_prompt.md # 系统提示词
│   ├─ collectors/          # 数据采集模块
│   │   └─ bilibili.py     # B 站数据采集
│   ├─ enhancers/           # 能力增强模块
│   │   ├─ gemini_vision.py # Gemini 视频分析
│   │   └─ prompt_expander.py # Prompt 扩展
│   ├─ generators/          # 视频生成器
│   │   ├─ flow_automator.py # Flow 浏览器自动化
│   │   └─ veo_api.py      # Veo 3 API 集成
│   ├─ graph/               # 流程图与状态管理
│   ├─ hotspot/             # 热点发现逻辑
│   ├─ interactive/         # 交互优化
│   ├─ iterators/           # 版本迭代
│   ├─ miners/              # 评论挖掘与洞察
│   ├─ prompt/              # Prompt 编排与 Schema
│   ├─ registry/            # 索引与注册
│   ├─ reports/             # 报表输出
│   └─ utils/               # 工具方法
├─ cli/                     # 命令行接口
├─ config/                  # 配置文件
│   ├─ default.yaml        # 默认配置
│   └─ logging.yaml        # 日志配置
├─ docs/                    # 项目文档
├─ prompts/                 # 生成的 Prompt 文件
├─ scripts/                 # 开发工具脚本
├─ tests/                   # 测试文件
├─ app.py                   # Streamlit 前端入口
├─ main.py                  # FastAPI 后端入口
├─ run_app.ps1             # 一键启动脚本
├─ pyproject.toml          # 项目配置
└─ requirements.txt        # 依赖列表
```

---

## 🚀 快速开始

### 环境要求
- **操作系统**：Windows 10/11（已适配 UTF-8 控制台）
- **Python**：3.10+
- **浏览器**：Chrome（用于 Flow 自动化）
- **推荐**：使用 Conda 虚拟环境

### 1. 环境准备

```bash
# 创建虚拟环境（推荐）
conda create -n MangoAgent python=3.10 -y
conda activate MangoAgent

# 安装依赖
pip install -r requirements.txt

# 安装开发工具（可选）
pip install -r requirements-dev.txt

# 安装 Playwright 浏览器内核（用于自动化）
python -m playwright install chromium
```

### 2. 一键启动（推荐）

```powershell
# 在项目根目录执行
.\run_app.ps1
```

启动脚本会自动：
- 启动带调试端口的 Chrome 浏览器
- 启动 FastAPI 后端服务（端口 8001）
- 启动 Streamlit 前端界面（端口 8501）
- 在 Chrome 中打开前端界面和 Flow 页面

### 3. 手动启动

如果需要分别控制服务：

```powershell
# 终端1：启动后端
uvicorn main:app --reload --port 8001

# 终端2：启动前端
streamlit run app.py
```

### 4. 配置 API 密钥

启动后在 Web 界面中配置以下 API 密钥：

- **DeepSeek API Key**：用于评论分析和 Prompt 优化
- **Gemini API Keys**：支持多个密钥轮询，用于视频分析
- **Veo API Key**：用于 Veo 3 视频生成

---

## 🔧 技术栈

### 后端技术
- **FastAPI**：现代、快速的 Web 框架
- **LangGraph**：AI 代理工作流管理
- **LangChain**：LLM 应用开发框架
- **Uvicorn**：ASGI 服务器

### 前端技术
- **Streamlit**：快速构建数据应用
- **实时流式输出**：SSE 技术实现 AI 思考过程展示

### AI 模型
- **Gemini 2.5 Flash**：Google 多模态模型，用于视频分析
- **DeepSeek Chat/Reasoner**：深度求索模型，用于文本分析和推理

### 数据采集
- **yt-dlp**：视频下载工具
- **browser-cookie3**：浏览器 Cookie 管理
- **requests**：HTTP 请求库

### 自动化工具
- **Selenium**：浏览器自动化
- **Playwright**：现代浏览器自动化
- **WebDriver Manager**：自动管理浏览器驱动

---

## 📚 API 接口

### 认证与配置
- `GET /api/health` - 健康检查
- `GET /api/keys/get` - 获取 API 密钥状态
- `POST /api/keys/update` - 更新 API 密钥
- `GET /api/auth/get-qr-code` - 获取 B 站登录二维码
- `GET /api/auth/poll-qr-code` - 轮询登录状态

### 热点发现
- `POST /api/hotspot/search` - 搜索热点视频
- `POST /api/hotspot/generate-from-link` - 从链接生成 Prompt

### Prompt 管理
- `GET /api/prompt/list` - 获取 Prompt 列表
- `DELETE /api/prompt/delete` - 删除 Prompt
- `POST /api/prompt/refine` - 交互式优化 Prompt
- `POST /api/prompt/expand` - 创意扩展

### 视频生成
- `POST /api/generate/video` - Flow 浏览器自动化生成
- `POST /api/generate/veo` - Veo 3 API 生成
- `GET /api/flow/queue_status` - 获取 Flow 队列状态

### AI 大脑
- `POST /api/agent/chat_stream` - 流式 AI 对话与工具调用

---

## 🎯 使用指南

### 1. 热点发现与 Prompt 生成
1. 在"授权登录"标签页完成 B 站登录
2. 在"热点发现"标签页输入关键词搜索热门视频
3. 选择感兴趣的视频进行 Gemini 分析
4. 系统自动生成英文 Prompt 和中文标题

### 2. Prompt 优化与迭代
1. 在"单视频迭代"标签页选择基础 Prompt 和视频链接
2. 系统自动分析评论并生成优化建议
3. 在"交互式优化"标签页基于反馈进一步优化
4. 使用"创意扩展"生成多个变体

### 3. 视频生成
1. 在"视频生成"标签页选择生成方式（Flow 或 Veo）
2. 选择要生成的 Prompt（支持批量选择）
3. 配置相关参数（端口、URL 等）
4. 提交生成任务并监控进度

### 4. AI 助手对话
1. 在右侧"AI 助手"面板选择模型
2. 开启"显示详细思考过程"查看 AI 工作流程
3. 通过自然语言与 AI 交互，AI 会自动调用相应工具

---

## ⚙️ 配置说明

### 环境变量
在 `.env` 文件中配置：
```env
DEEPSEEK_API_KEY=your_deepseek_key
GEMINI_API_KEYS=key1,key2,key3
VEO_API_KEY=your_veo_key
BILI_COOKIE=your_bilibili_cookie
```

### 端口配置
- **后端端口**：默认 8001，可在启动脚本中修改
- **前端端口**：默认 8501，可在启动脚本中修改
- **Chrome 调试端口**：默认 9222，用于 Flow 自动化

### 代理设置
支持 HTTP 代理配置，适用于需要科学上网的环境。

---

## 🛠️ 开发工具

### 代码格式化
```powershell
.\scripts\format.ps1
```

### 运行测试
```bash
pytest
```

### 本地开发
```bash
# 后端开发
uvicorn main:app --reload --port 8001

# 前端开发
streamlit run app.py
```

---

## 🔍 故障排查

### 常见问题

1. **控制台中文乱码**
   - 启动脚本已自动设置 UTF-8 编码
   - 如仍有问题，手动执行：`chcp 65001`

2. **Chrome 自动化失败**
   - 确保 Chrome 已安装
   - 检查调试端口是否被占用
   - 尝试重启 Chrome 或使用不同端口

3. **API 密钥错误**
   - 检查 `.env` 文件中的密钥格式
   - 确认密钥有效性和权限

4. **依赖安装失败**
   - 确认 Python 版本 >= 3.10
   - 尝试使用国内镜像源
   - 逐个安装依赖包排查问题

### 日志查看
- 后端日志：控制台输出
- 前端日志：Streamlit 界面底部
- 详细日志：`config/logging.yaml` 配置

---

## 🗺️ 开发路线图

### 近期计划
- [ ] 更细粒度的评论情感/主题聚类
- [ ] 多供应商 API 密钥管理与自动调度
- [ ] Prompt 质量评估指标与 A/B 测试
- [ ] 任务编排可视化与失败重试机制

### 长期规划
- [ ] 一键部署（Docker）与在线 Demo
- [ ] 多平台支持（macOS、Linux）
- [ ] 插件系统与第三方集成
- [ ] 企业级功能与权限管理

---

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

### 开发规范
- 代码遵循 `pyproject.toml` 中的 Black/Isort/Flake8 规范
- 新增功能请添加相应的测试用例
- 提交前请运行代码格式化和测试

### 问题反馈
- 使用 GitHub Issues 报告 Bug
- 提供详细的错误信息和复现步骤
- 包含系统环境信息

---

## 📄 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

---

## 🙏 致谢

感谢以下开源项目的支持：
- [LangChain](https://github.com/langchain-ai/langchain) - LLM 应用开发框架
- [FastAPI](https://github.com/tiangolo/fastapi) - 现代 Web 框架
- [Streamlit](https://github.com/streamlit/streamlit) - 数据应用框架
- [Selenium](https://github.com/SeleniumHQ/selenium) - 浏览器自动化

---

## 📞 联系方式

- **项目主页**：[https://github.com/TastyMan9o/MangoAgent](https://github.com/TastyMan9o/MangoAgent)
- **问题反馈**：[GitHub Issues](https://github.com/TastyMan9o/MangoAgent/issues)
- **功能建议**：[GitHub Discussions](https://github.com/TastyMan9o/MangoAgent/discussions)

---

<div align="center">

**⭐ 如果这个项目对你有帮助，请给个 Star！**

Made with ❤️ by MangoAgent Team

</div>