import httpx
from langchain_core.tools import tool
from app.core.runtime_config import get_runtime_config

AMAP_BASE_URL = "https://restapi.amap.com/v3"

# 模块级共享 HTTP client：原实现每次工具调用都新建 httpx.Client（含 TLS 握手），
# 高德类工具在一次会话中可能被多次调用，复用连接池可省掉重复握手开销。
_amap_client = httpx.Client(timeout=10.0)


def get_amap_api_key() -> str:
    return get_runtime_config().amap_web_key


def _amap_search_text(keywords, city=None, types=None, page_size=10) -> dict:
    """调用高德地点搜索接口，返回结构化字典（含 status / info / pois）。"""
    amap_api_key = get_amap_api_key()
    if not amap_api_key:
        return {
            "status": "0",
            "info": "缺少高德地图 API Key，请在 .env 中配置 AMAP_WEB_API_KEY。",
            "pois": [],
        }
    params = {
        "key": amap_api_key,
        "keywords": keywords,
        "offset": page_size,
        "extensions": "all",
    }
    if city:
        params["city"] = city
    if types:
        params["types"] = types
    try:
        response = _amap_client.get(f"{AMAP_BASE_URL}/place/text", params=params)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        return {"status": "0", "info": f"高德地图接口调用失败: {exc}", "pois": []}

    if data.get("status") != "1":
        return {
            "status": data.get("status", "0"),
            "info": data.get("info", "未知错误"),
            "pois": [],
        }

    return {"status": "1", "info": data.get("info", ""), "pois": data.get("pois", [])}


@tool(description="根据关键词在高德地图搜索 POI（如酒店、景点），返回格式化文本结果。")
def amap_search_poi(keywords, city=None, types=None, page_size=10) -> str:
    data = _amap_search_text(keywords, city, types, page_size)
    if data.get("status") != "1":
        return f"高德地图查询失败: {data.get('info', '未知错误')}"
    results = []
    for poi in data.get("pois", []):
        biz = poi.get("biz_extensions") or poi.get("biz_extension") or {}
        results.append(
            {
                "name": poi.get("name", ""),
                "rating": biz.get("rating", ""),
                "type": poi.get("type", ""),
                "address": poi.get("address", ""),
                "tel": poi.get("tel", ""),
                "cost": biz.get("cost", ""),
                "location": poi.get("location", ""),
            }
        )
    return str(results)


def amap_search_poi_raw(keywords, city=None, types=None, page_size=10) -> dict:
    """结构化版本：直接返回高德原始 POI 字典列表，供后端服务取用。"""
    return _amap_search_text(keywords, city, types, page_size)


@tool(description="在高德地图中搜索指定坐标周边的 POI（景点/餐厅/酒店等），适合根据落点推荐附近去处。")
def amap_search_around(location, keywords="", radius=1000, types="") -> str:
    amap_api_key = get_amap_api_key()
    if not amap_api_key:
        return "缺少高德地图 API Key，请在 .env 中配置 AMAP_WEB_API_KEY。"
    params = {
        "key": amap_api_key,
        "location": location,
        "radius": radius,
        "sortrule": "distance",
        "offset": 10,
        "extensions": "all",
    }
    if keywords:
        params["keywords"] = keywords
    if types:
        params["types"] = types
    try:
        response = _amap_client.get(f"{AMAP_BASE_URL}/place/around", params=params)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        return f"高德地图周边搜索失败: {exc}"

    if data.get("status") != "1":
        return f"高德地图周边搜索失败: {data.get('info', '未知错误')}"

    results = []
    for poi in data.get("pois", []):
        biz = poi.get("biz_extensions") or poi.get("biz_extension") or {}
        results.append(
            {
                "name": poi.get("name", ""),
                "type": poi.get("type", ""),
                "address": poi.get("address", ""),
                "distance": poi.get("distance", ""),
                "location": poi.get("location", ""),
                "rating": biz.get("rating", ""),
            }
        )
    return str(results)


