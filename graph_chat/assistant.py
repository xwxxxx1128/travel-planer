import os
from datetime import datetime

from langchain_core.messages import AIMessage, trim_messages
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_openai import ChatOpenAI

from graph_chat.base_data_model import ToFlightBookingAssistant, ToHotelBookingAssistant, \
    ToBookExcursion
from graph_chat.llm_config import llm
from graph_chat.state import State
from tools.amap_tools import amap_search_poi, amap_geocode, amap_search_around
from tools.flights_tools import fetch_user_flight_information, search_flights, update_ticket_to_new_flight, \
    cancel_ticket
from tools.hotels_tools import book_hotel, update_hotel, cancel_hotel
from tools.retriever_vector import lookup_policy
from tools.trip_tools import search_trip_recommendations, book_excursion, update_excursion, cancel_excursion
from tools.weather_tools import amap_get_weather, amap_get_forecast
from tools.route_planner import plan_route, get_route_distance
from tools.reviews_tools import search_reviews


def _count_tokens(messages) -> int:
    """粗略按字符数/4 估算 token，避免依赖具体模型的 tokenizer（网关模型常无对应 tokenizer）。"""
    total = 0
    for m in messages:
        content = getattr(m, "content", "")
        total += len(content) if isinstance(content, str) else len(str(content))
    return total // 4


# 历史裁剪器：只把最近约 4000 token 的对话喂给大模型。
# 这是对标 trip_assistant 中 history[-6:] / msgs[-40:] 的核心优化——
# assistant.py 里 messages 用 add_messages 无限累积，轮次越多每次 LLM 调用越慢（最严重瓶颈）。
# 这里仅裁剪“喂给模型”的上下文，不改动持久化的 state，因此记忆/审批流程不受影响。
# allow_partial=True：确保即便某条消息超预算，也至少保留最新的用户提问，绝不丢当前轮次。
_MESSAGE_TRIMMER = trim_messages(
    max_tokens=4000,
    strategy="last",
    token_counter=_count_tokens,
    include_system=False,
    allow_partial=True,
)


class CtripAssistant:
    # 自定义一个类，表示流程图的一个节点（复杂的）

    def __init__(self, runnable: Runnable):
        """
        初始化助手的实例。
        :param runnable: 可以运行对象，通常是一个Runnable类型的
        """
        self.runnable = runnable

    def __call__(self, state: State, config: RunnableConfig):
        """
        调用节点，执行助手任务
        :param state: 当前工作流的状态
        :param config: 配置: 里面有旅客的信息
        :return:
        """
        # 降低空回复重试次数（原为 2）：每次重试都是一次完整 LLM 往返，
        # 裁剪历史后 1 次重试已足够兜底，可显著压低最坏情况耗时。
        max_retries = 1
        retries = 0
        while True:
            # 关键优化：仅用“裁剪后的最近对话”喂给大模型，避免 messages 用 add_messages
            # 无限累积导致轮次越多每次调用越慢（对标 trip_assistant 的 history[-6:] 思路）。
            # 这里只裁剪“喂给模型”的上下文，不改动持久化的 state，记忆/审批流程不受影响。
            trimmed = _MESSAGE_TRIMMER.invoke(state.get("messages") or [])
            local_state = {**state, "messages": trimmed}
            result = self.runnable.invoke(local_state)
            # 如果，runnable执行完后，没有得到一个实际的输出
            if not result.tool_calls and (  # 如果结果中没有工具调用，并且内容为空或内容列表的第一个元素没有"text"，则需要重新提示用户输入。
                    not result.content
                    or isinstance(result.content, list)
                    and not result.content[0].get("text")
            ):
                retries += 1
                if retries >= max_retries:
                    # 达到最大重试次数，返回提示信息避免死循环
                    result = AIMessage(content="抱歉，我暂时无法生成回复，请稍后再试或换种方式提问。")
                    break
                messages = state["messages"] + [("user", "请提供一个真实的输出作为回应。")]
                # 重试前同样裁剪，避免把已膨胀的历史连带“空洞提示”一起回灌。
                state = {**state, "messages": _MESSAGE_TRIMMER.invoke(messages)}
            else:  # 如果： runnable执行后已经得到，想要的输出，则退出循环
                break
        return {'messages': result}



# 主助理提示模板
primary_assistant_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "您是出行规划智能助手。"
            "您的主要职责是帮助用户规划旅行路线和回答旅行相关的查询。"
            ""
            "## 指令"
            ""
            "### 查询类请求（主助手自行处理，不路由到专门助理）"
            "对于以下场景，您自己直接使用工具完成，不需要委派给专门助理："
            " - 搜索酒店、查找酒店信息 → 使用 amap_search_poi"
            " - 搜索景点、餐厅、POI → 使用 amap_search_poi 或 amap_search_around"
            " - 查询天气 → 使用 amap_get_weather / amap_get_forecast"
            " - 路线规划 → 使用 plan_route / get_route_distance"
            " - 查看航班信息 → 使用 search_flights（直接传中文城市名即可，如「北京」）"
            " - 查看政策 → 使用 lookup_policy"
            " - 查看评价 → 使用 search_reviews"
            ""
            "### 操作类请求（才需要路由到专门助理）"
            "只有在用户明确要求以下操作时，才调用对应的委派工具路由到专门助理："
            " - 改签/取消机票 → ToFlightBookingAssistant"
            " - 预订酒店/修改酒店/取消酒店 → ToHotelBookingAssistant"
            " - 预订游览/修改游览/取消游览 → ToBookExcursion"
            ""
            "### 通用原则"
            "向客户提供详细的信息。"
            "您可以使用高德地图工具搜索真实的景点、酒店、餐厅等POI信息，使用天气工具查询目的地天气，使用路径规划工具规划多个地点之间的最佳路线。"
            "当用户提到多个想去的地点时，自动调用路径规划工具为用户规划最佳游览顺序。"
            "\n特别注意："
            " - 当 search_reviews 返回包含 'fallback' 字段的结果时，说明数据库中没有该景点的评价数据。"
            "   此时请使用您自身对景点的知识，直接为用户撰写景点介绍、特色亮点和游玩建议，不要告诉用户数据库缺失。"
            "\n\n当前用户的航班信息:\n<Flights>\n{user_info}\n</Fllights>"
            "\n当前时间: {time}.",
        ),
        ("placeholder", "{messages}"),
    ]
).partial(time=datetime.now())

# 定义主助理使用的工具
primary_assistant_tools = [
    search_flights,  # 搜索航班的工具
    lookup_policy,  # 查找公司政策的工具
    amap_search_poi,  # 高德地图POI搜索
    amap_geocode,  # 高德地图地理编码（地址转经纬度）
    amap_get_weather,  # 高德实时天气查询
    amap_get_forecast,  # 高德天气预报
    plan_route,  # 路径规划（旅行商问题）
    get_route_distance,  # 获取两点间距离和时间
    search_reviews,  # 景点/地点用户评价查询
]

# 创建可运行对象，绑定主助理提示模板和工具集，包括委派给专门助理的工具
assistant_runnable = primary_assistant_prompt | llm.bind_tools(
    primary_assistant_tools
    + [
        ToFlightBookingAssistant,  # 用于转交航班更新或取消的任务
        ToHotelBookingAssistant,  # 用于转交酒店预订的任务
        ToBookExcursion,  # 用于转交旅行推荐和其他游览预订的任务
    ]
)

