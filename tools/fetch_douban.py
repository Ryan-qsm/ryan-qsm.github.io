# -*- coding: utf-8 -*-
"""
豆瓣年度榜单爬虫（每日推荐数据源）

从豆瓣年度榜单页面抓取书籍/电影的榜单数据：
- 书籍：年度图书 + 分类主榜 + 副榜（约 150 本）
- 电影：评分最高榜单（约 58 部，仅含有评分的条目）

每条数据包含：标题、作者/导演信息、豆瓣评分、热门短评（无短评时用简介节选）、
封面/海报（下载到 docs/assets/recommend/images/ 随仓库发布，豆瓣图床禁止站外直连）、
豆瓣链接、来源榜单及排名。

数据输出到 docs/assets/recommend/books.json 和 movies.json，
页面脚本（daily-pick.js）按日期轮播展示，每天 9:00（北京时间）切换。

本地运行（建议在国内网络环境下）：
    python tools/fetch_douban.py            # 抓取全部
    python tools/fetch_douban.py books      # 只抓书籍
    python tools/fetch_douban.py movies 3   # 只抓电影，且只补全前 3 条（测试用）

下一年更新榜单：修改下方 YEAR 后重新运行即可。
"""

import json
import random
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
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

YEAR = 2025
BOOK_ANNUAL_URL = "https://book.douban.com/annual/%d/?fullscreen=1&dt_from=navigation" % YEAR
MOVIE_ANNUAL_URL = "https://movie.douban.com/annual/%d/?fullscreen=1&dt_from=movie_navigation" % YEAR
SHUFFLE_SEED = 20250917
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT_ROOT / "docs" / "assets" / "recommend"

PAGE_ID_RE = re.compile(r"page:\s*\{'id':\s*(\d+)")
COLLECTION_ID_RE = re.compile(r"subject_collection/(\d+)")
QUOTE_MAX = 160
INTRO_MAX = 140
SLEEP_RANGE = (0.8, 1.5)
CURL = shutil.which("curl")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def http_get(url, referer, timeout=30, retries=3, accept=None):
    """带重试的 GET 请求，返回响应体 bytes"""
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            headers = dict(HEADERS)
            if referer:
                headers["Referer"] = referer
            if accept:
                headers["Accept"] = accept
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except Exception as error:
            last_error = error
            if attempt < retries:
                time.sleep(attempt * 3)
    raise RuntimeError("请求失败：%s（%s）" % (url, last_error))


def get_json(url, referer):
    return json.loads(http_get(url, referer).decode("utf-8", errors="replace"))


def polite_sleep():
    time.sleep(random.uniform(*SLEEP_RANGE))


def get_page_id(annual_url):
    """从年度榜单页面 HTML 中解析后台页面 id"""
    page_html = http_get(annual_url, annual_url).decode("utf-8", errors="replace")
    match = PAGE_ID_RE.search(page_html)
    if not match:
        raise RuntimeError("未能从页面解析出 page id：%s" % annual_url)
    return int(match.group(1))


def clean_text(text, limit):
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) > limit:
        text = text[:limit].rstrip() + "…"
    return text


def best_comment(kind, item_id):
    """取一条热门短评，返回 (短评, 星级)；没有则返回 ('', 0)"""
    url = "https://m.douban.com/rexxar/api/v2/%s/%s/interests?count=5&order_by=hot" % (
        kind,
        item_id,
    )
    referer = "https://m.douban.com/%s/subject/%s/" % (kind, item_id)
    try:
        data = get_json(url, referer)
    except RuntimeError:
        return "", 0
    for interest in data.get("interests", []):
        comment = re.sub(r"\s+", " ", interest.get("comment") or "").strip()
        if 8 <= len(comment) <= QUOTE_MAX:
            stars = (interest.get("rating") or {}).get("value") or 0
            return comment, stars
    return "", 0


def fetch_detail(kind, item_id):
    """取条目详情（简介、缺失的元数据），失败返回空 dict"""
    url = "https://m.douban.com/rexxar/api/v2/%s/%s" % (kind, item_id)
    referer = "https://m.douban.com/%s/subject/%s/" % (kind, item_id)
    try:
        return get_json(url, referer)
    except RuntimeError:
        return {}


def normalize_book_cover(url):
    """书籍封面用最小尺寸（s：270px 宽，约 12~30KB；页面显示宽 150px，足够清晰）"""
    return re.sub(r"/view/subject/[a-z]+/", "/view/subject/s/", url or "")


