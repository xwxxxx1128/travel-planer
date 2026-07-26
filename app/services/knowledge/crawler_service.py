"""景点评价真实爬虫服务。

- 使用 requests + BeautifulSoup 实时抓取公开网页中的游客评价/点评内容；
- 抓取结果按景点名写入本地 JSON 缓存（crawl_cache/），并支持增量刷新；
- 网络不可用时优雅降级为占位样例（source 标记为 sample），保证链路可用。
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from app.core.config import settings

logger = logging.getLogger(__name__)

USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
)


@dataclass
class CrawlRequest:
    poi_name: str
    city: str | None = None
    category: str = 'poi'
    force_refresh: bool = False


class IncrementalCrawlerService:
    """按需增量爬取：用户选中/询问 POI 才触发。"""

    def __init__(self, cache_dir: Path | None = None, max_age_hours: int = 24) -> None:
        self.cache_dir = cache_dir or (Path(settings.CHROMA_PERSIST_DIR).parent / 'crawl_cache')
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_age_hours = max_age_hours
        self.session = requests.Session()
        self.session.headers.update(
            {
                'User-Agent': USER_AGENT,
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }
        )

    # ---------- 缓存 ----------
    def _cache_file(self, poi_name: str) -> Path:
        safe_name = ''.join(ch for ch in poi_name if ch.isalnum() or ch in ('-', '_', ' ')).strip().replace(' ', '_')
        return self.cache_dir / f'{safe_name or "poi"}.json'

    def need_refresh(self, poi_name: str, max_age_hours: int | None = None) -> bool:
        max_age = max_age_hours if max_age_hours is not None else self.max_age_hours
        cache_file = self._cache_file(poi_name)
        if not cache_file.exists():
            return True
        modified_at = datetime.fromtimestamp(cache_file.stat().st_mtime)
        return datetime.now() - modified_at > timedelta(hours=max_age)

    # ---------- 对外主入口 ----------
    def crawl_reviews(self, request: CrawlRequest) -> list[dict]:
        cache_file = self._cache_file(request.poi_name)
        if (not request.force_refresh) and cache_file.exists() and not self.need_refresh(request.poi_name):
            try:
                return json.loads(cache_file.read_text(encoding='utf-8'))
            except Exception:
                pass  # 缓存损坏则重新抓取

        reviews = self._fetch_real_reviews(request)
        reviews = self._filter_relevant(reviews, request)
        if not reviews:
            logger.warning('「%s」实时抓取未命中相关内容，使用占位样例兜底', request.poi_name)
            reviews = self._sample_reviews(request)
            for item in reviews:
                item['source'] = 'sample'

        cache_file.write_text(json.dumps(reviews, ensure_ascii=False, indent=2), encoding='utf-8')
        return reviews

    @staticmethod
    def _filter_relevant(reviews: list[dict], request: CrawlRequest) -> list[dict]:
        """优先保留与景点相关的片段，但不再丢弃未精确命中的真实结果。

        旧逻辑要求摘要里逐字包含景点名/城市名，否则整段丢弃并回退占位样例，
        导致真实抓取结果常被误杀。这里改为按相关度排序后全部保留（最多 10 条），
        仅当确实没有任何抓取结果时才由调用方兜底占位。
        """
        if not reviews:
            return reviews

        poi = request.poi_name or ''
        city = request.city or ''

        def _score(item: dict) -> int:
            content = item.get('content', '')
            score = 0
            if poi and poi in content:
                score += 2
            if city and city in content:
                score += 1
            return score

        ordered = sorted(reviews, key=_score, reverse=True)
        return ordered[:10]

    # ---------- 真实抓取 ----------
    def _fetch_real_reviews(self, request: CrawlRequest) -> list[dict]:
        query = request.poi_name
        if request.city:
            query = f'{request.city} {request.poi_name}'
        query = f'{query} 景点 游客真实评价 点评'
        url = 'https://www.bing.com/search?q=' + quote_plus(query)
        try:
            resp = self.session.get(url, timeout=6)  # 超时快速失败，走离线样例兜底，避免前端久等
            resp.raise_for_status()
        except Exception as exc:  # 网络异常：返回空，由调用方兜底
            logger.warning('抓取请求失败: %s', exc)
            return []

        return self._parse_bing_snippets(resp.text, request)

    def _parse_bing_snippets(self, html: str, request: CrawlRequest) -> list[dict]:
        soup = BeautifulSoup(html, 'html.parser')
        reviews: list[dict] = []
        blocks = soup.select('li.b_algo') or soup.select('.b_algo')
        for block in blocks:
            caption = block.select_one('.b_caption p') or block.select_one('p')
            title_tag = block.select_one('h2')
            if not caption:
                continue
            text = caption.get_text(' ', strip=True)
            if len(text) < 20:  # 过滤过短的噪声片段
                continue
            link = ''
            if title_tag:
                a = title_tag.find('a')
                if a and a.get('href'):
                    link = a['href']
            reviews.append(
                {
                    'poi_name': request.poi_name,
                    'city': request.city,
                    'source': 'web-crawl',
                    'url': link,
                    'rating': None,
                    'label': '游客点评',
                    'content': text,
                }
            )
            if len(reviews) >= 8:
                break

        if not reviews:  # Bing 结构变化兜底：抓取所有结果段落
            for p in soup.select('#b_results p')[:8]:
                text = p.get_text(' ', strip=True)
                if len(text) >= 20:
                    reviews.append(
                        {
                            'poi_name': request.poi_name,
                            'city': request.city,
                            'source': 'web-crawl',
                            'url': '',
                            'rating': None,
                            'label': '游客点评',
                            'content': text,
                        }
                    )
        return reviews

    # ---------- 占位兜底（仅实时抓取失败时使用） ----------
    def _sample_reviews(self, request: CrawlRequest) -> list[dict]:
        name = request.poi_name
        return [
            {
                'poi_name': name,
                'city': request.city,
                'source': 'sample',
                'rating': 4.8,
                'label': '推荐',
                'content': f'{name} 适合打卡，评论普遍认为风景好、拍照出片。',
            },
            {
                'poi_name': name,
                'city': request.city,
                'source': 'sample',
                'rating': 4.5,
                'label': '注意排队',
                'content': f'{name} 周末人流较大，建议错峰前往。',
            },
        ]
