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

```
FIRECRAWL_API_KEY=你的_firecrawl_api_密钥
SUPABASE_ACCESS_TOKEN=你的_supabase_令牌
OPENAI_API_KEY=你的_openai_api_密钥
ASSEMBLYAI_API_KEY=你的_assemblyai_api_密钥
LIVEKIT_URL=你的_livekit_网址
LIVEKIT_API_KEY=你的_livekit_api_密钥
LIVEKIT_API_SECRET=你的_livekit_api_密钥
```

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

**模型选择逻辑：**
- 如果设置了 `OPENAI_API_KEY`，将使用 OpenAI GPT-4o 模型
- 如果未设置 `OPENAI_API_KEY`，将自动切换到本地 Ollama 模型（默认使用 llama3.2）
- 确保在使用 Ollama 之前已安装并运行 Ollama 服务

## 功能特性

- 使用 Firecrawl 进行实时网络搜索
- 通过 MCP 集成 Supabase 数据库
- 灵活的模型选择：
  - 优先使用 OpenAI GPT-4o（需要 API 密钥）
  - 备选方案：本地 Ollama 模型（llama3.2）
- 语音交互功能：
  - Silero VAD（语音活动检测）
  - AssemblyAI 语音转文字
  - OpenAI TTS 文字转语音

## 贡献

欢迎贡献！随时 fork 本仓库并提交您的改进 pull request。