def download_file(url, referer, target, timeout=60):
    """下载文件到 target。

    图片优先用 curl：豆瓣 CDN 会对 Python urllib 的 TLS 指纹返回反爬挑战页
    （HTTP 200 但内容是脚本而非图片），curl/.NET 等正常客户端不受影响。
    """
    if CURL:
        args = [
            CURL,
            "-s",
            "-f",
            "--location",
            "--retry",
            "3",
            "--retry-delay",
            "2",
            "--max-time",
            str(timeout),
            "-H",
            "User-Agent: " + HEADERS["User-Agent"],
            "-H",
            "Referer: " + referer,
            "-o",
            str(target),
            url,
        ]
        subprocess.run(args, capture_output=True)
        if target.exists() and target.stat().st_size > 1024:
            return True
        if target.exists():
            target.unlink()
        return False

    try:
        data = http_get(url, referer, accept="image/*,*/*;q=0.8")
    except RuntimeError:
        return False
    if len(data) > 1024:
        target.write_bytes(data)
        return True
    return False


def download_image(kind, item):
    """下载封面/海报到本地，成功时把 item['image'] 改为本地相对路径"""
    remote = item.get("image") or ""
    if not remote:
        return False
    img_dir = OUT_DIR / "images" / ("%ss" % kind)
    img_dir.mkdir(parents=True, exist_ok=True)
    target = img_dir / ("%s.jpg" % item["id"])
    local_path = "assets/recommend/images/%ss/%s.jpg" % (kind, item["id"])
    if target.exists() and target.stat().st_size > 1024:
        item["image"] = local_path
        return True

    candidates = [remote]
    if kind == "book" and "/view/subject/s/" in remote:
        candidates.append(remote.replace("/view/subject/s/", "/view/subject/m/"))
    referer = "https://%s.douban.com/" % kind
    for url in candidates:
        time.sleep(random.uniform(0.25, 0.55))
        if download_file(url, referer, target):
            item["image"] = local_path
            return True
    return False


def prune_images(kind, keep_ids):
    """删除不再引用的旧图"""
    img_dir = OUT_DIR / "images" / ("%ss" % kind)
    removed = 0
    if img_dir.exists():
        for path in img_dir.glob("*.jpg"):
            if path.stem not in keep_ids:
                path.unlink()
                removed += 1
    return removed


def normalize_book_url(url, item_id):
    """统一为豆瓣网页版链接（榜单数据里可能是 App 跳转链接）"""
    if not url or "doubanapp" in url:
        return "https://book.douban.com/subject/%s/" % item_id
    return url


def enrich_item(kind, item):
    """补全评分、封面、短评/简介"""
    detail = {}
    need_detail = not (item.get("meta") and item.get("rating") and item.get("image"))

    if need_detail:
        polite_sleep()
        detail = fetch_detail(kind, item["id"])
        if detail:
            item["meta"] = item.get("meta") or detail.get("card_subtitle") or ""
            rating = detail.get("rating") or {}
            if not item.get("rating") and rating.get("value"):
                item["rating"] = rating.get("value")
                item["rating_count"] = rating.get("rating_count") or rating.get("count") or 0
            if not item.get("image"):
                item["image"] = detail.get("cover_url") or ""

    polite_sleep()
    comment, stars = best_comment(kind, item["id"])
    if comment:
        item["quote"] = comment
        item["quote_from"] = "豆瓣短评"
        item["quote_stars"] = stars
    else:
        if not detail:
            polite_sleep()
            detail = fetch_detail(kind, item["id"])
        intro = detail.get("intro") or ""
        item["quote"] = clean_text(intro, INTRO_MAX) if intro else ""
        item["quote_from"] = "内容简介" if intro else ""
        item["quote_stars"] = 0
    return item


def collect_books(page_data):
    """汇总书籍主榜 + 副榜"""
    items = []
    seen = set()
    lists = []

    def add(raw, list_title, rank):
        item_id = str(raw.get("id") or "")
        if not item_id or item_id in seen:
            return
        seen.add(item_id)
        rating = raw.get("rating") or {}
        items.append(
            {
                "id": item_id,
                "title": raw.get("title") or "",
                "meta": raw.get("card_subtitle") or raw.get("info") or "",
                "rating": rating.get("value") or raw.get("score") or 0,
                "rating_count": rating.get("rating_count") or 0,
                "image": raw.get("cover_url") or "",
                "url": raw.get("url") or "https://book.douban.com/subject/%s/" % item_id,
                "list": list_title,
                "rank": rank,
            }
        )

    for widget in page_data.get("widgets", []):
        if widget.get("kind") == 1:
            source = widget.get("source_data") or {}
            collection = source.get("subject_collection") or {}
            list_title = collection.get("title") or widget.get("title") or ""
            lists.append(list_title)
            for index, raw in enumerate(source.get("subject_collection_items") or []):
                add(raw, list_title, index + 1)

    for widget in page_data.get("widgets", []):
        if widget.get("kind") != 3:
            continue
        for card in (widget.get("payload") or {}).get("items") or []:
            match = COLLECTION_ID_RE.search(card.get("source") or "")
            if not match:
                continue
            card_title = card.get("title") or ""
            list_title = "豆瓣%d年度%s" % (YEAR, card_title)
            lists.append(list_title)
            collection_id = match.group(1)
            start = 0
            while start < 300:
                url = (
                    "https://m.douban.com/rexxar/api/v2/subject_collection/%s/items"
                    "?start=%d&count=100" % (collection_id, start)
                )
                referer = "https://m.douban.com/subject_collection/%s" % collection_id
                try:
                    polite_sleep()
                    data = get_json(url, referer)
                except RuntimeError as error:
                    print("  副榜获取失败（%s）：%s" % (card_title, error))
                    break
                raw_items = data.get("subject_collection_items") or []
                for raw in raw_items:
                    add(raw, list_title, raw.get("rank") or 0)
                total = data.get("total") or 0
                start += len(raw_items)
                if not raw_items or start >= total:
                    break

    return items, lists


