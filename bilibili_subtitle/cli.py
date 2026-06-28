"""B站视频 → AI 总结命令行工具"""

import argparse
import os
import sys
from pathlib import Path

from .downloader import download_subtitle
from .summarizer import summarize


def main():
    parser = argparse.ArgumentParser(
        description="B站视频 → AI 总结笔记",
        usage="bili-summarize <BV号> [options]",
    )
    parser.add_argument("video", help="BV 号或视频 URL")
    parser.add_argument("-f", "--format", choices=["md", "org", "html"], default="md",
                        help="输出格式 (默认: md)")
    parser.add_argument("--login", action="store_true", help="强制重新扫码登录")
    parser.add_argument("--no-summarize", action="store_true", help="只下载字幕，不总结")
    parser.add_argument("-o", "--output", type=str, default="",
                        help="输出文件路径")
    parser.add_argument("--key", type=str, default="",
                        help="API Key")
    parser.add_argument("--model", type=str, default="deepseek-chat",
                        help="模型名 (默认: deepseek-chat, 也支持 gpt-4o, claude-3-opus 等)")
    parser.add_argument("--api-base", type=str, default="https://api.deepseek.com/v1",
                        help="API 地址 (默认: DeepSeek, 可设为 https://api.openai.com/v1 等)")
    args = parser.parse_args()

    # 提取 BV 号
    import re
    m = re.search(r"(BV[a-zA-Z0-9]{10})", args.video)
    if not m:
        print(f"错误: 无法从 '{args.video}' 提取 BV 号", file=sys.stderr)
        sys.exit(1)
    bvid = m.group(1)

    print(f"🎬 BV: {bvid}", file=sys.stderr)

    # 1. 下载字幕
    subtitle_data = download_subtitle(bvid, force_login=args.login)

    if args.no_summarize:
        print("⏹ 跳过总结（--no-summarize）", file=sys.stderr)
        return

    # 2. AI 总结
    print(f"\n🤖 开始 AI 总结...", file=sys.stderr)
    markdown = summarize(subtitle_data, api_key=args.key, model=args.model, api_base=args.api_base)

    # 4. 格式化输出
    from .summarizer import format_output
    title = subtitle_data["title"]
    output = format_output(markdown, title, args.format)

    out_dir = Path.home() / ".bilibili-subtitles"
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.output:
        outpath = Path(args.output)
    else:
        ext = {"md": "md", "org": "org", "html": "html"}[args.format]
        outpath = out_dir / f"{bvid}_summary.{ext}"

    outpath.write_text(output, encoding="utf-8")
    print(f"✅ 已保存: {outpath}", file=sys.stderr)


if __name__ == "__main__":
    main()
