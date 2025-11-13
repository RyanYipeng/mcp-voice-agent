# MCP驱动的语音智能体

本项目实现了一个语音智能体，通过 MCP（模型上下文协议）将 Firecrawl 的网络搜索功能与 Supabase 数据库操作相结合。

## 安装

确保已安装 Python 3.x，然后运行：


```bash
pip install -r requirements.txt
```

## 实现：agent.py

该实现使用 AssemblyAI 的服务进行语音转文字，同时使用 Firecrawl 进行网络搜索，使用 Supabase 进行数据库操作。

### 环境要求

- Firecrawl API 密钥（必需）
- Supabase 访问令牌（必需）
- OpenAI API 密钥（可选，未设置时将使用本地 Ollama 模型）
- AssemblyAI API 密钥（必需）
- LiveKit 凭证（必需）
- Ollama（当不使用 OpenAI API 时需要安装）

### 配置

复制 `.env.example` 文件为 `.env`，并配置以下环境变量：

**必需配置：**
```
FIRECRAWL_API_KEY=你的_firecrawl_api_密钥
SUPABASE_ACCESS_TOKEN=你的_supabase_令牌
ASSEMBLYAI_API_KEY=你的_assemblyai_api_密钥
LIVEKIT_URL=你的_livekit_网址
LIVEKIT_API_KEY=你的_livekit_api_密钥
LIVEKIT_API_SECRET=你的_livekit_api_密钥
```

**可选配置（LLM 模型选择）：**
```
# 强制使用本地 Ollama（优先级最高）
USE_LOCAL_LLM=true

# OpenAI 配置（可选）
OPENAI_API_KEY=你的_openai_api_密钥
OPENAI_BASE_URL=你的_自定义_api_端点（用于中转站等）
OPENAI_MODEL=gpt-4o（默认值，可自定义）

# Ollama 配置（本地模型）
OLLAMA_MODEL=qwen2.5:7b-instruct（默认值，可自定义）
```

**可选配置（TTS）：**
```
# 本地 TTS（推荐，轻量级且免费）
USE_LOCAL_TTS=true（默认值）
CARTESIA_API_KEY=你的_cartesia_密钥（可选，不设置使用免费额度）
CARTESIA_VOICE=语音ID（默认：79a125e8-cd45-4c13-8a67-188112f4dd22）

# 或使用 OpenAI TTS（需设置 USE_LOCAL_TTS=false）
TTS_VOICE=ash（可选：alloy, echo, fable, onyx, nova, shimmer）
```

**关于配置：**
- **本地 TTS**：默认使用 Cartesia（轻量级、免费额度、无需下载模型）
- **模型配置**：所有模型名称都可通过环境变量配置，无需修改代码
- **API 支持**：支持官方 OpenAI API 和自定义端点（中转站等）
- **端点兼容**：自定义端点需遵循 OpenAI API 格式

### 运行

使用以下命令启动智能体：

```bash
python agent.py
```

智能体将会：
1. 连接到 LiveKit
2. 初始化 Supabase 集成的 MCP 服务器
3. 设置语音交互功能（自动检测是否使用 OpenAI API 或本地 Ollama 模型）
4. 开始监听用户输入

**LLM 模型选择逻辑（优先级从高到低）：**
1. **强制使用本地 Ollama**：如果设置了 `USE_LOCAL_LLM=true`，将强制使用 Ollama（即使配置了 OpenAI API）
   - 模型名称：通过 `OLLAMA_MODEL` 配置（默认：qwen2.5:7b-instruct）
   - 需要确保 Ollama 服务运行在 `localhost:11434`

2. **使用 OpenAI API**：如果设置了 `OPENAI_API_KEY`（且 `USE_LOCAL_LLM` 不为 true）
   - 模型名称：通过 `OPENAI_MODEL` 配置（默认：gpt-4o）
   - 默认使用官方 OpenAI API
   - 如果设置了 `OPENAI_BASE_URL`，将使用自定义 API 端点（适用于中转站等）

3. **默认使用本地 Ollama**：如果未设置 `OPENAI_API_KEY`
   - 模型名称：通过 `OLLAMA_MODEL` 配置（默认：qwen2.5:7b-instruct）

**TTS 语音选择逻辑：**
- 默认使用本地 TTS（`USE_LOCAL_TTS=true`）
  - 使用 Cartesia TTS（轻量级、免费额度、无需本地下载）
  - 可选配置 `CARTESIA_API_KEY` 获得更多配额
- 可切换到 OpenAI TTS（设置 `USE_LOCAL_TTS=false`）
  - 需要有效的 OpenAI API 密钥
  - 通过 `TTS_VOICE` 配置语音

## 功能特性

- 使用 Firecrawl 进行实时网络搜索
- 通过 MCP 集成 Supabase 数据库
- 灵活的模型选择：
  - 支持 OpenAI 模型（官方 API 和自定义端点）
  - 支持本地 Ollama 模型
  - 所有模型名称可通过环境变量配置
- 语音交互功能：
  - Silero VAD（语音活动检测）
  - AssemblyAI 语音转文字
  - **本地 TTS**：Cartesia（轻量级、免费、无需下载模型）
  - 可选：OpenAI TTS（需配置）

## 贡献

欢迎贡献！随时 fork 本仓库并提交您的改进 pull request。
