# Bilibili AI 字幕总结

输入 B 站 BV 号，自动下载 AI 字幕，用 DeepSeek 总结为结构化笔记。

## 安装

```bash
pip install bilibili-subtitle-summarize
python -m playwright install chromium
```

## 设置 API Key

二选一：

```bash
# 方式1：环境变量（推荐，通用）
export DEEPSEEK_KEY=sk-xxx              # WSL2/Linux/macOS
set DEEPSEEK_KEY=sk-xxx                # Windows cmd
$env:DEEPSEEK_KEY="sk-xxx"            # Windows PowerShell

# 方式2：bili-summarize --key 参数
bili-summarize BV1ooDyBmE6v --key sk-xxx
```

DeepSeek key 也可存放在用户目录的 `.deepseek_key` 文件中（纯文本，一行 key）：

| 系统 | 路径 |
|------|------|
| WSL2/Linux/macOS | `~/.deepseek_key` |
| Windows | `%USERPROFILE%\.deepseek_key` |

## 用法

```bash
# 默认 DeepSeek
bili-summarize BV1ooDyBmE6v

# 指定模型和 API
bili-summarize BV1ooDyBmE6v --model gpt-4o --api-base https://api.openai.com/v1 --key sk-xxx
bili-summarize BV1ooDyBmE6v --model llama3 --api-base http://localhost:11434/v1

# 格式选项
bili-summarize BV1ooDyBmE6v -f org
bili-summarize BV1ooDyBmE6v -f html
bili-summarize BV1ooDyBmE6v --login
bili-summarize BV1ooDyBmE6v --no-summarize
```

DeepSeek 的 API Key 会自动从 `~/.deepseek_key` 或 n8n 数据库读取，无需每次指定。其他模型的 key 用 `--key` 传入。
```

首次使用会弹出二维码，用 Bilibili App 扫码登录。Cookie 缓存 24 小时。

## 流程

```
BV号 → 扫码登录(首次) → 下载AI字幕 → DeepSeek总结 → Markdown/Org/HTML
```

## 文件结构

```
bili_summarize.py    ← 主入口（下载 + 总结 + 格式化输出）
download.py          ← 纯字幕下载器
requirements.txt     ← 依赖
README.md
```

## License

MIT
