# Bilibili AI 字幕总结

输入 B 站 BV 号，自动下载 AI 字幕，用 AI 总结为结构化笔记。

支持 **DeepSeek / OpenAI / Ollama** 等任何 OpenAI 兼容 API。

## 安装

```bash
pip install bilibili-subtitle-summarize
python -m playwright install chromium
```

## 设置 API Key

```bash
# 环境变量（推荐）
export LLM_API_KEY=sk-xxx               # WSL2/Linux/macOS
$env:LLM_API_KEY="sk-xxx"               # Windows PowerShell

# 或通过 --key 参数
bili-summarize BV1ooDyBmE6v --key sk-xxx
```

DeepSeek 用户无需手动设置——工具会自动从已安装的 n8n 数据库读取 DeepSeek API Key。

## 用法

```bash
# 默认 DeepSeek（key 自动读取）
bili-summarize BV1ooDyBmE6v

# 指定模型
bili-summarize BV1ooDyBmE6v --model gpt-4o --api-base https://api.openai.com/v1 --key sk-xxx
bili-summarize BV1ooDyBmE6v --model llama3 --api-base http://localhost:11434/v1

# 输出格式
bili-summarize BV1ooDyBmE6v -f org
bili-summarize BV1ooDyBmE6v -f html
bili-summarize BV1ooDyBmE6v --login          # 重新扫码登录
bili-summarize BV1ooDyBmE6v --no-summarize    # 只下载不总结
```

首次使用弹出二维码，用 Bilibili App 扫码。Cookie 缓存 24 小时，之后无需重复登录。

## 流程

```
BV号 → 扫码登录(首次) → 下载AI字幕 → AI总结 → Markdown/Org/HTML
```

## License

MIT
