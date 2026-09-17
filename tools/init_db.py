"""航班班次数据集（travel_new.sqlite）维护。

三件事：
1. `sync_flight_dates()`：把班次日期整体平移到「当前 / 近期」——保持相对间隔不变，
   让最新班次落在「今天 + _HORIZON_DAYS 天」，并据此重算状态
   （已取消保留 Cancelled；已过去 3 小时以上记为 Arrived；其余 Scheduled）。
2. `ensure_domestic_flights()`：补齐国内主流航线班次（幂等，逐个航班检查，缺才补）。
   投放日期为「今天起连续 _SEED_DAYS 天」，因此国内航线始终有近期班次可查。
3. `sync_flight_dataset()`：启动时调用 1 + 2（顺序不可颠倒，见下）。

顺序说明：必须先平移、后补齐。若先补齐，新补的班次会成为数据集里的最新班次，
紧接着的平移会把它们一起推到地平线附近；先平移则新补班次停留在「今天 ~ 今天+6」，
而每天启动的平移（+1 天）会让它们始终保持在近期窗口内。

所有时间统一按北京时间（+08:00）存储，保证字符串排序与范围比较可用。
可用 FLIGHT_DATA_SYNC=0 关闭启动同步；pytest 下自动跳过，避免污染测试数据。
"""
from __future__ import annotations

import logging
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from tools import backup_file, db as _DB_PATH, local_file

logger = logging.getLogger(__name__)

_TZ = timezone(timedelta(hours=8))  # 北京时间
_TS_SUFFIX = "+08:00"
_HORIZON_DAYS = 30   # 最新班次落在「今天 + 30 天」
_SEED_DAYS = 7       # 国内班次连续投放的天数
_SEED_FLIGHTS_PER_DIRECTION = 3

_ENABLED = os.getenv("FLIGHT_DATA_SYNC", "1").strip().lower() not in (
    "0",
    "false",
    "no",
    "off",
)

