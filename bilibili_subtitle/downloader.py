"""B站 AI 字幕下载器 —— 纯模块，不含 CLI。"""

import json
import os
import sys
import time
from pathlib import Path

import requests

COOKIE_FILE = Path.home() / ".bilibili_cookies.json"
SUBTITLE_DIR = Path.home() / ".bilibili-subtitles"


def _init_browser():
    from playwright.sync_api import sync_playwright
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--no-proxy-server"])
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        locale="zh-CN",
    )
    return p, browser, context


def _load_cookies(context) -> bool:
    if COOKIE_FILE.exists():
        context.add_cookies(json.loads(COOKIE_FILE.read_text()))
        return True
    return False


def _qr_login(page, timeout=180):
    print("🔐 正在打开登录页...", file=sys.stderr)
    page.goto("https://passport.bilibili.com/login", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2000)

    qr_path = SUBTITLE_DIR / "bilibili_qr.png"
    SUBTITLE_DIR.mkdir(parents=True, exist_ok=True)
    qr_element = page.query_selector(".bili-qrcode-img, .login-qrcode-img, img[src*='qrcode']")
    if qr_element:
        qr_element.screenshot(path=str(qr_path))
    else:
        page.screenshot(path=str(qr_path))

    win_path = os.popen(f"wslpath -w {qr_path}").read().strip()
    print(f"📱 二维码: {win_path}", file=sys.stderr)
    print(f"   请用 Bilibili App 扫码 (超时 {timeout}s)...", file=sys.stderr)

    deadline = time.time() + timeout
    while time.time() < deadline:
        cookies = page.context.cookies("https://bilibili.com")
        if any(c['name'] == 'SESSDATA' for c in cookies):
            COOKIE_FILE.write_text(json.dumps(cookies, indent=2))
            print("✅ 登录成功", file=sys.stderr)
            return True
        if int(time.time()) % 15 == 0:
            print("   ⏳ 等待扫码中...", file=sys.stderr)
        time.sleep(2)
    print("❌ 登录超时", file=sys.stderr)
    return False


def _fetch_subtitle_meta(page, bvid: str) -> list:
    """调用 player/wbi/v2，返回字幕列表。"""
    page.goto(f"https://www.bilibili.com/video/{bvid}", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(4000)

    # 先不带 cid 调一次，拿到 cid
    result = page.evaluate(
        """
        async (bvid) => {
            const r = await fetch(
                'https://api.bilibili.com/x/player/wbi/v2?bvid=' + bvid,
                {credentials: 'include'}
            );
            return await r.json();
        }
        """,
        bvid,
    )
    cid = result.get("data", {}).get("cid", 0)

    # 带 cid 再调一次，拿完整数据
    result = page.evaluate(
        """
        async ([bvid, cid]) => {
            const r = await fetch(
                'https://api.bilibili.com/x/player/wbi/v2?bvid=' + bvid + '&cid=' + cid,
                {credentials: 'include'}
            );
            return await r.json();
        }
        """,
        [bvid, str(cid)],
    )
    return result.get("data", {})
    

def _download_subtitle_json(subtitle_url: str) -> list:
    """从 CDN URL 下载字幕 JSON。"""
    if subtitle_url.startswith("//"):
        subtitle_url = "https:" + subtitle_url
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.bilibili.com/",
    }
    resp = requests.get(subtitle_url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json().get("body", [])


def download_subtitle(bvid: str, force_login: bool = False) -> dict:
    """下载 B 站视频 AI 字幕，返回结构化数据。

    返回 dict:
        bvid, title, cid, aid, language, chapters, subtitles
    """
    SUBTITLE_DIR.mkdir(parents=True, exist_ok=True)
    p, browser, context = _init_browser()

    try:
        page = context.new_page()

        if not force_login:
            _load_cookies(context)
        if force_login or not COOKIE_FILE.exists():
            if not _qr_login(page):
                raise RuntimeError("登录失败")

        print("🔍 获取字幕列表...", file=sys.stderr)
        data = _fetch_subtitle_meta(page, bvid)

        aid = data.get("aid", 0)
        cid = data.get("cid", 0)
        title = data.get("title", bvid)
        subs = data.get("subtitle", {}).get("subtitles", [])

        # 章节
        chapters = [
            {"from": vp.get("from", 0), "title": vp.get("content", "")}
            for vp in data.get("view_points", [])
        ]

        if not subs:
            logged = any('SESSDATA' in c['name'] for c in page.context.cookies())
            raise RuntimeError(
                "未登录，AI 字幕需要登录。请加 --login 重试。" if not logged
                else "该视频没有字幕"
            )

        # 优先中文
        chosen = subs[0]
        for s in subs:
            if "zh" in s.get("lan", ""):
                chosen = s
                break

        url = chosen.get("subtitle_url", "")
        print(f"📺 {title[:60]}", file=sys.stderr)
        print(f"⬇ 下载 {chosen.get('lan_doc', '')} 字幕...", file=sys.stderr)

        body = _download_subtitle_json(url)

        # 缓存原始数据
        cache_file = SUBTITLE_DIR / f"{bvid}.json"
        cache_file.write_text(
            json.dumps({
                "bvid": bvid, "title": title, "cid": cid, "aid": aid,
                "language": chosen.get("lan_doc", ""), "subtitles": body,
                "chapters": chapters,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        print(f"✅ {len(body)} 行字幕已缓存", file=sys.stderr)
        return {
            "bvid": bvid, "title": title, "cid": cid, "aid": aid,
            "language": chosen.get("lan_doc", ""),
            "subtitles": body, "chapters": chapters,
        }

    finally:
        browser.close()
        p.stop()