def collect_movies(page_data):
    """汇总电影评分榜（过滤无评分条目）"""
    items = []
    seen = set()
    lists = []
    for widget in page_data.get("widgets", []):
        if widget.get("kind") != 1:
            continue
        source = widget.get("source_data") or {}
        collection = source.get("subject_collection") or {}
        list_title = collection.get("title") or widget.get("title") or ""
        raw_items = source.get("subject_collection_items") or []
        if not raw_items or "期待" in list_title:
            continue
        lists.append(list_title)
        for index, raw in enumerate(raw_items):
            rating = raw.get("rating") or {}
            if not rating.get("value"):
                continue
            item_id = str(raw.get("id") or "")
            if not item_id or item_id in seen:
                continue
            seen.add(item_id)
            items.append(
                {
                    "id": item_id,
                    "title": raw.get("title") or "",
                    "meta": raw.get("card_subtitle") or "",
                    "rating": rating.get("value"),
                    "rating_count": rating.get("rating_count") or 0,
                    "image": raw.get("cover_url") or "",
                    "url": raw.get("url") or "",
                    "list": list_title,
                    "rank": index + 1,
                }
            )
    return items, lists


def build_dataset(kind, annual_url, json_host, source_title, limit=0):
    print("=== 开始抓取：%s ===" % source_title)
    page_id = get_page_id(annual_url)
    print("页面 id：%d" % page_id)
    polite_sleep()
    page_data = get_json("https://%s/j/neu/page/%d/" % (json_host, page_id), annual_url)

    if kind == "book":
        items, lists = collect_books(page_data)
    else:
        items, lists = collect_movies(page_data)

    if limit:
        items = items[:limit]
    print("榜单 %d 个，条目 %d 条，开始补全短评/简介（约需数分钟）…" % (len(lists), len(items)))

    kept = []
    image_ok = 0
    for index, item in enumerate(items, 1):
        try:
            item = enrich_item(kind, item)
        except Exception as error:
            print("  [%d/%d] 补全失败（%s）：%s" % (index, len(items), item.get("title"), error))
        if kind == "book":
            item["image"] = normalize_book_cover(item.get("image"))
            item["url"] = normalize_book_url(item.get("url"), item["id"])
        if not item.get("rating"):
            print("  [%d/%d] 跳过（缺评分）：%s" % (index, len(items), item.get("title")))
            continue
        if download_image(kind, item):
            image_ok += 1
        else:
            print("  [%d/%d] 封面下载失败（稍后重试）：%s" % (index, len(items), item.get("title")))
        kept.append(item)
        if index % 10 == 0 or index == len(items):
            print("  进度：%d/%d" % (index, len(items)))

    failed = [item for item in kept if not str(item.get("image", "")).startswith("assets/")]
    if failed:
        print("  重试 %d 张失败的图片…" % len(failed))
        time.sleep(5)
        for item in failed:
            if download_image(kind, item):
                image_ok += 1
    for item in kept:
        if not str(item.get("image", "")).startswith("assets/"):
            print("  封面最终缺失：%s" % item.get("title"))
            item["image"] = ""

    removed = prune_images(kind, {item["id"] for item in kept})
    if removed:
        print("  清理旧图 %d 张" % removed)

    random.Random(SHUFFLE_SEED).shuffle(kept)

    data = {
        "source": source_title,
        "source_url": annual_url,
        "generated_at": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M"),
        "total": len(kept),
        "items": kept,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / ("%ss.json" % kind)
    out_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        "已写入：%s（%d 条，%.0f KB，本地图片 %d 张）"
        % (out_path, len(kept), out_path.stat().st_size / 1024, image_ok)
    )
    return len(kept)


def main():
    args = sys.argv[1:]
    target = args[0] if args else "all"
    limit = int(args[1]) if len(args) > 1 and args[1].isdigit() else 0

    if target in ("books", "all"):
        build_dataset(
            "book", BOOK_ANNUAL_URL, "book.douban.com", "豆瓣%d年度读书榜单" % YEAR, limit
        )
    if target in ("movies", "all"):
        build_dataset(
            "movie", MOVIE_ANNUAL_URL, "movie.douban.com", "豆瓣%d年度电影榜单" % YEAR, limit
        )
    print("全部完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
