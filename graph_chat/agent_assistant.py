from datetime import datetime

from langchain_core.prompts import ChatPromptTemplate

from graph_chat.base_data_model import CompleteOrEscalate
from graph_chat.llm_config import llm
from tools.amap_tools import amap_search_poi, amap_search_around, amap_geocode
from tools.flights_tools import search_flights, update_ticket_to_new_flight, cancel_ticket
from tools.hotels_tools import book_hotel, update_hotel, cancel_hotel
from tools.wishlist_tools import add_to_wishlist, remove_from_wishlist, list_wishlist

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

# 旅行清单助手（只管「加入 / 移出 / 查看」自己的旅行清单，不再做景点推荐）
travel_list_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "您是专门负责「旅行清单」的助理，帮用户管理自己的旅行清单（想去的地方）。"
            "当用户想查看自己的旅行清单，或想把某个地点加入 / 移出清单时，主助理会将工作委托给您。"
            "把地点加入清单用 add_to_wishlist（传名称，若有城市 / 地址一并传入）；"
            "把地点移出清单用 remove_from_wishlist（传名称即可）；查看当前清单用 list_wishlist。"
            "这些都是低风险操作，直接执行，无需用户二次确认。"
            "注意：本助手不提供「景点推荐」，也不要凭自身知识编造景点或来源；"
            "若用户是想找景点、要推荐，请 CompleteOrEscalate 回主助手处理。"
            "\n当前时间: {time}."
            "\n\n如果用户需要帮助，并且您的工具都不适用，则"
            '“CompleteOrEscalate”对话给主助理。不要浪费用户的时间。不要编造无效的工具或功能。'
            "\n\n以下是一些你应该CompleteOrEscalate的例子：\n"
            " - '帮我推荐几个成都的景点'\n"
            " - '我想看看有哪些好玩的地方'\n"
            " - '我需要先订个航班再考虑景点'",
        ),
        ("placeholder", "{messages}"),
    ]
).partial(time=datetime.now())

# 旅行清单助手的工具集（均为低风险操作，无需人工审批）
travel_list_tools = [
    add_to_wishlist,
    remove_from_wishlist,
    list_wishlist,
]

# 创建可运行对象，绑定旅行清单提示模板和工具集，包括CompleteOrEscalate工具
travel_list_runnable = travel_list_prompt | llm.bind_tools(
    travel_list_tools + [CompleteOrEscalate]
)
