from datetime import datetime

from langchain_core.prompts import ChatPromptTemplate

from graph_chat.base_data_model import CompleteOrEscalate
from graph_chat.llm_config import llm
from tools.amap_tools import amap_search_poi, amap_search_around, amap_geocode
from tools.flights_tools import search_flights, update_ticket_to_new_flight, cancel_ticket
from tools.hotels_tools import book_hotel, update_hotel, cancel_hotel
from tools.trip_tools import search_trip_recommendations, book_excursion, update_excursion, cancel_excursion
from tools.weather_tools import amap_get_weather

# 航班预订助手
flight_booking_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "您是专门处理航班查询，改签和预定的助理。"
            "当用户需要帮助更新他们的预订时，主助理会将工作委托给您。"
            "请与客户确认更新后的航班详情，并告知他们任何额外费用。"
            "在搜索时，请坚持不懈，但最多尝试 2 次搜索。"
            "若 2 次后仍无匹配航班，请直接告知用户没有符合要求的航班，并 CompleteOrEscalate 回主助手。"
            "如果您需要更多信息或客户改变主意，请将任务升级回主助理。"
            "请记住，在相关工具成功使用后，预订才算完成。"
            "\n\n当前用户的航班信息:\n<Flights>\n{user_info}\n</Flights>"
            "\n当前时间: {time}."
            "\n\n如果用户需要帮助，并且您的工具都不适用，则"
            '“CompleteOrEscalate”对话给主助理。不要浪费用户的时间。不要编造无效的工具或功能。',
        ),
        ("placeholder", "{messages}"),
    ]
).partial(time=datetime.now())

# 定义安全工具（只读操作）和敏感工具（涉及更改的操作）
update_flight_safe_tools = [search_flights]
update_flight_sensitive_tools = [update_ticket_to_new_flight, cancel_ticket]

# 合并所有工具
update_flight_tools = update_flight_safe_tools + update_flight_sensitive_tools

# 创建可运行对象，绑定航班预订提示模板和工具集，包括CompleteOrEscalate工具
update_flight_runnable = flight_booking_prompt | llm.bind_tools(
    update_flight_tools + [CompleteOrEscalate]
)

# 酒店预订助手
book_hotel_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "您是专门处理酒店预订的助理。"
            "当用户需要帮助预订酒店时，主助理会将工作委托给您。"
            "使用高德地图POI搜索工具（amap_search_poi）查询酒店信息。"
            "如果用户提到具体位置，请先用 amap_geocode 获取经纬度，再用 amap_search_poi 或 amap_search_around 搜索。"
            "搜索 1 次即可，如果无匹配结果直接告知用户并 CompleteOrEscalate 回主助手，不要重复搜索。"
            "如果您需要更多信息或客户改变主意，请将任务升级回主助理。"
            "请记住，在相关工具成功使用后，预订才算完成。"
            "\n当前时间: {time}."
            "\n\n如果用户需要帮助，并且您的工具都不适用，则"
            '“CompleteOrEscalate”对话给主助理。不要浪费用户的时间。不要编造无效的工具或功能。'
            ' 注意：酒店搜索结果来自高德地图实时 POI，仅含名称、地址、电话、位置等信息，不含价格与用户评分；'
            '因此不要主动向用户承诺或提供“查看价格”“查看评分”等本系统不具备的功能，若用户问及请如实说明当前数据不含这些信息，并仅提供已有的名称、地址、电话、位置等。'
            "\n\n以下是一些你应该CompleteOrEscalate的例子：\n"
            " - '这个季节的天气怎么样？'\n"
            " - '我再考虑一下，可能单独预订'\n"
            " - '我需要弄清楚我在那里的交通方式'\n"
            " - '哦，等等，我还没预订航班，我会先订航班'\n"
            " - '酒店预订已确认'",
        ),
        ("placeholder", "{messages}"),
    ]
).partial(time=datetime.now())

# 定义安全工具（只读操作）和敏感工具（涉及更改的操作）
book_hotel_safe_tools = [amap_search_poi, amap_search_around, amap_geocode]
book_hotel_sensitive_tools = [book_hotel, update_hotel, cancel_hotel]

# 合并所有工具
book_hotel_tools = book_hotel_safe_tools + book_hotel_sensitive_tools

# 创建可运行对象，绑定酒店预订提示模板和工具集，包括CompleteOrEscalate工具
book_hotel_runnable = book_hotel_prompt | llm.bind_tools(
    book_hotel_tools + [CompleteOrEscalate]
)

# 游览预订助手
book_excursion_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "您是专门处理旅行推荐的助理。"
            "当用户需要帮助预订推荐的旅行时，主助理会将工作委托给您。"
            "根据用户的偏好搜索可用的旅行推荐，并与客户确认预订详情。"
            "您可以使用高德地图工具搜索真实的景点、酒店、餐厅等POI信息，使用天气工具查询目的地天气。"
            "如果用户提到具体位置，先用地理编码获取经纬度，再搜索周边景点。"
            "如果您需要更多信息或客户改变主意，请将任务升级回主助理。"
            "搜索 1 次即可，如果无匹配结果请直接告知用户并 CompleteOrEscalate 回主助手，不要重复搜索。"
            "请记住，在相关工具成功使用后，预订才算完成。"
            "\n当前时间: {time}."
            "\n\n如果用户需要帮助，并且您的工具都不适用，则"
            '“CompleteOrEscalate”对话给主助理。不要浪费用户的时间。不要编造无效的工具或功能。'
            "\n\n以下是一些你应该CompleteOrEscalate的例子：\n"
            " - '我再考虑一下，可能单独预订'\n"
            " - '我需要弄清楚我在那里的交通方式'\n"
            " - '哦，等等，我还没预订航班，我会先订航班'\n"
            " - '游览预订已确认！'",
        ),
        ("placeholder", "{messages}"),
    ]
).partial(time=datetime.now())

# 定义安全工具（只读操作）和敏感工具（涉及更改的操作）
book_excursion_safe_tools = [search_trip_recommendations, amap_search_poi, amap_search_around, amap_geocode, amap_get_weather]
book_excursion_sensitive_tools = [book_excursion, update_excursion, cancel_excursion]

# 合并所有工具
book_excursion_tools = book_excursion_safe_tools + book_excursion_sensitive_tools

# 创建可运行对象，绑定游览预订提示模板和工具集，包括CompleteOrEscalate工具
book_excursion_runnable = book_excursion_prompt | llm.bind_tools(
    book_excursion_tools + [CompleteOrEscalate]
)
