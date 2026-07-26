"""地图相关接口：地理编码、POI 搜索、周边搜索、路径规划与距离估算。

后端通过高德 Web 服务 Key（AMAP_WEB_KEY）调用高德开放平台接口。
本路由被 `app/api/router.py` 以无前缀方式注册（tags=['maps']），因此路径均以此文件内定义的 `/maps/...` 为准。
"""
from __future__ import annotations

import ast
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from tools.amap_tools import (
    amap_geocode,
    amap_search_around,
    amap_search_poi_raw,
    amap_geocode_raw,
    amap_reverse_geocode,
    amap_inputtips,
    amap_search_around_raw,
)
from tools.route_planner import get_route_distance_core, plan_route_core

router = APIRouter()


def _parse_str_dict(text: str) -> object:
    """工具函数常返回 Python 字典字符串或错误文本，这里尽量还原为可序列化结构。"""
    if not isinstance(text, str):
        return text
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return {"message": text}


@router.get('/maps/geocode')
def geocode(address: str = Query(..., description='待地理编码的地址文本')):
    """地址 -> 经纬度等位置信息。"""
    return _parse_str_dict(amap_geocode(address))


@router.get('/maps/poi')
def search_poi(
    keywords: str = Query(..., description='POI 关键词，如「酒店」「景点」'),
    city: str = Query(None, description='城市名或城市编码'),
    types: str = Query(None, description='POI 分类编码'),
    page_size: int = Query(10, ge=1, le=25),
):
    """关键词 POI 搜索，返回高德原始结构化结果。"""
    return amap_search_poi_raw(keywords, city=city, types=types, page_size=page_size)


@router.get('/maps/around')
def search_around(
    location: str = Query(..., description='中心点经纬度，格式 "lng,lat"'),
    keywords: str = Query('', description='周边搜索关键词'),
    radius: int = Query(1000, ge=1, le=50000, description='搜索半径（米）'),
    types: str = Query('', description='POI 分类编码'),
):
    """按中心点坐标搜索周边 POI。"""
    return _parse_str_dict(amap_search_around(location, keywords=keywords, radius=radius, types=types))


class RouteRequest(BaseModel):
    destinations: list[str]
    start_point: str = ''
    end_point: str = ''
    transport_mode: str = 'driving'


@router.post('/maps/route')
def plan_route_api(req: RouteRequest):
    """多目的地路径规划（默认驾车，可传 walking / bicycling / transit）。"""
    try:
        return plan_route_core(req.destinations, req.start_point, req.end_point, req.transport_mode)
    except Exception as exc:  # 工具层可能抛出“至少 2 个目的地”等校验错误
        raise HTTPException(status_code=400, detail=str(exc))


@router.get('/maps/distance')
def route_distance(
    origin: str = Query(..., description='起点，地址文本或 "lng,lat"'),
    destination: str = Query(..., description='终点，地址文本或 "lng,lat"'),
    transport_mode: str = Query('driving', description='交通方式'),
):
    """两点间距离与预计耗时。"""
    try:
        return get_route_distance_core(origin, destination, transport_mode)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# --------------------------------------------------------------------------- #
# 以下路由对齐前端 RoutePlanner.vue 实际调用的接口路径（POST /api/...）。
# 注意：api_router 在 main.py 中以 /api 前缀挂载，故此处路径不含 /api 前缀。
# --------------------------------------------------------------------------- #
class GeocodeRequest(BaseModel):
    address: str
    city: str = ""


@router.post('/geocode/')
def geocode_api(req: GeocodeRequest):
    """地址 -> 经纬度；前端搜索目的地“手动添加”使用。"""
    return amap_geocode_raw(req.address, city=req.city)


class ReverseGeocodeRequest(BaseModel):
    lng: float
    lat: float


@router.post('/reverse-geocode/')
def reverse_geocode_api(req: ReverseGeocodeRequest):
    """经纬度 -> 地址；前端地图点击落点、定位当前位置使用。"""
    return amap_reverse_geocode(req.lng, req.lat)


class InputTipsRequest(BaseModel):
    keywords: str
    city: str = ""


@router.post('/inputtips/')
def inputtips_api(req: InputTipsRequest):
    """输入提示（智能匹配推荐）；前端起点/终点/搜索目的地搜索框使用。"""
    return amap_inputtips(req.keywords, city=req.city)


class NearbyPoiRequest(BaseModel):
    location: str
    radius: int = 1000
    types: str = ""
    limit: int = 5


@router.post('/nearby-poi/')
def nearby_poi_api(req: NearbyPoiRequest):
    """周边搜索；前端地图点击落点推荐附近去处使用。"""
    return amap_search_around_raw(req.location, radius=req.radius, types=req.types, limit=req.limit)


class PlanRouteFrontendRequest(BaseModel):
    destinations: List[Dict[str, Any]]
    start_point: Any = None
    end_point: Any = None
    transport_mode: str = "driving"


@router.post('/plan-route/')
def plan_route_frontend_api(req: PlanRouteFrontendRequest):
    """多目的地路线规划（前端“规划路线”按钮）；对齐前端 plan-route 期望返回结构。"""
    try:
        return plan_route_core(req.destinations, req.start_point or "", req.end_point or "", req.transport_mode)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
