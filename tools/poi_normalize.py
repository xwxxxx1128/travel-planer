"""景点名称归一化：让同一景点的不同叫法命中同一份评价缓存。

背景：评价缓存（见 reviews 表 / fetch_tavily_reviews）以「景点名」构成 key，
但用户与大模型对同一景点可能用不同叫法（如「小珠山」与「珠山国家森林公园」、
「东方明珠」与「东方明珠广播电视塔」）。精确字符串匹配会导致缓存不命中、
重复调用 Tavily。这里统一做归一化，使不同叫法落到同一个规范名上。

归一化流程：
1) 去掉意图词/修饰词（「的游客评价」「怎么样」等）；
2) 去掉标点与空白；
3) 查别名表（精确 → 包含），命中则替换为规范名。

别名表可在内置字典基础上，通过 config/poi_aliases.json 覆盖/扩展（可选）。
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

# 内置别名表：{别名: 规范名}
_BUILTIN_ALIASES: Dict[str, str] = {
    "小珠山": "珠山国家森林公园",
    "大珠山": "大珠山风景区",
    "东方明珠": "东方明珠广播电视塔",
    "东方明珠塔": "东方明珠广播电视塔",
    "兵马俑": "秦始皇兵马俑博物馆",
    "故宫": "故宫博物院",
    "天安门": "天安门广场",
    "西湖": "西湖风景名胜区",
    "长城": "万里长城",
    "八达岭": "八达岭长城",
    "慕田峪": "慕田峪长城",
}

_ALIAS_FILE = Path(__file__).resolve().parents[1] / "config" / "poi_aliases.json"

# 需要剥离的“意图词/修饰词”（按长度倒序替换，避免子串残留）
_NOISE_WORDS = [
    "的游客真实评价", "的游客评价", "的真实评价", "的用户评价", "的网友评价",
    "游客真实评价", "游客评价", "游客点评", "用户评价", "网友评价", "真实评价",
    "评价", "点评", "口碑", "怎么样", "如何", "好玩吗", "值得去吗", "值得去",
    "推荐吗", "攻略", "游记",
]

_PUNCT_RE = re.compile(r"[\s,，。.、;；:：!！?？~～\-—_/\\'\"“”‘’()（）\[\]【】<>《》]+")


def _load_aliases() -> Dict[str, str]:
    aliases = dict(_BUILTIN_ALIASES)
    try:
        if _ALIAS_FILE.exists():
            with open(_ALIAS_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                aliases.update({str(k): str(v) for k, v in data.items()})
                logger.info("已加载景点别名表 %s（共 %d 条）", _ALIAS_FILE, len(aliases))
    except Exception as exc:  # noqa: BLE001
        logger.warning("加载景点别名表失败（%s）：%s", _ALIAS_FILE, exc)
    return aliases


_ALIASES = _load_aliases()


def _strip_noise(text: str) -> str:
    for word in sorted(_NOISE_WORDS, key=len, reverse=True):
        text = text.replace(word, "")
    return text


def normalize_poi_name(raw: str) -> str:
    """把任意写法的景点名归一化为规范名；无法识别时返回清洗后的原名。"""
    if not raw:
        return ""
    text = _strip_noise(str(raw).strip())
    text = _PUNCT_RE.sub("", text)
    if not text:
        return ""
    if text in _ALIASES:
        return _ALIASES[text]
    # 包含匹配：问句里常出现「青岛小珠山」这类“城市+景点”的写法
    for alias, canonical in _ALIASES.items():
        if alias and alias in text:
            return canonical
    return text


def cache_key(poi_name: str, city: str = "") -> str:
    """生成评价缓存的规范化 key：城市 + 规范景点名。

    统一在此拼装，保证写入与读取使用同一 key，从而实现“同景点不同叫法走同一缓存”。
    """
    return f"{normalize_poi_name(city)}::{normalize_poi_name(poi_name)}"
