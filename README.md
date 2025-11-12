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

- Firecrawl API 密钥
- Supabase 访问令牌
- OpenAI API 密钥
- AssemblyAI API 密钥
- LiveKit 凭证

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
3. 设置语音交互功能
4. 开始监听用户输入

## 功能特性

- 使用 Firecrawl 进行实时网络搜索
- 通过 MCP 集成 Supabase 数据库
- 语音交互功能：
  - Silero VAD（语音活动检测）
  - AssemblyAI 语音转文字
  - OpenAI GPT-4 语言处理
  - OpenAI TTS 文字转语音

## 📬 订阅我们的新闻通讯！

**订阅我们的新闻通讯，免费获取数据科学电子书** 📖，包含 150 多个数据科学基础课程！及时了解最新教程、见解和独家资源。[立即订阅！](https://join.dailydoseofds.com)

[![Daily Dose of Data Science Newsletter](https://github.com/patchy631/ai-engineering/blob/main/resources/join_ddods.png)](https://join.dailydoseofds.com)

## 贡献

欢迎贡献！随时 fork 本仓库并提交您的改进 pull request。