# --------------------------------------------------------------------------- #
# 机场数据（补齐国内机场，city 必须是中文城市经 transform_location 得到的英文名，
# 因为 tools.flights_tools._resolve_airport_codes 用它做 LOWER(city) LIKE 匹配）
# --------------------------------------------------------------------------- #
_AIRPORTS: List[Tuple[str, str, str, str]] = [
    ("PEK", "Beijing Capital International Airport", "Beijing", "[40.0799, 116.6031]"),
    ("PKX", "Beijing Daxing International Airport", "Beijing", "[39.5098, 116.4105]"),
    ("SHA", "Shanghai Hongqiao International Airport", "Shanghai", "[31.1979, 121.3354]"),
    ("PVG", "Shanghai Pudong International Airport", "Shanghai", "[31.1443, 121.8083]"),
    ("CAN", "Guangzhou Baiyun International Airport", "Guangzhou", "[23.3959, 113.308]"),
    ("SZX", "Shenzhen Baoan International Airport", "Shenzhen", "[22.6393, 113.8107]"),
    ("CTU", "Chengdu Shuangliu International Airport", "Chengdu", "[30.5785, 103.9471]"),
    ("TFU", "Chengdu Tianfu International Airport", "Chengdu", "[30.3125, 104.4415]"),
    ("HGH", "Hangzhou Xiaoshan International Airport", "Hangzhou", "[30.2295, 120.4344]"),
    ("CKG", "Chongqing Jiangbei International Airport", "Chongqing", "[29.7192, 106.6417]"),
    ("XIY", "Xian Xianyang International Airport", "Xian", "[34.4471, 108.7516]"),
    ("WUH", "Wuhan Tianhe International Airport", "Wuhan", "[30.7838, 114.2081]"),
    ("NKG", "Nanjing Lukou International Airport", "Nanjing", "[31.742, 118.8622]"),
    ("KMG", "Kunming Changshui International Airport", "Kunming", "[25.1019, 102.9292]"),
    ("TSN", "Tianjin Binhai International Airport", "Tianjin", "[39.1244, 117.3462]"),
    ("TAO", "Qingdao Jiaodong International Airport", "Qingdao", "[36.3661, 120.0889]"),
    ("XMN", "Xiamen Gaoqi International Airport", "Xiamen", "[24.544, 118.1277]"),
    ("CSX", "Changsha Huanghua International Airport", "Changsha", "[28.1892, 113.2196]"),
    ("DLC", "Dalian Zhoushuizi International Airport", "Dalian", "[38.9657, 121.5386]"),
    ("SYX", "Sanya Phoenix International Airport", "Sanya", "[18.3029, 109.4123]"),
    ("SHE", "Shenyang Taoxian International Airport", "Shenyang", "[41.6398, 123.4833]"),
    ("TNA", "Jinan Yaoqiang International Airport", "Jinan", "[36.8572, 117.216]"),
    ("CGO", "Zhengzhou Xinzheng International Airport", "Zhengzhou", "[34.5197, 113.8408]"),
    ("FOC", "Fuzhou Changle International Airport", "Fuzhou", "[25.9351, 119.6633]"),
    ("KHN", "Nanchang Changbei International Airport", "Nanchang", "[28.865, 115.9]"),
    ("HFE", "Hefei Xinqiao International Airport", "Hefei", "[31.78, 116.9767]"),
    ("NGB", "Ningbo Lishe International Airport", "Ningbo", "[29.8267, 121.4619]"),
    ("HRB", "Harbin Taiping International Airport", "Harbin", "[45.6234, 126.25]"),
    ("WUX", "Wuxi Shuofang Airport", "Wuxi", "[31.4944, 120.4292]"),
    ("ZUH", "Zhuhai Jinwan Airport", "Zhuhai", "[22.0064, 113.376]"),
    ("HAK", "Haikou Meilan International Airport", "Haikou", "[19.9349, 110.4589]"),
    ("KWE", "Guiyang Longdongbao International Airport", "Guiyang", "[26.5385, 106.8008]"),
    ("NNG", "Nanning Wuxu International Airport", "Nanning", "[22.6083, 108.1722]"),
    ("LHW", "Lanzhou Zhongchuan International Airport", "Lanzhou", "[36.5152, 103.6205]"),
    ("XNN", "Xining Caojiabao International Airport", "Xining", "[36.5275, 102.0431]"),
    ("INC", "Yinchuan Hedong International Airport", "Yinchuan", "[38.3215, 106.3931]"),
    ("HET", "Hohhot Baita International Airport", "Hohhot", "[40.8514, 111.8241]"),
    ("SJW", "Shijiazhuang Zhengding International Airport", "Shijiazhuang", "[38.2807, 114.6964]"),
    ("TYN", "Taiyuan Wusu International Airport", "Taiyuan", "[37.7469, 112.6284]"),
    ("CGQ", "Changchun Longjia International Airport", "Changchun", "[43.9962, 125.6846]"),
    ("WNZ", "Wenzhou Longwan International Airport", "Wenzhou", "[27.9122, 120.8522]"),
    ("YNT", "Yantai Penglai International Airport", "Yantai", "[37.6572, 120.9783]"),
    ("LYA", "Luoyang Beijiao Airport", "Luoyang", "[34.7411, 112.3881]"),
    ("JJN", "Quanzhou Jinjiang International Airport", "Quanzhou", "[24.7961, 118.59]"),
    ("HKG", "Hong Kong International Airport", "Hong Kong", "[22.3089, 113.9146]"),
    ("MFM", "Macau International Airport", "Macau", "[22.1496, 113.5915]"),
    ("TPE", "Taiwan Taoyuan International Airport", "Taipei", "[25.0777, 121.2328]"),
]

# --------------------------------------------------------------------------- #
# 国内航线（出发, 到达, 飞行时长分钟）；双向各投放 _SEED_FLIGHTS_PER_DIRECTION 个班次
# --------------------------------------------------------------------------- #
_PAIRS: List[Tuple[str, str, int]] = [
    ("PEK", "SHA", 135), ("PEK", "CAN", 195), ("PEK", "SZX", 200), ("PEK", "CTU", 175),
    ("PEK", "HGH", 140), ("PEK", "CKG", 165), ("PEK", "XIY", 125), ("PEK", "WUH", 130),
    ("PEK", "NKG", 125), ("PEK", "XMN", 170), ("PEK", "SYX", 245), ("PEK", "KMG", 210),
    ("PEK", "TAO", 90), ("PEK", "CSX", 155), ("PEK", "DLC", 85), ("PEK", "HRB", 120),
    ("PEK", "FOC", 165), ("PEK", "NGB", 140), ("PEK", "CGO", 110), ("PEK", "HKG", 200),
    ("SHA", "CAN", 145), ("SHA", "SZX", 150), ("SHA", "CTU", 165), ("SHA", "CKG", 150),
    ("SHA", "XIY", 140), ("SHA", "XMN", 105), ("SHA", "SYX", 180), ("SHA", "KMG", 200),
    ("SHA", "WUH", 110), ("SHA", "TAO", 95), ("SHA", "DLC", 110), ("SHA", "CSX", 115),
    ("SHA", "HKG", 165), ("SHA", "TPE", 120), ("SHA", "NGB", 55), ("SHA", "WNZ", 70),
    ("CAN", "CTU", 150), ("CAN", "HGH", 130), ("CAN", "XIY", 155), ("CAN", "XMN", 80),
    ("CAN", "CKG", 130), ("CAN", "KMG", 145), ("CAN", "HKG", 65), ("CAN", "HAK", 80),
    ("SZX", "CTU", 155), ("SZX", "HGH", 135), ("SZX", "XIY", 175), ("SZX", "CKG", 145),
    ("SZX", "NKG", 130), ("CTU", "XIY", 95), ("CTU", "KMG", 90), ("CTU", "HGH", 155),
    ("CTU", "CKG", 70), ("CTU", "KWE", 80), ("HGH", "XMN", 95), ("HGH", "CKG", 150),
    ("HGH", "XIY", 145), ("NKG", "XMN", 105), ("TSN", "CAN", 200), ("TSN", "SHA", 130),
    ("WUH", "CAN", 110), ("WUH", "CTU", 110), ("XIY", "KMG", 145), ("CKG", "KMG", 95),
]

