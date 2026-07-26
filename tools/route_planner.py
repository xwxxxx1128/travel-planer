import itertools
import json
from concurrent.futures import ThreadPoolExecutor
from math import sqrt
from typing import Any, Dict, List, Tuple

import httpx
from langchain_core.tools import tool

from app.core.runtime_config import get_runtime_config

def get_amap_key() -> str:
    return get_runtime_config().amap_web_key
SUPPORTED_ROUTE_MODES = {"driving", "walking", "transit"}
MODE_LABELS = {
    "driving": "驾车",
    "walking": "步行",
    "transit": "公共交通",
    "smart": "智能推荐",
}


def _normalize_mode(mode: str) -> str:
    if mode in SUPPORTED_ROUTE_MODES or mode == "smart":
        return mode
    return "driving"


def _route_endpoint(mode: str) -> str:
    if mode == "walking":
        return "walking"
    if mode == "transit":
        return "transit/integrated"
    return "driving"


def _format_distance(distance_m: int) -> str:
    return f"{distance_m}米（约{round(distance_m / 1000, 1)}公里）"


def _format_duration(duration_s: int) -> str:
    return f"{duration_s}秒（约{round(duration_s / 60, 1)}分钟）"


def _infer_suggested_mode(distance_m: int) -> str:
    if distance_m <= 1500:
        return "walking"
    elif distance_m <= 10000:
        return "transit"
    return "driving"


def _fallback_segment(origin: Dict[str, Any], destination: Dict[str, Any], mode: str) -> Dict[str, Any]:
    lng1, lat1 = origin["lng"], origin["lat"]
    lng2, lat2 = destination["lng"], destination["lat"]
    distance_km = sqrt((lng1 - lng2) ** 2 + (lat1 - lat2) ** 2) * 111
    speed_kmh = {"walking": 5, "driving": 35, "transit": 20}.get(mode, 30)
    duration_min = max(1, int(round(distance_km / speed_kmh * 60)))
    distance_m = int(distance_km * 1000)
    duration_s = duration_min * 60
    return {
        "distance": distance_m,
        "duration": duration_s,
        "distance_km": round(distance_m / 1000, 1),
        "duration_minutes": round(duration_s / 60, 1),
        "note": "本地估算",
        "is_estimate": True,
    }


def _geocode_point(point: str) -> Dict[str, Any]:
    amap_key = get_amap_key()
    if not amap_key:
        raise ValueError("未配置高德地图API Key")

    geocode_url = f"https://restapi.amap.com/v3/geocode/geo?address={point}&key={amap_key}"
    response = httpx.get(geocode_url, timeout=10)
    data = response.json()

    if data.get("status") == "1" and data.get("geocodes"):
        geocode = data["geocodes"][0]
        location = geocode["location"]
        lng, lat = location.split(",")
        return {
            "name": geocode.get("formatted_address") or point,
            "location": location,
            "lng": float(lng),
            "lat": float(lat),
        }
    raise ValueError(f"无法找到地点 '{point}' 的坐标")


