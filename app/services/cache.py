"""通用 KV 缓存：优先 Redis，不可用时优雅降级为进程内存。

设计动机：
- 项目原先的进程内 dict 缓存（如政策检索结果）进程重启即丢、多进程/多实例间不共享，
  且“超限清空”的策略过于粗暴；
- 这里统一为 **Redis 优先**（REDIS_URL 可配，见 app/core/config.py），Redis 连不上时
  自动退回进程内存并记录告警——单机开发零依赖也能跑，部署多实例时天然共享。

降级语义：
- 初始化时 ping 失败 → 本进程生命周期内不再尝试 Redis（避免每次请求都重试拖慢响应），
  全部走进程内存（带条数上限的 FIFO 淘汰）；
- 运行中 get/set 抛异常 → 本次操作降级内存，并永久停用 Redis（同上）。
"""
from __future__ import annotations

import json
import logging
import threading
from typing import Any, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

try:  # redis 为可选依赖：未安装时同样降级进程内存
    import redis as _redis
except Exception:  # pragma: no cover
    _redis = None


class CacheClient:
    """Redis 优先的 KV 缓存，值以 JSON 序列化存储。"""

    def __init__(self, namespace: str = "trip", url: str = "", memory_limit: int = 256) -> None:
        self._namespace = namespace
        self._memory_limit = memory_limit
        self._memory: dict[str, str] = {}
        self._order: list[str] = []  # 简易 FIFO 淘汰，避免进程内存无界增长
        self._lock = threading.Lock()
        self._url = url or settings.REDIS_URL
        self._client = None
        self._init_redis()

    def _init_redis(self) -> None:
        if _redis is None or not self._url:
            if _redis is None:
                logger.warning("未安装 redis 库，缓存降级为进程内存")
            return
        try:
            client = _redis.Redis.from_url(
                self._url,
                decode_responses=True,
                socket_connect_timeout=0.5,
                socket_timeout=0.5,
            )
            client.ping()
            self._client = client
            logger.info("缓存已连接 Redis：%s", self._url)
        except Exception as exc:  # noqa: BLE001
            self._client = None
            logger.warning("Redis 不可用（%s），缓存降级为进程内存", exc)

    def _key(self, key: str) -> str:
        return f"{self._namespace}:{key}"

    def get(self, key: str) -> Optional[Any]:
        full = self._key(key)
        if self._client is not None:
            try:
                raw = self._client.get(full)
                if raw is not None:
                    return json.loads(raw)
                return None
            except Exception as exc:  # noqa: BLE001
                logger.warning("Redis get 失败，本进程起降级为进程内存：%s", exc)
                self._disable_redis()
        with self._lock:
            raw = self._memory.get(full)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except Exception:  # noqa: BLE001
            return None

    def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        full = self._key(key)
        raw = json.dumps(value, ensure_ascii=False)
        if self._client is not None:
            try:
                self._client.setex(full, max(1, int(ttl)), raw)
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning("Redis set 失败，本进程起降级为进程内存：%s", exc)
                self._disable_redis()
        with self._lock:
            if full not in self._memory:
                self._order.append(full)
            self._memory[full] = raw
            while len(self._order) > self._memory_limit:
                self._memory.pop(self._order.pop(0), None)

    def delete(self, key: str) -> None:
        full = self._key(key)
        if self._client is not None:
            try:
                self._client.delete(full)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Redis delete 失败：%s", exc)
        with self._lock:
            self._memory.pop(full, None)
            if full in self._order:
                self._order.remove(full)

    def _disable_redis(self) -> None:
        """Redis 出现读写异常后，本进程内停用之（后续直接走内存，避免反复重试拖慢请求）。"""
        self._client = None


# 进程级单例：各处共享同一份缓存（政策检索、后续可扩展高德结果等）
cache = CacheClient()
