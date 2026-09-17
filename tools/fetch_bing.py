# -*- coding: utf-8 -*-
"""
每日必应壁纸抓取脚本

从 https://bing.wdbyte.com/zh-cn/ 抓取最新 7 天的壁纸，
下载 1920x1080 图片到 docs/assets/bing/，并生成 manifest.json 供首页读取。

该脚本在 GitHub Actions 构建前运行，图片不提交进仓库，仓库不会随天数膨胀。
本地预览时也可手动运行：python tools/fetch_bing.py
"""

import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

if sys.platform == "win32":
    try:
        import ctypes

        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    except Exception:
        pass
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PAGE_URL = "https://bing.wdbyte.com/zh-cn/"
KEEP_DAYS = 7
PROJECT_ROOT = Path(__file__).resolve().parent.parent
IMG_DIR = PROJECT_ROOT / "docs" / "assets" / "bing"
MANIFEST = IMG_DIR / "manifest.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    ),
    "Referer": "https://bing.wdbyte.com/",
}

CARD_RE = re.compile(
    r'<div class="w3-third[^"]*"[^>]*>\s*'
    r'<img class="smallImg" src="https://cn\.bing\.com/th\?id='
    r'(?P<img_id>OHR\.[^"&]+_UHD\.jpg)[^"]*"'
    r'.*?data-date="(?P<date>\d{4}-\d{2}-\d{2})"\s+data-desc="(?P<desc>[^"]*)"',
    re.DOTALL,
)

CAPTION_TAIL_RE = re.compile(r"\s*\(©.*?\)\s*$")
FILENAME_RE = re.compile(r"^bing-(\d{8})\.jpg$")


def http_get(url, timeout=30, retries=3):
    """带重试的 GET 请求，返回响应体 bytes"""
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except Exception as error:
            last_error = error
            print("  第 %d 次请求失败：%s" % (attempt, error))
            if attempt < retries:
                time.sleep(attempt * 3)
    raise RuntimeError("请求失败：%s（%s）" % (url, last_error))


def parse_cards(page_html):
    """解析页面，按时间倒序返回最新的 KEEP_DAYS 条记录"""
    cards = []
    seen_dates = set()
    for match in CARD_RE.finditer(page_html):
        date = match.group("date")
        if date in seen_dates:
            continue
        seen_dates.add(date)
        caption = CAPTION_TAIL_RE.sub("", html.unescape(match.group("desc"))).strip()
        cards.append(
            {
                "date": date,
                "img_id": match.group("img_id"),
                "caption": caption,
            }
        )
        if len(cards) >= KEEP_DAYS:
            break
    return cards


def download_images(cards):
    """下载缺失的图片，返回成功下载数量"""
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    downloaded = 0
    for card in cards:
        date_compact = card["date"].replace("-", "")
        target = IMG_DIR / ("bing-%s.jpg" % date_compact)
        if target.exists() and target.stat().st_size > 0:
            print("已存在，跳过：%s" % target.name)
            continue
        url = (
            "https://cn.bing.com/th?id=%s&pid=hp&w=1920&h=1080&rs=1&c=4"
            % card["img_id"]
        )
        print("下载中：%s -> %s" % (url.split("&")[0], target.name))
        data = http_get(url)
        if len(data) < 10240:
            raise RuntimeError("图片内容异常（仅 %d 字节）：%s" % (len(data), url))
        target.write_bytes(data)
        downloaded += 1
    return downloaded


def prune_old_images(cards):
    """删除不在保留列表中的旧图"""
    keep_names = {
        "bing-%s.jpg" % card["date"].replace("-", "") for card in cards
    }
    removed = 0
    for path in IMG_DIR.glob("bing-*.jpg"):
        if FILENAME_RE.match(path.name) and path.name not in keep_names:
            path.unlink()
            print("删除旧图：%s" % path.name)
            removed += 1
    return removed


def write_manifest(cards):
    """生成 manifest.json"""
    entries = [
        {
            "date": card["date"],
            "src": "assets/bing/bing-%s.jpg" % card["date"].replace("-", ""),
            "caption": card["caption"],
        }
        for card in cards
    ]
    MANIFEST.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return len(entries)


def main():
    print("抓取页面：%s" % PAGE_URL)
    try:
        page_html = http_get(PAGE_URL).decode("utf-8", errors="replace")
    except RuntimeError as error:
        print("错误：%s" % error, file=sys.stderr)
        return 1

    cards = parse_cards(page_html)
    if not cards:
        print("错误：未从页面解析到任何壁纸，页面结构可能已变化", file=sys.stderr)
        return 1

    print("解析到 %d 天壁纸，最新：%s（%s）" % (len(cards), cards[0]["date"], cards[0]["caption"]))

    try:
        downloaded = download_images(cards)
        removed = prune_old_images(cards)
        count = write_manifest(cards)
    except RuntimeError as error:
        print("错误：%s" % error, file=sys.stderr)
        return 1

    print(
        "完成：新下载 %d 张，删除旧图 %d 张，manifest 共 %d 条" % (downloaded, removed, count)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
