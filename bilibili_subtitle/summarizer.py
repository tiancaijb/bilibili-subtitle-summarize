"""AI 总结模块 —— DeepSeek 分段总结 + 合并。"""

import json
import os
import re
import sys
from pathlib import Path

import requests

DEEPSEEK_KEY_FILE = Path.home() / ".deepseek_key"
CHUNK_SIZE = 6000


def get_deepseek_key() -> str:
    """获取 DeepSeek API key（环境变量 > 文件 > n8n 数据库）"""
    key = os.environ.get("DEEPSEEK_KEY", "")
    if key:
        return key
    if DEEPSEEK_KEY_FILE.exists():
        return DEEPSEEK_KEY_FILE.read_text().strip()

    # 从 n8n 数据库解密
    try:
        import sqlite3, base64, hashlib
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

        config_path = Path.home() / ".n8n/config"
        if config_path.exists():
            with open(config_path) as f:
                cfg = json.load(f)
            key_bytes = cfg.get("encryptionKey", "").encode()
            conn = sqlite3.connect(str(Path.home() / ".n8n/database.sqlite"))
            cursor = conn.execute(
                "SELECT data FROM credentials_entity WHERE type = 'deepSeekApi' LIMIT 1"
            )
            row = cursor.fetchone()
            conn.close()
            if row:
                enc = base64.b64decode(row[0])
                salt, ct = enc[8:16], enc[16:]
                dk = b""
                while len(dk) < 48:
                    dk += hashlib.md5(
                        dk[-16:] + key_bytes + salt if dk else key_bytes + salt
                    ).digest()
                cipher = Cipher(algorithms.AES(dk[:32]), modes.CBC(dk[32:48]))
                decryptor = cipher.decryptor()
                plain = decryptor.update(ct) + decryptor.finalize()
                plain = plain[:-plain[-1]]
                return json.loads(plain)["apiKey"]
    except Exception:
        pass

    raise RuntimeError(
        "未找到 DeepSeek API key。设置 DEEPSEEK_KEY 环境变量或创建 ~/.deepseek_key 文件。"
    )


def _format_subtitle_text(data: dict) -> str:
    """字幕 → LLM 可读文本。"""
    subs = data["subtitles"]
    chapters = data.get("chapters", [])

    lines = [f"标题: {data['title']}", f"语言: {data['language']}", ""]

    if chapters:
        lines.append("## 章节")
        for ch in chapters:
            ts = int(ch["from"])
            lines.append(f"- {ts//60:02d}:{ts%60:02d} {ch['title']}")
        lines.append("")

    lines.append("## 字幕全文\n")

    ci = 0
    for item in subs:
        t = int(item.get("from", 0))
        content = item.get("content", "")
        while ci < len(chapters) and t >= chapters[ci]["from"]:
            lines.append(f"\n### {chapters[ci]['title']}")
            ci += 1
        lines.append(f"[{t//60:02d}:{t%60:02d}] {content}")

    return "\n".join(lines)


def _chunk_text(text: str, max_chars: int = CHUNK_SIZE) -> list:
    """按字数分块。"""
    if len(text) <= max_chars:
        return [text]
    chunks = []
    while len(text) > max_chars:
        split = text.rfind("。", 0, max_chars)
        if split == -1:
            split = text.rfind("\n", 0, max_chars)
        if split == -1:
            split = max_chars
        chunks.append(text[:split + 1])
        text = text[split + 1:].strip()
    if text:
        chunks.append(text)
    return chunks


