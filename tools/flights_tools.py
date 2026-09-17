"""航班班次查询工具（demo 班次库 travel_new.sqlite 的 flights 表）。

说明：这里的 search_flights 查的是「任意城市之间的航班班次」（覆盖从哪到哪、几点起飞）。
「我的航班 / 我的预订」属于个人订单，存于应用自身的库（flight_bookings 表），
对应工具见 tools/flight_bookings_tools.py；两者数据源完全分离。
"""
from sqlite3 import connect
from datetime import date, datetime
from typing import Optional, List, Dict
import re

from langchain_core.tools import tool

from tools import db
from tools.location_trans import transform_location


def _is_chinese_city(name: str) -> bool:
    """判断字符串是否包含中文（很可能是城市名而非机场代码）。"""
    if not name:
        return False
    return bool(re.search(r'[\u4e00-\u9fff]', name))


def _resolve_airport_codes(city_name: str) -> List[str]:
    """
    将中文城市名转换为对应的机场代码列表。
    步骤：
    1. 将中文城市名翻译为英文（如"北京"→"Beijing"）
    2. 在 airports_data 表中模糊匹配 city 字段
    3. 返回所有匹配的 airport_code
    """
    if not city_name:
        return []

    conn = connect(db)
    cursor = conn.cursor()

    codes: List[str] = []

    try:
        # 先尝试用英文名直接匹配（如果是英文输入）
        cursor.execute(
            "SELECT DISTINCT airport_code FROM airports_data WHERE LOWER(city) LIKE ?",
            (f"%{city_name.lower()}%",)
        )
        rows = cursor.fetchall()
        if rows:
            codes = [r[0] for r in rows]
        else:
            # 中文城市名 → 英文 → 再查
            english_city = transform_location(city_name)
            if english_city and english_city != city_name:
                cursor.execute(
                    "SELECT DISTINCT airport_code FROM airports_data WHERE LOWER(city) LIKE ?",
                    (f"%{english_city.lower()}%",)
                )
                rows = cursor.fetchall()
                codes = [r[0] for r in rows]

        # 如果还是找不到，尝试直接用中文模糊匹配 city 字段
        if not codes and _is_chinese_city(city_name):
            cursor.execute(
                "SELECT DISTINCT airport_code FROM airports_data WHERE city LIKE ?",
                (f"%{city_name}%",)
            )
            rows = cursor.fetchall()
            codes = [r[0] for r in rows]
    except Exception:
        pass
    finally:
        cursor.close()
        conn.close()

    return codes


@tool
def search_flights(
        departure_airport: Optional[str] = None,
        arrival_airport: Optional[str] = None,
        start_time: Optional[date | datetime] = None,
        end_time: Optional[date | datetime] = None,
        limit: int = 20,
) -> List[Dict]:
    """
    根据指定的参数搜索航班，并返回匹配的航班列表。支持中文城市名（如"北京"、"上海"）和英文机场代码（如"PEK"、"SHA"）。
    可以设置一个限制值来控制返回的结果数量。

    参数:
    - departure_airport (Optional[str]): 出发城市或机场。支持中文城市名（"北京"、"上海"）或英文机场代码（"PEK"、"PVG"）（可选）。
    - arrival_airport (Optional[str]): 到达城市或机场。支持中文城市名（"北京"、"上海"）或英文机场代码（"PEK"、"PVG"）（可选）。
    - start_time (Optional[date | datetime]): 出发时间范围的开始时间（可选）。
    - end_time (Optional[date | datetime]): 出发时间范围的结束时间（可选）。
    - limit (int): 返回结果的最大数量，默认为20。

    返回:
        匹配条件的航班信息列表。
    """
    def _get_codes(raw: str) -> List[str]:
        """如果输入是中文城市名则转换为机场代码列表，否则直接用原始值。"""
        if not raw:
            return []
        if _is_chinese_city(raw):
            codes = _resolve_airport_codes(raw)
            if codes:
                return codes
        return [raw]

    dep_codes = _get_codes(departure_airport) if departure_airport else []
    arr_codes = _get_codes(arrival_airport) if arrival_airport else []

    conn = connect(db)
    cursor = conn.cursor()

    query = "SELECT * FROM flights WHERE 1 = 1"
    params = []

    if dep_codes:
        placeholders = ",".join("?" for _ in dep_codes)
        query += f" AND departure_airport IN ({placeholders})"
        params.extend(dep_codes)

    if arr_codes:
        placeholders = ",".join("?" for _ in arr_codes)
        query += f" AND arrival_airport IN ({placeholders})"
        params.extend(arr_codes)

    if start_time:
        query += " AND scheduled_departure >= ?"
        params.append(start_time)

    if end_time:
        query += " AND scheduled_departure <= ?"
        params.append(end_time)

    # 按计划起飞时间倒序：本地数据集多为历史班次，倒序可取到最接近当前时间的班次
    query += " ORDER BY scheduled_departure DESC LIMIT ?"
    params.append(limit)
    cursor.execute(query, params)
    rows = cursor.fetchall()
    column_names = [column[0] for column in cursor.description]
    results = [dict(zip(column_names, row)) for row in rows]

    cursor.close()
    conn.close()

    return results
