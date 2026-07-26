# 得到项目所在绝对路径
from pathlib import Path

basic_dir = Path(__file__).resolve().parent.parent

db = f"{basic_dir}/travel_new.sqlite"  # 这是数据库文件名

# 这个数据库才是，项目测试过程中使用的
local_file = f"{basic_dir}/travel_new.sqlite"

# 创建一个备份文件，允许我们在测试的时候可以重新开始
backup_file = f"{basic_dir}/travel2.sqlite"

# 导出高德地图工具
from tools.amap_tools import (
    amap_search_poi,
    amap_geocode
)

# 导出天气工具（高德天气）
from tools.weather_tools import (
    amap_get_weather,
    amap_get_forecast
)

# 导出路径规划工具
from tools.route_planner import (
    plan_route,
    get_route_distance
)
