import httpx
from typing import Dict
from langchain_core.tools import tool
from dotenv import load_dotenv

from app.core.runtime_config import get_runtime_config

load_dotenv()

AMAP_WEATHER_URL = "https://restapi.amap.com/v3/weather/weatherInfo"
AMAP_GEO_URL = "https://restapi.amap.com/v3/geocode/geo"

_adcode_cache: Dict[str, str] = {}


def get_amap_key() -> str:
    """从运行时配置读取高德 Web API Key。"""
    try:
        return get_runtime_config().amap_web_key or ""
    except Exception:
        return ""


def _resolve_adcode(location: str) -> str:
    """把城市名/地址解析为 adcode（高德天气接口需要 adcode）。"""
    if not location:
        return ""
    if location.isdigit():
        return location
    if location in _adcode_cache:
        return _adcode_cache[location]
    key = get_amap_key()
    adcode = ""
    if key:
        try:
            response = httpx.get(
                AMAP_GEO_URL,
                params={"key": key, "address": location, "output": "json"},
                timeout=8,
            )
            data = response.json()
            geocodes = data.get("geocodes") or []
            if geocodes:
                adcode = geocodes[0].get("adcode", "") or ""
        except Exception:
            adcode = ""
    _adcode_cache[location] = adcode
    return adcode


@tool(description="获取天气信息工具，根据位置获取当前实时天气（高德地图天气）")
def amap_get_weather(location: str) -> str:
    """
    根据位置（城市名或经纬度）获取实时天气。\n
    返回包含天气现象、温度、风向、风力、湿度的字符串。\n
    参数:\n
    - location: 城市名（如“北京”）或 "经度,纬度"\n
    """
    key = get_amap_key()
    if not key:
        return "错误：未配置高德地图 Web API Key，无法获取天气。"
    city = _resolve_adcode(location)
    if not city:
        return f"错误：无法解析城市或坐标 '{location}'，请提供更明确的城市名称。"
    try:
        response = httpx.get(
            AMAP_WEATHER_URL,
            params={"key": key, "city": city, "extensions": "base", "output": "json"},
            timeout=10,
        )
        data = response.json()
        if data.get("status") == "1" and data.get("lives"):
            live = data["lives"][0]
            result = {
                "城市": live.get("city", ""),
                "天气": live.get("weather", ""),
                "温度": live.get("temperature", ""),
                "风向": live.get("winddirection", ""),
                "风力": live.get("windpower", ""),
                "湿度": live.get("humidity", ""),
                "发布时间": live.get("reporttime", ""),
            }
            return str(result)
        return f"天气查询失败：{data.get('info', '未知错误')}"
    except Exception as e:
        return f"天气查询异常：{str(e)}"


@tool(description="获取未来天气预报工具，根据位置获取未来几天的天气预报（高德地图天气）")
def amap_get_forecast(location: str, days: int = 3) -> str:
    """
    根据位置（城市名或经纬度）获取未来天气预报。\n
    返回未来若干天的白天/夜间天气与高低温。\n
    参数:\n
    - location: 城市名（如“北京”）或 "经度,纬度"\n
    - days: 预报天数，默认 3，最多 7\n
    """
    key = get_amap_key()
    if not key:
        return "错误：未配置高德地图 Web API Key，无法获取天气预报。"
    city = _resolve_adcode(location)
    if not city:
        return f"错误：无法解析城市或坐标 '{location}'，请提供更明确的城市名称。"
    days = max(1, min(int(days or 3), 7))
    try:
        response = httpx.get(
            AMAP_WEATHER_URL,
            params={"key": key, "city": city, "extensions": "all", "output": "json"},
            timeout=10,
        )
        data = response.json()
        if data.get("status") == "1" and data.get("forecasts"):
            casts = data["forecasts"][0].get("casts", [])
            forecast = []
            for cast in casts[:days]:
                forecast.append({
                    "日期": cast.get("date", ""),
                    "星期": cast.get("week", ""),
                    "白天天气": cast.get("dayweather", ""),
                    "夜间天气": cast.get("nightweather", ""),
                    "最高温": cast.get("daytemp", ""),
                    "最低温": cast.get("nighttemp", ""),
                    "白天风向": cast.get("daywind", ""),
                    "白天风力": cast.get("daypower", ""),
                })
            result = {"城市": data["forecasts"][0].get("city", ""), "预报": forecast}
            return str(result)
        return f"天气预报查询失败：{data.get('info', '未知错误')}"
    except Exception as e:
        return f"天气预报查询异常：{str(e)}"