def _parse_point_value(point: str | Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(point, str):
        return _geocode_point(point)

    name = point.get("name") or point.get("address") or "未命名地点"
    location = point.get("location")
    lng = point.get("lng")
    lat = point.get("lat")

    if location:
        if isinstance(location, str) and "," in location:
            lng_text, lat_text = location.split(",", 1)
            return {
                "name": name,
                "location": location,
                "lng": float(lng_text),
                "lat": float(lat_text),
            }
        raise ValueError("地点 location 格式不正确")

    if lng is not None and lat is not None:
        return {
            "name": name,
            "location": f"{float(lng)},{float(lat)}",
            "lng": float(lng),
            "lat": float(lat),
        }

    return _geocode_point(name)


def _decode_amap_polyline(polyline_str: str) -> list:
    """高德地图 polyline 解析 -> [[lng, lat], ...]

    AMap 路径规划 API（驾车/步行/公交 integrated）返回的 polyline 字段
    格式为绝对坐标串："lng1,lat1;lng2,lat2;..."，每一对都是完整的经纬度，
    不是差分值，不能累加（之前误以为是差分编码会导致坐标严重发散）。
    """
    if not polyline_str:
        return []
    points = []
    for segment in polyline_str.split(";"):
        segment = segment.strip()
        if not segment:
            continue
        parts = segment.split(",")
        if len(parts) >= 2:
            try:
                lng = float(parts[0])
                lat = float(parts[1])
                # 过滤明显异常的坐标，防止空串/异常数据污染路径
                if -180.0 <= lng <= 180.0 and -90.0 <= lat <= 90.0:
                    points.append([lng, lat])
            except (ValueError, TypeError):
                continue
    return points


def _collect_path_from_driving_steps(path_item: dict) -> list:
    """从驾车/步行 API 的 steps 中收集完整 polyline 路径"""
    path = []
    for step in path_item.get("steps", []):
        poly = step.get("polyline", "")
        path.extend(_decode_amap_polyline(poly))
    return path


_adcode_cache: Dict[str, str] = {}


def _adcode_of(location: str) -> str:
    """根据经纬度反查所在城市 adcode（高德 transit 公交规划接口必须传 city 参数）。"""
    if not location:
        return ""
    if location in _adcode_cache:
        return _adcode_cache[location]
    amap_key = get_amap_key()
    adcode = ""
    if amap_key:
        try:
            response = httpx.get(
                "https://restapi.amap.com/v3/geocode/regeo",
                params={"key": amap_key, "location": location, "output": "json"},
                timeout=8,
            )
            data = response.json()
            adcode = (
                data.get("regeocode", {})
                .get("addressComponent", {})
                .get("adcode", "")
                or ""
            )
        except Exception:
            adcode = ""
    _adcode_cache[location] = adcode
    return adcode


def _direction_segment(origin: Dict[str, Any], destination: Dict[str, Any], mode: str) -> Dict[str, Any]:
    mode = (mode or "driving").lower()
    amap_key = get_amap_key()

    # 智能模式：先用本地估算挑选最合适的交通方式，再调用真实接口
    if mode == "smart":
        estimate = _fallback_segment(origin, destination, "smart")
        mode = _infer_suggested_mode(estimate["distance"])

    route_mode = _route_endpoint(mode)
    if not amap_key or mode not in SUPPORTED_ROUTE_MODES:
        return _fallback_segment(origin, destination, mode)

    params = {
        "origin": origin["location"],
        "destination": destination["location"],
        "key": amap_key,
        "output": "json",
    }
    if route_mode == "transit/integrated":
        city = _adcode_of(origin["location"])
        if city:
            params["city"] = city

    try:
        response = httpx.get(
            f"https://restapi.amap.com/v3/direction/{route_mode}",
            params=params,
            timeout=20,
        )
        data = response.json()
    except Exception:
        return _fallback_segment(origin, destination, mode)

    if data.get("status") != "1" or not data.get("route"):
        return _fallback_segment(origin, destination, mode)

    # ---- 公共交通：高德返回 route.transits（不是 route.paths） ----
    if mode == "transit":
        transits = data["route"].get("transits", [])
        if not transits:
            return _fallback_segment(origin, destination, mode)

        transit = transits[0]
        distance = int(float(transit.get("distance", 0)))
        duration = int(float(transit.get("duration", 0)))

        steps = []
        path = []
        for seg in transit.get("segments", []):
            # 步行段
            walking = seg.get("walking", {})
            if walking:
                for ws in walking.get("steps", []):
                    path.extend(_decode_amap_polyline(ws.get("polyline", "")))

            # 公交/地铁段
            bus = seg.get("bus", {})
            buslines = bus.get("buslines", [])
            for bl in buslines:
                path.extend(_decode_amap_polyline(bl.get("polyline", "")))
                line_type = bl.get("type", "") or ""
                line_kind = "地铁" if "地铁" in line_type else "公交"
                dep_name = bl.get("departure_stop", {}).get("name", "起点")
                arr_name = bl.get("arrival_stop", {}).get("name", "终点")
                steps.append({
                    "line_name": bl.get("name", "公交"),
                    "line_type": line_type,
                    "line_kind": line_kind,
                    "departure": {
                        "name": dep_name,
                        "stop": dep_name,
                    },
                    "arrival": {
                        "name": arr_name,
                        "stop": arr_name,
                    },
                    "distance": int(float(bl.get("distance", 0))),
                    "duration": int(float(bl.get("duration", 0))),
                    "instruction": f"乘坐{bl.get('name', '公车')}，从 {dep_name} 到 {arr_name}",
                })

            # 跨段步行衔接
            for rs in seg.get("railway", {}).get("steps", []):
                path.extend(_decode_amap_polyline(rs.get("polyline", "")))

        return {
            "distance": distance,
            "duration": duration,
            "distance_km": round(distance / 1000, 1),
            "duration_minutes": round(duration / 60, 1),
            "path": path,
            "transit_steps": steps,
        }

    # ---- 驾车 / 步行 ----
    paths = data["route"].get("paths", [])
    if not paths:
        return _fallback_segment(origin, destination, mode)

    path_item = paths[0]
    distance = int(float(path_item.get("distance", 0)))
    duration = int(float(path_item.get("duration", 0)))

    return {
        "distance": distance,
        "duration": duration,
        "distance_km": round(distance / 1000, 1),
        "duration_minutes": round(duration / 60, 1),
        "path": _collect_path_from_driving_steps(path_item),
    }


def _evaluate_order(order: Tuple[int, ...], locations: List[Dict[str, Any]], cache: Dict[Tuple[int, int], Dict[str, Any]]) -> Tuple[int, int]:
    total_distance = 0
    total_duration = 0
    for index in range(len(order) - 1):
        segment = cache[(order[index], order[index + 1])]
        total_distance += segment["distance"]
        total_duration += segment["duration"]
    return total_distance, total_duration


def _build_route_result(
    order: Tuple[int, ...],
    locations: List[Dict[str, Any]],
    cache: Dict[Tuple[int, int], Dict[str, Any]],
    transport_mode: str,
) -> Dict[str, Any]:
    ordered_points = [locations[index] for index in order]
    segments = []
    total_distance = 0
    total_duration = 0

    for index in range(len(order) - 1):
        from_index = order[index]
        to_index = order[index + 1]
        from_point = locations[from_index]
        to_point = locations[to_index]
        cached = cache[(from_index, to_index)]
        segment = cached.copy()
        suggested_mode = transport_mode if transport_mode != "smart" else _infer_suggested_mode(segment["distance"])
        # 使用后端返回的真实 polyline，否则 fallback 为起点-终点直线
        real_path = cached.get("path") if isinstance(cached.get("path"), list) and len(cached.get("path")) >= 2 else None
        segment.update(
            {
                "from": from_point["name"],
                "to": to_point["name"],
                "from_location": from_point["location"],
                "to_location": to_point["location"],
                "transport_mode": suggested_mode,
                "transport_mode_label": MODE_LABELS.get(suggested_mode, "驾车"),
                "path": real_path or [
                    [from_point["lng"], from_point["lat"]],
                    [to_point["lng"], to_point["lat"]],
                ],
            }
        )
        # transit_steps 由 _direction_segment 直接写入 cache，不要丢失
        if "transit_steps" in cached and "transit_steps" not in segment:
            segment["transit_steps"] = cached["transit_steps"]
        segments.append(segment)
        total_distance += segment["distance"]
        total_duration += segment["duration"]

    return {
        "optimal_order": [point["name"] for point in ordered_points],
        "ordered_points": ordered_points,
        "segments": segments,
        "total_distance_m": total_distance,
        "total_duration_s": total_duration,
        "total_distance": _format_distance(total_distance),
        "total_time": _format_duration(total_duration),
        "transport_mode": transport_mode,
        "transport_mode_label": MODE_LABELS.get(transport_mode, "驾车"),
    }


def optimize_route(locations: List[Dict[str, Any]], transport_mode: str = "driving", fixed_end_index: int | None = None) -> Dict[str, Any]:
    if len(locations) <= 1:
        point = locations[0]
        return {
            "optimal_order": [point["name"]],
            "ordered_points": locations,
            "segments": [],
            "total_distance_m": 0,
            "total_duration_s": 0,
            "total_distance": "0米（约0.0公里）",
            "total_time": "0秒（约0.0分钟）",
            "transport_mode": transport_mode,
            "transport_mode_label": MODE_LABELS.get(transport_mode, "驾车"),
        }

    route_mode = _normalize_mode(transport_mode)
    cache: Dict[Tuple[int, int], Dict[str, Any]] = {}

    # 关键优化：原实现逐对串行调用高德方向 API，N 个点需 n*(n-1) 次请求，
    # 8 点即 56 次串行 HTTP（每次 1-2s）→ 累计 1-2 分钟。
    # 这里用线程池并发请求所有点对（I/O 密集，线程池即可大幅加速），
    # 8 点从 ~60s 降到 ~3-5s。上限按点对数量动态取，避免无谓的大池。
    pairs = list(itertools.permutations(range(len(locations)), 2))
    max_workers = min(len(pairs), 8)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        # 提交所有点对任务，记录 (origin_idx, dest_idx) -> future
        future_map = {
            (o, d): pool.submit(
                _direction_segment,
                locations[o],
                locations[d],
                route_mode,
            )
            for (o, d) in pairs
        }
        for (o, d), fut in future_map.items():
            cache[(o, d)] = fut.result()

    exact_limit = 8
    start_fixed = locations[0].get("kind") == "start"
    end_fixed = fixed_end_index is not None

    if len(locations) <= exact_limit:
        if start_fixed and end_fixed:
            middle_indexes = [index for index in range(1, len(locations)) if index != fixed_end_index]
            candidate_orders = ((0,) + perm + (fixed_end_index,) for perm in itertools.permutations(middle_indexes))
        elif start_fixed:
            candidate_orders = ((0,) + perm for perm in itertools.permutations(range(1, len(locations))))
        elif end_fixed:
            middle_indexes = [index for index in range(len(locations)) if index != fixed_end_index]
            candidate_orders = (perm + (fixed_end_index,) for perm in itertools.permutations(middle_indexes))
        else:
            candidate_orders = itertools.permutations(range(len(locations)))

        best_order = None
        best_score = None
        for order in candidate_orders:
            score = _evaluate_order(order, locations, cache)
            if best_score is None or score < best_score:
                best_order = order
                best_score = score

        if best_order is None:
            best_order = tuple(range(len(locations)))

        return _build_route_result(best_order, locations, cache, transport_mode)

    def greedy_from_start(start_index: int) -> Tuple[Tuple[int, ...], Tuple[int, int]]:
        visited = {start_index}
        order = [start_index]
        total_distance = 0
        total_duration = 0
        current_index = start_index

        while len(visited) < len(locations):
            candidate_index = None
            candidate_score = None
            for index in range(len(locations)):
                if index in visited:
                    continue
                segment = cache[(current_index, index)]
                score = (segment["distance"], segment["duration"])
                if candidate_score is None or score < candidate_score:
                    candidate_score = score
                    candidate_index = index
            if candidate_index is None:
                break
            visited.add(candidate_index)
            order.append(candidate_index)
            segment = cache[(current_index, candidate_index)]
            total_distance += segment["distance"]
            total_duration += segment["duration"]
            current_index = candidate_index

        return tuple(order), (total_distance, total_duration)

    if start_fixed and end_fixed:
        visited = {0, fixed_end_index}
        order = [0]
        total_distance = 0
        total_duration = 0
        current_index = 0

        while len(visited) < len(locations) - 1:
            candidate_index = None
            candidate_score = None
            for index in range(1, len(locations)):
                if index in visited or index == fixed_end_index:
                    continue
                segment = cache[(current_index, index)]
                score = (segment["distance"], segment["duration"])
                if candidate_score is None or score < candidate_score:
                    candidate_score = score
                    candidate_index = index
            if candidate_index is None:
                break
            visited.add(candidate_index)
            order.append(candidate_index)
            segment = cache[(current_index, candidate_index)]
            total_distance += segment["distance"]
            total_duration += segment["duration"]
            current_index = candidate_index

        order.append(fixed_end_index)
        segment = cache[(current_index, fixed_end_index)]
        total_distance += segment["distance"]
        total_duration += segment["duration"]
        return _build_route_result(tuple(order), locations, cache, transport_mode)

    if start_fixed:
        order, _ = greedy_from_start(0)
        return _build_route_result(order, locations, cache, transport_mode)

    if end_fixed:
        best_order = None
        best_score = None
        for perm in itertools.permutations(range(len(locations) - 1)):
            order = perm + (fixed_end_index,)
            score = _evaluate_order(order, locations, cache)
            if best_score is None or score < best_score:
                best_order = order
                best_score = score
        return _build_route_result(best_order or tuple(range(len(locations))), locations, cache, transport_mode)

    best_order = None
    best_score = None
    for start_index in range(len(locations)):
        order, score = greedy_from_start(start_index)
        if best_score is None or score < best_score:
            best_order = order
            best_score = score

    return _build_route_result(best_order or tuple(range(len(locations))), locations, cache, transport_mode)


def plan_route_core(
    destinations: List[str | Dict[str, Any]],
    start_point: str | Dict[str, Any] = "",
    end_point: str | Dict[str, Any] = "",
    transport_mode: str = "driving",
) -> Dict[str, Any]:
    amap_key = get_amap_key()
    if not amap_key:
        raise ValueError("未配置高德地图API Key")

    if len(destinations) < 2:
        raise ValueError("至少需要2个目的地才能规划路径")

    locations: List[Dict[str, Any]] = []

    if start_point:
        start_location = _parse_point_value(start_point)
        start_location["kind"] = "start"
        locations.append(start_location)

    for point in destinations:
        destination_location = _parse_point_value(point)
        destination_location["kind"] = "destination"
        locations.append(destination_location)

    fixed_end_index = None
    if end_point:
        end_location = _parse_point_value(end_point)
        end_location["kind"] = "end"
        locations.append(end_location)
        fixed_end_index = len(locations) - 1

    result = optimize_route(locations, transport_mode=transport_mode, fixed_end_index=fixed_end_index)
    result["start_point"] = locations[0]["name"] if start_point else ""
    result["end_point"] = locations[-1]["name"] if end_point else ""
    return result


def get_route_distance_core(origin: str, destination: str, transport_mode: str = "driving") -> Dict[str, Any]:
    amap_key = get_amap_key()
    if not amap_key:
        raise ValueError("未配置高德地图API Key")

    origin_location = _parse_point_value(origin)
    destination_location = _parse_point_value(destination)
    route_mode = _normalize_mode(transport_mode)
    segment = _direction_segment(origin_location, destination_location, route_mode)

    return {
        "from": origin_location["name"],
        "to": destination_location["name"],
        "distance": segment["distance"],
        "duration": segment["duration"],
        "distance_km": segment["distance_km"],
        "duration_minutes": segment["duration_minutes"],
        "transport_mode": route_mode,
        "transport_mode_label": MODE_LABELS.get(route_mode, "驾车"),
    }


@tool(description="路径规划工具，根据多个地点之间的交通方式规划最佳路线")
def plan_route(destinations: List[str], start_point: str = "", transport_mode: str = "driving") -> str:
    """
    规划多个地点之间的最佳路线。
    """
    try:
        result = plan_route_core(destinations, start_point, transport_mode)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"路径规划失败：{str(e)}"


@tool(description="获取两点之间的路程和时间工具，根据交通方式计算两点之间的距离和预计时间")
def get_route_distance(origin: str, destination: str, transport_mode: str = "driving") -> str:
    """
    获取两点之间的路程和时间。
    """
    try:
        result = get_route_distance_core(origin, destination, transport_mode)
        return (
            f"从{result['from']}到{result['to']}：\n"
            f"- 距离：{result['distance']}米（约{result['distance_km']}公里）\n"
            f"- 预计时间：{result['duration']}秒（约{result['duration_minutes']}分钟）\n"
            f"- 交通方式：{result['transport_mode_label']}"
        )
    except Exception as e:
        return f"获取路线失败：{str(e)}"
