"""
每日爬取：搜索各高校2026年招生计划新闻 → 提取数据 → 更新数据库

策略：
  1. 先搜索汇总型文章（一篇文章含多校数据），从中批量提取
  2. 再对未找到的学校逐个搜索
  3. 提取每所学校的最新总计划数
  4. 如果与2025年数据有差异，更新 enrollment_plan

用法：
  python scripts/crawl_plan_news.py           # 执行一次完整爬取
  python scripts/crawl_plan_news.py --status  # 查看当前覆盖状态

数据流向：
  新闻文章 → (school_name, total_plan, change) → enrollment_plan
                                                      ↓
                                            compute_cumulative_shifts()
                                                      ↓
                                            recommend_service 调整位次
"""

import argparse
import json
import logging
import os
import re
import sqlite3
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

# ── 路径 ─────────────────────────────────────────────────────────────
DB_PATH = Path(__file__).resolve().parent.parent / "gaokao.db"
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
CACHE_PATH = Path(__file__).resolve().parent.parent / "cache" / "plan_news_cache.json"

# ── 日志 ─────────────────────────────────────────────────────────────
def setup_logging():
    """初始化日志（要等LOG_DIR确认存在后再调用）"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOG_DIR / f"crawl_{datetime.now().strftime('%Y%m%d')}.log", encoding="utf-8"),
        ],
        force=True,
    )

logger = logging.getLogger(__name__)

# ── 请求头 ──────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ── 搜索配置 ─────────────────────────────────────────────────────────
# 搜索间隔（秒）—— 搜狗对频繁请求很敏感，必须保持足够间隔
SOGOU_DELAY = 8.0       # 搜狗搜索间隔
SO360_DELAY = 5.0       # 360搜索间隔
ARTICLE_DELAY = 1.5     # 文章抓取间隔

# 单次运行最大请求数（避免被封IP）
MAX_SEARCHES_PER_RUN = 8
MAX_ARTICLES_PER_RUN = 15

SEARCH_ENGINES = {
    "sogou": {
        "url": "https://www.sogou.com/web",
        "params": {"query": None, "num": 10},
        "delay": SOGOU_DELAY,
    },
    "so360": {
        "url": "https://www.so.com/s",
        "params": {"q": None, "pn": 1},
        "delay": SO360_DELAY,
    },
}

# 汇总型查询关键词（优先搜索，一篇文章覆盖多校）
SCHOOL_QUERY_TEMPLATE = "{school} 2026 招生计划 本科"

# ── 新闻源域名 + 内容提取规则 ─────────────────────────────────
NEWS_SOURCES = {
    "news.qq.com": {"selector": ".content-article", "fallback": "article"},
    "view.inews.qq.com": {"selector": ".content-article", "fallback": "body"},
    "new.qq.com": {"selector": ".content-article", "fallback": "body"},
    "news.dayoo.com": {"selector": ".article-content", "fallback": "body"},
    "news.10jqka.com.cn": {"selector": ".article-body", "fallback": "body"},
    "m.163.com": {"selector": ".post_body", "fallback": "article"},
    "news.sohu.com": {"selector": "article", "fallback": "body"},
    "www.sohu.com": {"selector": "article", "fallback": "body"},
    "guangdong.eol.cn": {"selector": ".article-content", "fallback": "body"},
    "baijiahao.baidu.com": {"selector": ".article-content", "fallback": "body"},
    "so.html5.qq.com": {"selector": "body", "fallback": None},  # QQ search results page
    "newsa.html5.qq.com": {"selector": "body", "fallback": None},
    # 南都N视频（南方都市报）
    "m.mp.oeeee.com": {"selector": None, "fallback": "body"},
}

# 南都高考专栏URL（每天检查）
OEEEE_SPECIAL_COLUMN = "https://m.mp.oeeee.com/special/4872_cdd49212b688b0a7dfdc577e30f1d461.html"

# 汇总型查询关键词（优先搜索，一篇文章覆盖多校）
# 策略：广东本地 + 全国范围 + 热门省外高校聚集地，轮流搜索
ROUNDUP_QUERIES = [
    # ── 广东本地（南都/广州日报等） ──
    "2026 广东 高校 招生计划 扩招",
    "2026年广东高校本科招生计划公布",
    "广东多所高校2026本科招生计划",
    "site:m.mp.oeeee.com 招生计划 2026",

    # ── 全国范围（省外高校在广东的招生） ──
    "2026 年全国高校在广东招生计划",
    "2026 本科招生计划 扩招 全国",
    "2026 各高校招生计划 公布 汇总",
    "2026 高考 招生计划 出炉 汇总",

    # ── 热门省外省份/城市（广东考生常报考） ──
    "2026 武汉 高校 在广东 招生计划",
    "2026 长沙 高校 本科 招生计划",
    "2026 南京 高校 本科 招生计划",
    "2026 西安 高校 在广东 招生",
    "2026 成都 高校 本科 招生计划",
    "2026 北京 高校 本科 招生计划",
    "2026 上海 高校 本科 招生计划",
    "2026 杭州 高校 本科 招生计划",
    "2026 南昌 高校 在广东 招生",

    # ── 双一流/重点高校 ──
    "2026 双一流 高校 招生计划 扩招",
    "2026 985 211 高校 招生计划",
]


# ═════════════════════════════════════════════════════════════════════
#  数据层
# ═════════════════════════════════════════════════════════════════════

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def load_school_list() -> list[dict]:
    """从 enrollment_plan 中加载所有学校（去重）"""
    conn = get_db()
    rows = conn.execute("""
        SELECT school_code, school_name, school_level, city,
               SUM(CASE WHEN year=2025 THEN plan_count ELSE 0 END) as plan_2025,
               SUM(CASE WHEN year=2026 THEN plan_count ELSE 0 END) as plan_2026
        FROM enrollment_plan
        WHERE year IN (2025, 2026) AND batch = '本科普通批'
        GROUP BY school_code, school_name, school_level, city
        ORDER BY school_name
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def load_news_cache() -> dict:
    """加载已爬取的新闻缓存，避免重复爬取"""
    if CACHE_PATH.exists():
        try:
            with open(CACHE_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_news_cache(cache: dict):
    """保存新闻缓存"""
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def get_existing_2026_plans() -> dict:
    """获取数据库中已有的 2026 学校级总计划数"""
    conn = get_db()
    rows = conn.execute("""
        SELECT school_code, SUM(plan_count) as total
        FROM enrollment_plan
        WHERE year = 2026 AND batch = '本科普通批'
        GROUP BY school_code
    """).fetchall()
    conn.close()
    return {r["school_code"]: r["total"] for r in rows}


# ═════════════════════════════════════════════════════════════════════
#  搜索层
# ═════════════════════════════════════════════════════════════════════

def search_sogou(query: str, retries: int = 2) -> str | None:
    """搜狗搜索（先访问首页拿cookie，再搜索）"""
    session = requests.Session()
    session.headers.update(HEADERS)

    for attempt in range(retries + 1):
        try:
            # 先拿cookie
            session.get("https://www.sogou.com/", timeout=10)
            time.sleep(1)

            resp = session.get(
                "https://www.sogou.com/web",
                params={"query": query, "num": 10},
                timeout=15,
            )
            if resp.status_code == 200 and len(resp.text) > 5000:
                return resp.text
            elif "antispider" in resp.text.lower() or len(resp.text) < 5000:
                logger.warning(f"  Sogou anti-spider triggered (attempt {attempt+1})")
                time.sleep(5 * (attempt + 1))
            else:
                return resp.text
        except Exception as e:
            logger.warning(f"  Sogou error: {e}")
            time.sleep(3)
    return None


def search_360(query: str, retries: int = 2) -> str | None:
    """360搜索"""
    session = requests.Session()
    session.headers.update(HEADERS)

    for attempt in range(retries + 1):
        try:
            resp = session.get(
                "https://www.so.com/s",
                params={"q": query, "pn": 1},
                timeout=15,
            )
            if resp.status_code == 200 and len(resp.text) > 5000:
                return resp.text
            time.sleep(3 * (attempt + 1))
        except Exception as e:
            logger.warning(f"  360 search error: {e}")
            time.sleep(2)
    return None


def extract_article_urls(html: str, source: str) -> list[str]:
    """从搜索结果页中提取文章URL"""
    soup = BeautifulSoup(html, "html.parser")
    raw_links = set()

    # 提取所有可能包含新闻链接的 a 标签
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        if len(text) < 10:
            continue

        # 方案1: 直接链接（view.inews.qq.com, news.qq.com 等）
        if any(domain in href for domain in [
            "view.inews.qq.com", "news.qq.com", "new.qq.com",
            "news.dayoo.com", "news.10jqka.com.cn",
            "m.163.com", "news.sohu.com", "www.sohu.com",
            "so.html5.qq.com", "newsa.html5.qq.com",
            "guangdong.eol.cn", "baijiahao.baidu.com",
        ]):
            raw_links.add(href)

        # 方案2: Sogou 跳转链接
        if "sogou.com/link" in href and "url=" in href:
            import urllib.parse
            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
            if "url" in parsed:
                real_url = parsed["url"][0]
                if any(domain in real_url for domain in [
                    "view.inews.qq.com", "news.qq.com", "new.qq.com",
                    "news.dayoo.com", "news.10jqka.com.cn",
                    "m.163.com", "news.sohu.com", "www.sohu.com",
                    "so.html5.qq.com", "newsa.html5.qq.com",
                ]):
                    raw_links.add(real_url)

    # 方案3: 360搜索结果 — 从JS redirect中提取
    if source == "so360":
        for match in re.finditer(r'window\.location\.replace\(["\']([^"\']+)["\']\)', html):
            url = match.group(1)
            if any(domain in url for domain in [
                "view.inews.qq.com", "news.qq.com", "news.dayoo.com",
                "m.163.com", "news.sohu.com", "news.10jqka.com.cn",
            ]):
                raw_links.add(url)

    return list(raw_links)


def fetch_article(url: str) -> str | None:
    """抓取文章内容"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return None
        return resp.text
    except Exception:
        return None


def extract_article_text(html: str, url: str) -> str | None:
    """从HTML中提取文章正文"""
    soup = BeautifulSoup(html, "html.parser")

    # 根据域名选择提取规则
    for domain, rules in NEWS_SOURCES.items():
        if domain in url:
            if rules["selector"]:
                el = soup.select_one(rules["selector"])
                if el:
                    return el.get_text(strip=True)
            if rules["fallback"]:
                # 对于南都文章，有特殊的正文范围
                if "m.mp.oeeee.com" in url:
                    body = soup.select_one(rules["fallback"])
                    if body:
                        raw = body.get_text(strip=True)
                        start = raw.find("查看")
                        end = raw.find("采写：")
                        if start > 0:
                            article = raw[start+2:end] if end > 0 else raw[start+2:]
                            if len(article) > 200:
                                return article
                else:
                    el = soup.select_one(rules["fallback"])
                    if el:
                        return el.get_text(strip=True)
            break

    # 通用提取：尝试常见选择器
    for selector in [
        ".content-article", ".articleContent", ".article-detail",
        ".main-content", ".post_body", ".article-content",
        ".rich_media_content", "article", ".article-body",
        ".left_zw", ".articlecont", ".ne_article_content",
        ".article-con", ".news-content", "#article-content",
    ]:
        el = soup.select_one(selector)
        if el:
            text = el.get_text(strip=True)
            if len(text) > 200:
                return text

    # 最后fallback: body中的所有p标签
    body = soup.find("body")
    if body:
        # 跳过脚本和样式
        for tag in body.find_all(["script", "style", "noscript"]):
            tag.decompose()
        ps = body.find_all("p")
        text = " ".join(p.get_text(strip=True) for p in ps if len(p.get_text(strip=True)) > 10)
        if len(text) > 200:
            return text

    return None


# ═════════════════════════════════════════════════════════════════════
#  解析层
# ═════════════════════════════════════════════════════════════════════

# 计划数匹配模式
PLAN_PATTERNS = [
    # "XX大学2026年本科招生计划数7100人"
    r"(?:招生计划\s*(?:总数?|数|为)?|计划\s*(?:招生|招收)\s*)(\d{3,5})\s*人",
    # "本科招生计划数7100人"
    r"(?:本科|普通|全国|内地)\s*(?:招生)?\s*计划\s*(?:总数?|数|为)?\s*(\d{3,5})\s*人",
    # "招生总规模7230人"
    r"(?:招生|计划)\s*(?:总)?\s*(?:规模|人数?|名额)\s*(\d{3,5})\s*人",
    # "扩招100人" (上下文需要学校名)
    r"(?:扩招|增加|新增)\s*(\d{2,4})\s*人",
    # "招生3060人"
    r"(?:招收|招生)\s*(\d{3,5})\s*人",
    # "计划招生7100人"
    r"计划\s*招生\s*(\d{3,5})\s*人",
]

# 学校名+计划数的组合模式
SCHOOL_PLAN_PATTERNS = [
    # "XX大学本科招生计划数7100人"
    r"([一-鿿]{2,8}(?:大学|学院))\s*(?:2026年)?\s*(?:本科|普高|普通)?\s*(?:招生)?\s*计划\s*(?:总数?|数|为)?\s*(\d{3,5})\s*人",
    # "XX大学招生总规模7230人"
    r"([一-鿿]{2,8}(?:大学|学院))\s*(?:招生|计划)\s*(?:总)?\s*(?:规模|人数?|名额)\s*(\d{3,5})\s*人",
    # "XX大学计划招生7100人"
    r"([一-鿿]{2,8}(?:大学|学院))\s*计划\s*招生\s*(\d{3,5})\s*人",
    # "XX大学在粤/在广东招生N人"
    r"([一-鿿]{2,8}(?:大学|学院))\s*(?:在粤|在广东|在广东省)?\s*(?:招生|计划)\s*(?:计划)?\s*(\d{3,5})\s*人",
    # "XX大学2026年本科招生7100人"
    r"([一-鿿]{2,8}(?:大学|学院))\s*2026年\s*(?:本科)?\s*(?:招生)?\s*(?:计划)?\s*(\d{3,5})\s*人",
]


def parse_article_for_plans(text: str) -> list[dict]:
    """从文章正文中提取学校+计划数对"""
    results = []

    # 学校名校验和清洗
    # 常见的非学校名前缀词（出现在学校名前面的干扰词）
    NON_SCHOOL_PREFIXES = {"从", "者", "记者", "通讯员", "获悉", "走进", "来到", "来到"}

    def clean_school_name(name: str) -> str | None:
        """从文本中提取最可能是学校名的部分"""
        candidates = []
        for i in range(len(name)):
            for j in range(i + 2, min(i + 10, len(name) + 1)):
                sub = name[i:j]
                if re.match(r"^[一-鿿]+(?:大学|学院)$", sub) and len(sub) >= 4:
                    # 检查第一个词是否是非学校前缀
                    first_word = sub
                    for prefix_len in range(1, 4):
                        if len(sub) > prefix_len and sub[:prefix_len] in NON_SCHOOL_PREFIXES:
                            first_word = sub[prefix_len:]
                            break
                    candidates.append((len(sub), first_word))
        if candidates:
            # 取最长且没有前缀的候选
            candidates.sort(key=lambda x: (-x[0], x[1]))
            return candidates[0][1]
        return None

    # 方法1: 学校名+计划数同时匹配
    for pattern in SCHOOL_PLAN_PATTERNS:
        for match in re.finditer(pattern, text):
            school_name = match.group(1).strip()
            plan_count = int(match.group(2))
            cleaned = clean_school_name(school_name)
            if cleaned and 500 <= plan_count <= 50000:
                # 去重
                if not any(r["school_name"] == cleaned and r["plan_count"] == plan_count for r in results):
                    results.append({
                        "school_name": cleaned,
                        "plan_count": plan_count,
                        "source_text": match.group(0),
                        "confidence": "high",
                    })

    # 方法2: 如果文章开头有学校名，后续的计划数匹配到该学校
    # 按段落处理
    paragraphs = re.split(r"\n+", text)
    current_school = None

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # 检测段落中是否包含学校名
        school_match = re.search(r"([一-鿿]{2,8}(?:大学|学院))", para)
        if school_match:
            raw_name = school_match.group(1)
            current_school = clean_school_name(raw_name) or raw_name

        # 检测计划数
        if current_school:
            for pattern in PLAN_PATTERNS:
                match = re.search(pattern, para)
                if match:
                    plan = int(match.group(1))
                    if 500 <= plan <= 50000:
                        # 检查是否已存在
                        if not any(r["school_name"] == current_school for r in results):
                            results.append({
                                "school_name": current_school,
                                "plan_count": plan,
                                "source_text": para[:80],
                                "confidence": "medium",
                            })
                        break

    return results


def match_to_db_schools(
    extracted: list[dict],
    db_schools: list[dict],
) -> list[dict]:
    """将提取的学校名匹配到数据库中的学校"""
    matched = []

    # 构建DB学校名查找表
    db_names = {s["school_name"]: s for s in db_schools}
    # 模糊匹配：别名、简称
    aliases = {}
    for s in db_schools:
        name = s["school_name"]
        # 各种可能的简称
        aliases[name] = s
        # 去除"广东"、"广州"等前缀
        for prefix in ["广东", "广州", "华南", "中山", "深圳", "汕头", "佛山"]:
            if name.startswith(prefix) and len(name) > 4:
                short = name[len(prefix):]
                aliases[short] = s

    for item in extracted:
        sname = item["school_name"]
        # 精确匹配
        if sname in db_names:
            item["db_school"] = db_names[sname]
            matched.append(item)
            continue

        # 别名匹配
        if sname in aliases:
            item["db_school"] = aliases[sname]
            matched.append(item)
            continue

        # 子串匹配
        for db_name, db_info in db_names.items():
            if sname in db_name or db_name in sname:
                item["db_school"] = db_info
                matched.append(item)
                break

    return matched


# ═════════════════════════════════════════════════════════════════════
#  更新层
# ═════════════════════════════════════════════════════════════════════

def update_school_plan(
    school_info: dict,
    new_total: int,
    article_url: str,
) -> bool:
    """
    更新某所学校在 enrollment_plan 中的2026年计划数据。
    
    策略：在 enrollment_plan 中插入/更新一条汇总记录（标记为 '新闻汇总' 来源）
    """
    conn = get_db()
    try:
        school_code = school_info["school_code"]
        school_name = school_info["school_name"]
        school_level = school_info.get("school_level", "普通本科")
        city = school_info.get("city", "")

        # 检查是否已有2026年汇总记录
        existing = conn.execute("""
            SELECT id, plan_count FROM enrollment_plan
            WHERE year = 2026 AND school_code = ?
              AND group_code = 'NEWS_AGGREGATE'
              AND batch = '本科普通批'
        """, (school_code,)).fetchone()

        if existing:
            if existing["plan_count"] == new_total:
                logger.info(f"  → {school_name}: 计划数无变化 ({new_total})")
                return False
            # 更新
            conn.execute("""
                UPDATE enrollment_plan SET plan_count = ?
                WHERE id = ?
            """, (new_total, existing["id"]))
            logger.info(f"  ✓ {school_name}: 更新计划 {existing['plan_count']} → {new_total}")
        else:
            # 插入汇总记录
            conn.execute("""
                INSERT INTO enrollment_plan
                    (year, province, batch, school_code, school_name,
                     group_code, group_name, major_code, major_name,
                     subject_requirement, subject_track, plan_count, school_level, city)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                2026, "广东", "本科普通批",
                school_code, school_name,
                "NEWS_AGGREGATE", f"2026全校计划({new_total}人)",
                "999999", f"新闻汇总({article_url[:50]})",
                "", "",
                new_total,
                school_level, city,
            ))
            logger.info(f"  ✓ {school_name}: 新增汇总记录 plan_count={new_total}")

        conn.commit()
        return True

    except Exception as e:
        logger.error(f"  ✗ {school_info['school_name']}: 更新失败 - {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


# ═════════════════════════════════════════════════════════════════════
#  编排层
# ═════════════════════════════════════════════════════════════════════

def crawl_roundup_articles() -> list[dict]:
    """搜索并解析汇总型文章（核心入口）

    策略：
      1. 每天只搜前3个关键词，避免触发反爬
      2. 每个关键词轮流使用不同搜索引擎
      3. 保持足够间隔
    """
    all_extracted = []
    seen_urls = set()
    search_count = 0

    logger.info("=" * 60)
    logger.info("阶段1: 搜索汇总型文章（一篇文章含多校数据）")
    logger.info("=" * 60)

    # 每天取4个关键词，按日期轮换，确保不同类型的学校都能覆盖到
    day_of_week = datetime.now().weekday()
    group_size = 4
    start_idx = (day_of_week * group_size) % len(ROUNDUP_QUERIES)
    queries_to_run = ROUNDUP_QUERIES[start_idx:start_idx + group_size]
    if len(queries_to_run) < group_size:
        queries_to_run += ROUNDUP_QUERIES[:group_size - len(queries_to_run)]

    logger.info(f"今日搜索计划 ({datetime.now().strftime('%A')}): {len(queries_to_run)} 个关键词")

    for qi, query in enumerate(queries_to_run):
        if search_count >= MAX_SEARCHES_PER_RUN:
            logger.info(f"  → 已达单次最大搜索数 ({MAX_SEARCHES_PER_RUN})，停止搜索")
            break

        logger.info(f"\n查询 [{qi+1}/{len(queries_to_run)}]: {query}")

        # 轮流使用搜狗和360
        for engine_name in ["sogou", "so360"]:
            if search_count >= MAX_SEARCHES_PER_RUN:
                break

            search_count += 1
            logger.info(f"  引擎 [{search_count}/{MAX_SEARCHES_PER_RUN}]: {engine_name}")

            if engine_name == "sogou":
                html = search_sogou(query)
            else:
                html = search_360(query)

            if not html:
                continue

            # 提取文章URL
            urls = extract_article_urls(html, engine_name)
            logger.info(f"  找到 {len(urls)} 个文章链接")

            article_count = 0
            for url in urls:
                if article_count >= MAX_ARTICLES_PER_RUN // len(queries_to_run):
                    break
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                # 抓取文章
                html_content = fetch_article(url)
                if not html_content:
                    continue

                # 提取正文
                text = extract_article_text(html_content, url)
                if not text:
                    continue

                # 解析计划数据
                extracted = parse_article_for_plans(text)
                if extracted:
                    article_count += 1
                    logger.info(f"    ✓ {url.split('/')[-1][:20]}: 提取到 {len(extracted)} 条数据")
                    for item in extracted:
                        logger.info(f"      {item['school_name']}: {item['plan_count']}人")
                        item["article_url"] = url
                    all_extracted.extend(extracted)

                time.sleep(ARTICLE_DELAY)

    return all_extracted


def crawl_single_schools(
    db_schools: list[dict],
    found_codes: set[str],
    cache: dict,
) -> list[dict]:
    """对未找到的学校逐个搜索"""
    all_extracted = []
    missing = [s for s in db_schools if s["school_code"] not in found_codes]

    logger.info("\n" + "=" * 60)
    logger.info(f"阶段2: 逐个搜索 {len(missing)} 所未覆盖学校")
    logger.info("=" * 60)

    # 限制每次最多搜30个，避免被封
    MAX_SINGLE_SEARCH = 30
    to_search = missing[:MAX_SINGLE_SEARCH]

    for i, school in enumerate(to_search):
        name = school["school_name"]
        code = school["school_code"]

        # 检查缓存（一天内不重复搜）
        cache_key = f"{code}_{name}"
        if cache.get(cache_key, {}).get("found"):
            logger.info(f"  [{i+1}/{len(to_search)}] {name}: 已缓存，跳过")
            continue

        query = SCHOOL_QUERY_TEMPLATE.format(school=name)
        logger.info(f"  [{i+1}/{len(to_search)}] 搜索: {name}")

        html = search_sogou(query)
        if not html:
            html = search_360(query)
        if not html:
            continue

        # 提取文章
        urls = extract_article_urls(html, "sogou")
        if not urls:
            urls = extract_article_urls(html, "so360")

        found_school = False
        for url in urls[:3]:  # 只看前3篇
            html_content = fetch_article(url)
            if not html_content:
                continue

            text = extract_article_text(html_content, url)
            if not text:
                continue

            extracted = parse_article_for_plans(text)
            for item in extracted:
                if name in item["school_name"] or item["school_name"] in name:
                    item["db_school"] = school
                    item["article_url"] = url
                    all_extracted.append(item)
                    # 更新缓存
                    cache[cache_key] = {"found": True, "plan": item["plan_count"], "url": url, "date": datetime.now().isoformat()}
                    logger.info(f"    ✓ 找到 {name}: {item['plan_count']}人")
                    found_school = True
                    break
            if found_school:
                break

        if not found_school:
            cache[cache_key] = {"found": False, "date": datetime.now().isoformat()}

        # 搜索间隔
        time.sleep(1.5)

    return all_extracted


def show_status():
    """显示当前数据覆盖状态"""
    db_schools = load_school_list()
    existing = get_existing_2026_plans()

    total = len(db_schools)
    with_2026 = len([s for s in db_schools if s["plan_2026"] > 0])
    with_news = len([s for s in db_schools if existing.get(s["school_code"], 0) > 0])

    print(f"\n{'='*60}")
    print(f"📊 2026年招生计划数据状态")
    print(f"{'='*60}")
    print(f"  数据库学校总数:     {total}")
    print(f"  已有2026明细数据:   {with_2026} ({with_2026/total*100:.1f}%)")
    print(f"  已有新闻汇总数据:   {with_news} ({with_news/total*100:.1f}%)")
    print()

    # 有空缺的学校类型分布
    missing = [s for s in db_schools if not existing.get(s["school_code"], 0)]
    if missing:
        print(f"  尚未覆盖的学校: {len(missing)}")
        level_dist = defaultdict(int)
        for s in missing:
            level_dist[s.get("school_level", "未知")] += 1
        for level, count in sorted(level_dist.items(), key=lambda x: -x[1]):
            print(f"    {level}: {count}")
        print(f"\n  前20所未覆盖学校:")
        for s in missing[:20]:
            print(f"    {s['school_code']} {s['school_name']} (2025: {s['plan_2025']})")

    # 最近更新的新闻
    cache = load_news_cache()
    found_items = {k: v for k, v in cache.items() if v.get("found")}
    if found_items:
        print(f"\n  最近新闻中找到数据: {len(found_items)} 所学校")
        for k, v in sorted(found_items.items(), key=lambda x: x[1].get("date", ""), reverse=True)[:10]:
            print(f"    {k}: {v.get('plan')}人 ({v.get('date', '')[:10]})")


def main():
    parser = argparse.ArgumentParser(description="每日爬取各高校2026招生计划新闻")
    parser.add_argument("--status", action="store_true", help="显示当前数据状态")
    parser.add_argument("--roundup-only", action="store_true", help="仅搜索汇总型文章（不逐个搜学校）")
    parser.add_argument("--max-schools", type=int, default=30, help="逐个搜索的最大学校数")
    args = parser.parse_args()

    # 创建log目录
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    if args.status:
        show_status()
        return

    setup_logging()

    # 加载数据
    logger.info("加载学校列表...")
    db_schools = load_school_list()
    logger.info(f"共 {len(db_schools)} 所学校")

    cache = load_news_cache()
    existing_2026 = get_existing_2026_plans()

    # ── 阶段1: 汇总型文章 ──
    roundup_results = crawl_roundup_articles()

    # 匹配到DB学校
    matched_roundup = match_to_db_schools(roundup_results, db_schools)
    found_codes = set()

    logger.info(f"\n汇总文章匹配结果: {len(matched_roundup)} 条匹配到DB学校")
    for item in matched_roundup:
        db = item["db_school"]
        code = db["school_code"]
        new_plan = item["plan_count"]
        old_plan = existing_2026.get(code, 0)

        if new_plan != old_plan:
            update_school_plan(db, new_plan, item.get("article_url", ""))
        else:
            logger.info(f"  ~ {db['school_name']}: 计划数与现有一致 ({new_plan})")

        found_codes.add(code)

    # ── 阶段2: 单个学校补漏 ──
    if not args.roundup_only:
        single_results = crawl_single_schools(
            db_schools, found_codes, cache
        )

        for item in single_results:
            db = item["db_school"]
            code = db["school_code"]
            new_plan = item["plan_count"]
            old_plan = existing_2026.get(code, 0)

            if new_plan != old_plan:
                update_school_plan(db, new_plan, item.get("article_url", ""))

    # 保存缓存
    save_news_cache(cache)

    # ── 报告 ──
    logger.info("\n" + "=" * 60)
    logger.info("爬取完成")
    logger.info("=" * 60)

    # 统计
    updated_after = get_existing_2026_plans()
    new_count = len([c for c in updated_after.values() if c > 0])
    logger.info(f"  现有2026计划数据: {new_count}/{len(db_schools)} 所学校")
    logger.info(f"  覆盖率: {new_count/len(db_schools)*100:.1f}%")

    # 哪些学校有变化
    changes = []
    for s in db_schools:
        old = existing_2026.get(s["school_code"], 0)
        new = updated_after.get(s["school_code"], 0)
        if old != new and new > 0:
            changes.append((s["school_name"], old, new, new - old))

    if changes:
        logger.info(f"\n计划变动学校 ({len(changes)}所):")
        for name, old, new, diff in sorted(changes, key=lambda x: -abs(x[3]))[:20]:
            logger.info(f"  {name}: {old} → {new} ({diff:+d})")
    else:
        logger.info("\n本次爬取未发现计划变动")

    # ── 建议执行计划偏移 ──
    if changes:
        logger.info("\n💡 建议: 运行以下命令更新推荐引擎:")
        logger.info("   cd server && python -c \"from services.plan_analysis_service import compute_cumulative_shifts; print('偏移计算完成')\"")
        logger.info("   然后将 config.py 中的 data_year 改为 2026")


if __name__ == "__main__":
    main()
