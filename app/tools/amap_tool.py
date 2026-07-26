from dataclasses import dataclass
from math import sqrt


@dataclass
class AMapRouteTool:
    """本地路线工具；无外网时也能回退生成距离/耗时。"""

    def calculate(self, start: tuple[float, float], end: tuple[float, float], mode: str = 'driving') -> dict:
        lng1, lat1 = start
        lng2, lat2 = end
        distance_km = round(sqrt((lng1 - lng2) ** 2 + (lat1 - lat2) ** 2) * 111, 2)
        speed = {'walking': 5, 'transit': 18, 'driving': 35}.get(mode, 30)
        duration_min = max(5, int(distance_km / speed * 60))
        return {'mode': mode, 'distance_km': distance_km, 'duration_min': duration_min, 'note': '本地估算'}