_CARRIERS = ("CA", "MU", "CZ", "HU", "3U", "MF", "SC", "ZH", "GS", "KN")
_SLOTS = ("07:30", "10:20", "13:10", "15:40", "19:20", "21:30")
_AIRCRAFT = ("320", "738", "333", "321", "77W", "359", "787", "319")
_FLIGHT_NO_BASE = 5000


# --------------------------------------------------------------------------- #
# 时间工具
# --------------------------------------------------------------------------- #
def _parse_dt(value) -> Optional[datetime]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text == "\\N":
        return None
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        dt = None
        for fmt in ("%Y-%m-%d %H:%M:%S.%f%z", "%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        if dt is None:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_TZ)
    return dt


def _fmt_dt(dt: datetime) -> str:
    """统一输出为北京时间字符串，保持与库中既有格式一致（便于字符串排序）。"""
    return dt.astimezone(_TZ).strftime("%Y-%m-%d %H:%M:%S.%f") + _TS_SUFFIX


def _recompute_status(raw_status: str, dep: Optional[datetime], now: datetime) -> str:
    text = (raw_status or "").strip()
    if text.lower().startswith("cancel"):
        return "Cancelled"
    if dep is None:
        return text or "Scheduled"
    return "Arrived" if dep < now - timedelta(hours=3) else "Scheduled"


# --------------------------------------------------------------------------- #
# 1) 日期平移
# --------------------------------------------------------------------------- #
def sync_flight_dates() -> int:
    """整体平移班次日期，使最新班次落在「今天 + _HORIZON_DAYS 天」；返回更新行数。

    位移不足 1 小时（同一天重复启动）时直接跳过，避免每次启动都全表重写。
    """
    conn = sqlite3.connect(_DB_PATH)
    try:
        cursor = conn.cursor()
        rows = cursor.execute(
            "SELECT flight_id, scheduled_departure, scheduled_arrival, "
            "actual_departure, actual_arrival, status FROM flights"
        ).fetchall()
        if not rows:
            return 0

        parsed = [(row[0], _parse_dt(row[1])) for row in rows]
        max_dep = max((dep for _, dep in parsed if dep is not None), default=None)
        if max_dep is None:
            return 0

        target = (datetime.now(_TZ) + timedelta(days=_HORIZON_DAYS)).replace(
            hour=23, minute=59, second=0, microsecond=0
        )
        offset = target - max_dep
        if abs(offset) < timedelta(hours=1):
            return 0

        now = datetime.now(_TZ)
        updates = []
        for flight_id, dep_raw, arr_raw, act_dep_raw, act_arr_raw, status in rows:
            dep = _parse_dt(dep_raw)
            arr = _parse_dt(arr_raw)
            act_dep = _parse_dt(act_dep_raw)
            act_arr = _parse_dt(act_arr_raw)
            new_dep = dep + offset if dep else None
            updates.append(
                (
                    _fmt_dt(new_dep) if new_dep else dep_raw,
                    _fmt_dt(arr + offset) if arr else arr_raw,
                    _fmt_dt(act_dep + offset) if act_dep else act_dep_raw,
                    _fmt_dt(act_arr + offset) if act_arr else act_arr_raw,
                    _recompute_status(status, new_dep, now),
                    flight_id,
                )
            )
        cursor.executemany(
            "UPDATE flights SET scheduled_departure = ?, scheduled_arrival = ?, "
            "actual_departure = ?, actual_arrival = ?, status = ? WHERE flight_id = ?",
            updates,
        )
        conn.commit()
        logger.info("航班班次日期已平移：offset=%s，共 %d 条", offset, len(updates))
        return len(updates)
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# 2) 补齐国内航线
# --------------------------------------------------------------------------- #
def _ensure_airports(cursor: sqlite3.Cursor) -> None:
    for code, name, city, coords in _AIRPORTS:
        cursor.execute(
            "INSERT INTO airports_data (airport_code, airport_name, city, coordinates, timezone) "
            "SELECT ?, ?, ?, ?, ? WHERE NOT EXISTS "
            "(SELECT 1 FROM airports_data WHERE airport_code = ?)",
            (code, name, city, coords, "Asia/Shanghai", code),
        )


def ensure_domestic_flights() -> int:
    """补齐国内主流航线班次（幂等：按 航班号+出发+到达 判断是否已存在）；返回新增行数。"""
    conn = sqlite3.connect(_DB_PATH)
    try:
        cursor = conn.cursor()
        _ensure_airports(cursor)

        base = datetime.now(_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
        now = datetime.now(_TZ)
        next_id = (cursor.execute("SELECT MAX(flight_id) FROM flights").fetchone()[0] or 0) + 1
        inserted = 0

        for pair_index, (dep_code, arr_code, duration) in enumerate(_PAIRS):
            for direction in (0, 1):
                from_code, to_code = (
                    (dep_code, arr_code) if direction == 0 else (arr_code, dep_code)
                )
                for slot_index in range(_SEED_FLIGHTS_PER_DIRECTION):
                    carrier = _CARRIERS[
                        (pair_index + direction + slot_index) % len(_CARRIERS)
                    ]
                    number = (
                        _FLIGHT_NO_BASE + pair_index * 6 + direction * 3 + slot_index + 1
                    )
                    flight_no = f"{carrier}{number}"
                    if cursor.execute(
                        "SELECT 1 FROM flights WHERE flight_no = ? AND "
                        "departure_airport = ? AND arrival_airport = ? LIMIT 1",
                        (flight_no, from_code, to_code),
                    ).fetchone():
                        continue

                    slot = _SLOTS[(slot_index * 2 + direction) % len(_SLOTS)]
                    hour, minute = (int(part) for part in slot.split(":"))
                    aircraft = _AIRCRAFT[
                        (pair_index + slot_index + direction) % len(_AIRCRAFT)
                    ]
                    for day in range(_SEED_DAYS):
                        dep_dt = base + timedelta(days=day, hours=hour, minutes=minute)
                        arr_dt = dep_dt + timedelta(minutes=duration)
                        status = "Scheduled" if dep_dt >= now else "Arrived"
                        cursor.execute(
                            "INSERT INTO flights (flight_id, flight_no, scheduled_departure, "
                            "scheduled_arrival, departure_airport, arrival_airport, status, "
                            "aircraft_code, actual_departure, actual_arrival) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (
                                next_id, flight_no, _fmt_dt(dep_dt), _fmt_dt(arr_dt),
                                from_code, to_code, status, aircraft, None, None,
                            ),
                        )
                        next_id += 1
                        inserted += 1

        conn.commit()
        if inserted:
            logger.info("已补充国内航线班次 %d 条", inserted)
        return inserted
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# 3) 启动同步 / 重置
# --------------------------------------------------------------------------- #
def _skip_in_tests() -> bool:
    return "pytest" in sys.modules or bool(os.environ.get("PYTEST_CURRENT_TEST"))


def sync_flight_dataset() -> None:
    """启动时调用：先平移日期、再补齐国内航线（顺序不可颠倒，见模块说明）。

    任何失败都只记日志，不影响服务启动。
    """
    if not _ENABLED or _skip_in_tests():
        return
    try:
        sync_flight_dates()
        ensure_domestic_flights()
    except Exception:  # noqa: BLE001
        logger.exception("航班数据集同步失败（不影响服务启动）")


def reset_from_backup() -> str:
    """用 travel2.sqlite 备份整体重置班次库（调试 / 测试用），返回库文件路径。"""
    shutil.copy(backup_file, local_file)
    logger.info("航班班次库已从备份重置：%s", local_file)
    return local_file


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sync_flight_dataset()