def _call_llm(prompt: str, model: str, api_key: str, api_base: str, max_tokens: int = 4096) -> str:
    """调用 OpenAI 兼容 API（DeepSeek、OpenAI、Ollama 等通用）"""
    resp = requests.post(
        f"{api_base}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": max_tokens,
        },
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def summarize(subtitle_data: dict, api_key: str = "", model: str = "deepseek-chat", api_base: str = "https://api.deepseek.com/v1") -> str:
    """总结字幕内容，返回 Markdown。

    默认使用 DeepSeek。指定 model 和 api_base 可切换模型：
      - OpenAI:     model="gpt-4o", api_base="https://api.openai.com/v1"
      - 本地 Ollama: model="llama3", api_base="http://localhost:11434/v1"
    """
    if not api_key:
        api_key = get_deepseek_key()

    title = subtitle_data["title"]
    text = _format_subtitle_text(subtitle_data)
    chunks = _chunk_text(text)

    print(f"📝 字幕共 {len(text)} 字，分 {len(chunks)} 段处理", file=sys.stderr)

    summaries = []
    for i, chunk in enumerate(chunks):
        prompt = f"""请将以下B站视频字幕（第 {i+1}/{len(chunks)} 部分）整理为结构化笔记：

{chunk}

要求：
- 保留关键的技术细节和具体数据
- 用标题组织层次结构
- 提取核心观点和可操作要点
- 直接用中文输出，不要解释、不要寒暄"""
        print(f"  🤖 总结第 {i+1}/{len(chunks)} 部分...", file=sys.stderr)
        summaries.append(_call_llm(prompt, model, api_key, api_base))

    if len(summaries) == 1:
        return summaries[0]

    combined = "\n\n---\n\n".join(
        f"## 第 {i+1} 部分\n\n{s}" for i, s in enumerate(summaries)
    )
    prompt = f"""请将以下多段视频笔记合并整理为一份完整的结构化笔记。

视频标题: {title}

{combined}

要求：
- 去除重复内容
- 统一标题层级
- 保留所有关键信息
- 输出完整的结构化笔记（Markdown 格式）
- 直接用中文输出"""
    print(f"  🔗 合并 {len(summaries)} 段总结...", file=sys.stderr)
    return _call_llm(prompt, model, api_key, api_base, max_tokens=4096)


def _to_org(md: str, title: str) -> str:
    lines = [f"#+TITLE: {title}", ""]
    for line in md.split("\n"):
        if line.startswith("### "):
            lines.append(f"*** {line[4:]}")
        elif line.startswith("## "):
            lines.append(f"** {line[3:]}")
        elif line.startswith("# "):
            lines.append(f"* {line[2:]}")
        elif line.startswith("- "):
            lines.append(f"- {line[2:]}")
        else:
            lines.append(line)
    return "\n".join(lines)


def _to_html(md: str, title: str) -> str:
    html = []
    in_list = False
    for line in md.split("\n"):
        line = line.strip()
        if not line:
            if in_list:
                html.append("</ul>")
                in_list = False
            html.append("")
            continue
        if line.startswith("### "):
            if in_list:
                html.append("</ul>")
                in_list = False
            html.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("## "):
            if in_list:
                html.append("</ul>")
                in_list = False
            html.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("# "):
            if in_list:
                html.append("</ul>")
                in_list = False
            html.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("- "):
            if not in_list:
                html.append("<ul>")
                in_list = True
            html.append(f"<li>{line[2:]}</li>")
        else:
            if in_list:
                html.append("</ul>")
                in_list = False
            line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
            html.append(f"<p>{line}</p>")
    if in_list:
        html.append("</ul>")
    body = "\n".join(html)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  body {{ font-family: -apple-system, sans-serif; max-width: 720px; margin: 0 auto; padding: 40px 20px; line-height: 1.7; color: #1a1a1a; }}
  h1 {{ font-size: 1.8rem; border-bottom: 2px solid #2563eb; padding-bottom: 8px; }}
  h2 {{ font-size: 1.3rem; margin-top: 32px; color: #2563eb; }}
  h3 {{ font-size: 1.1rem; margin-top: 24px; }}
  ul {{ padding-left: 20px; }}
  li {{ margin: 4px 0; }}
  p {{ margin: 12px 0; }}
  strong {{ color: #2563eb; }}
</style>
</head>
<body>
<h1>{title}</h1>
{body}
</body>
</html>"""


def format_output(md: str, title: str, fmt: str) -> str:
    if fmt == "org":
        return _to_org(md, title)
    elif fmt == "html":
        return _to_html(md, title)
    return f"# {title}\n\n{md}"