@tool(description="根据地址进行地理编码，返回经纬度等位置信息。")
def amap_geocode(address) -> str:
    amap_api_key = get_amap_api_key()
    if not amap_api_key:
        return "缺少高德地图 API Key，请在 .env 中配置 AMAP_WEB_API_KEY。"
    try:
        response = _amap_client.get(
            f"{AMAP_BASE_URL}/geocode/geo",
            params={"address": address, "key": amap_api_key},
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        return f"高德地图地理编码失败: {exc}"

    if data.get("status") == "1" and data.get("geocodes"):
        geo = data["geocodes"][0]
        return str(
            {
                "formatted_address": geo.get("formatted_address", ""),
                "location": geo.get("location", ""),
                "province": geo.get("province", ""),
                "city": geo.get("city", ""),
                "district": geo.get("district", ""),
            }
        )
    return f"高德地图地理编码失败: {data.get('info', '未知错误')}"


# --------------------------------------------------------------------------- #
# 结构化辅助函数（供后端 API 路由直接调用，返回 dict 而非字符串）
# --------------------------------------------------------------------------- #
def amap_geocode_raw(address: str, city: str = "") -> dict:
    """地理编码，返回结构化字典；前端 /api/geocode/ 使用。"""
    amap_api_key = get_amap_api_key()
    if not amap_api_key:
        return {"success": False, "message": "缺少高德地图 API Key"}
    params = {"address": address, "key": amap_api_key}
    if city:
        params["city"] = city
    try:
        response = _amap_client.get(f"{AMAP_BASE_URL}/geocode/geo", params=params)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        return {"success": False, "message": f"高德地图地理编码失败: {exc}"}
    if data.get("status") == "1" and data.get("geocodes"):
        geo = data["geocodes"][0]
        return {
            "success": True,
            "formatted_address": geo.get("formatted_address", ""),
            "address": geo.get("formatted_address", ""),
            "name": geo.get("formatted_address") or address,
            "location": geo.get("location", ""),
            "province": geo.get("province", ""),
            "city": geo.get("city", ""),
            "district": geo.get("district", ""),
        }
    return {"success": False, "message": data.get("info", "未找到地址")}


def amap_reverse_geocode(lng: float, lat: float) -> dict:
    """逆地理编码：经纬度 -> 地址信息；前端 /api/reverse-geocode/ 使用。"""
    amap_api_key = get_amap_api_key()
    if not amap_api_key:
        return {"success": False, "message": "缺少高德地图 API Key"}
    location = f"{lng},{lat}"
    try:
        response = _amap_client.get(
            f"{AMAP_BASE_URL}/geocode/regeo",
            params={"key": amap_api_key, "location": location, "output": "json", "extensions": "base"},
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        return {"success": False, "message": f"高德地图逆地理编码失败: {exc}"}
    if data.get("status") == "1":
        regeo = data.get("regeocode", {})
        comp = regeo.get("addressComponent", {})
        return {
            "success": True,
            "formatted_address": regeo.get("formatted_address", ""),
            "address": regeo.get("formatted_address", ""),
            "name": regeo.get("formatted_address") or location,
            "province": comp.get("province", ""),
            "city": comp.get("city", ""),
            "district": comp.get("district", ""),
            "adcode": comp.get("adcode", ""),
            "township": comp.get("township", ""),
            "street": comp.get("streetNumber", {}).get("street", ""),
        }
    return {"success": False, "message": data.get("info", "逆地理编码失败")}


def amap_inputtips(keywords: str, city: str = "") -> dict:
    """高德输入提示（智能匹配推荐）；前端 /api/inputtips/ 使用。"""
    amap_api_key = get_amap_api_key()
    if not amap_api_key:
        return {"success": False, "message": "缺少高德地图 API Key", "tips": []}
    params = {"key": amap_api_key, "keywords": keywords, "output": "json"}
    if city:
        params["city"] = city
    try:
        response = _amap_client.get(f"{AMAP_BASE_URL}/assistant/inputtips", params=params)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        return {"success": False, "message": f"高德地图输入提示失败: {exc}", "tips": []}
    if data.get("status") == "1":
        tips = []
        for tip in data.get("tips", []):
            tips.append(
                {
                    "id": tip.get("id", ""),
                    "name": tip.get("name", ""),
                    "district": tip.get("district", ""),
                    "address": tip.get("address", ""),
                    "location": tip.get("location", ""),
                    "adcode": tip.get("adcode", ""),
                }
            )
        return {"success": True, "tips": tips}
    return {"success": False, "message": data.get("info", "输入提示获取失败"), "tips": []}


def amap_search_around_raw(location: str, radius: int = 1000, types: str = "", limit: int = 10) -> dict:
    """结构化周边搜索；前端 /api/nearby-poi/ 使用，返回 {success, pois}。"""
    amap_api_key = get_amap_api_key()
    if not amap_api_key:
        return {"success": False, "message": "缺少高德地图 API Key", "pois": []}
    params = {
        "key": amap_api_key,
        "location": location,
        "radius": radius,
        "sortrule": "distance",
        "offset": limit,
        "extensions": "all",
    }
    if types:
        params["types"] = types
    try:
        response = _amap_client.get(f"{AMAP_BASE_URL}/place/around", params=params)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        return {"success": False, "message": f"高德地图周边搜索失败: {exc}", "pois": []}
    if data.get("status") == "1":
        pois = []
        for poi in data.get("pois", []):
            biz = poi.get("biz_extensions") or poi.get("biz_extension") or {}
            pois.append(
                {
                    "id": poi.get("id", ""),
                    "name": poi.get("name", ""),
                    "type": poi.get("type", ""),
                    "address": poi.get("address", ""),
                    "distance": poi.get("distance", ""),
                    "location": poi.get("location", ""),
                    "rating": biz.get("rating", ""),
                }
            )
        return {"success": True, "pois": pois}
    return {"success": False, "message": data.get("info", "未找到周边POI"), "pois": []}
