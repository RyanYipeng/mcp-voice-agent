#!/bin/bash
# 1. 创建虚拟环境
python3 -m venv venv

# 2. 激活虚拟环境
# Mac/Linux
source venv/bin/activate

# Windows
# .\venv\Scripts\activate.bat

# 3. 在虚拟环境中安装所需的包
pip install livekit-agents livekit-plugins-assemblyai livekit-plugins-openai livekit-plugins-silero python-dotenv "pydantic-ai-slim[openai,mcp]"

# 4. 运行智能体
python agent.py dev