import os
from datetime import datetime

from langchain_core.messages import AIMessage, HumanMessage, trim_messages
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_openai import ChatOpenAI

from graph_chat.base_data_model import ToFlightBookingAssistant, ToHotelBookingAssistant, \
    ToTravelList
from graph_chat.llm_config import llm
from graph_chat.state import State
from tools.amap_tools import amap_search_poi, amap_geocode, amap_search_around
from tools.flight_bookings_tools import list_my_flights
from tools.flights_tools import search_flights
from tools.hotels_tools import book_hotel, update_hotel, cancel_hotel
from tools.retriever_vector import lookup_policy
from tools.weather_tools import amap_get_weather, amap_get_forecast
from tools.route_planner import plan_route, get_route_distance
from tools.reviews_tools import search_reviews


import logging
logger = logging.getLogger(__name__)

def _count_tokens(messages) -> int:
    """粗略按字符数/4 估算 token，避免依赖具体模型的 tokenizer（网关模型常无对应 tokenizer）。"""
    total = 0
    for m in messages:
        content = getattr(m, "content", "")
        total += len(content) if isinstance(content, str) else len(str(content))
    return total // 4


# --------------------------------------------------------------------------- #
# 方案4：评价类提问的“后置校验”辅助
# 说明：主助手是否调用 search_reviews 由模型自主决定，存在“凭自身知识编造评价 +
# 伪造来源链接”的风险。这里在节点内做兜底校验：评价类提问若既没检索、也没拿到
# 系统预取的材料，却直接作答，则补一次“强制检索”提示后重试。
# 注意：_REVIEW_CTX_MARK 必须与 app/services/review_intent.MARK_PREFIX 保持一致。
# --------------------------------------------------------------------------- #
_REVIEW_CTX_MARK = "【评价检索"
_REVIEW_HINT_WORDS = (
    "评价", "点评", "口碑", "游记", "好评", "差评", "游客", "游人",
    "值得去", "好玩吗", "推荐吗",
)
_REVIEW_GENERIC_BLOCK = (
    "天气", "路线", "酒店", "机票", "航班", "门票", "交通", "美食", "餐厅",
    "住宿", "价格", "费用", "规划", "行程",
)


def _is_review_query(messages) -> bool:
    """最后一条用户消息是否为“景点评价类”提问（排除天气/酒店等通用主题）。"""
    for m in reversed(messages or []):
        if isinstance(m, HumanMessage):
            content = m.content
            text = content if isinstance(content, str) else str(content)
            if any(b in text for b in _REVIEW_GENERIC_BLOCK):
                return False
            return any(w in text for w in _REVIEW_HINT_WORDS)
    return False


def _called_search_reviews(messages) -> bool:
    """本轮对话中是否调用过 search_reviews。"""
    for m in messages or []:
        for tc in (getattr(m, "tool_calls", []) or []):
            if tc.get("name") == "search_reviews":
                return True
    return False


def _has_prefetched_review_ctx(messages) -> bool:
    """本轮是否已注入系统预取的评价上下文（材料或无材料提示）。"""
    for m in messages or []:
        content = getattr(m, "content", "")
        if isinstance(content, str) and _REVIEW_CTX_MARK in content:
            return True
    return False


# --------------------------------------------------------------------------- #
# 航班类提问的“后置校验”（与评价类同理）：主助手是否调用航班工具由模型自主决定，
# 存在“凭自身知识编造航班号/时刻”的风险。这里在节点内做兜底：航班类提问若未调用
# 任何航班工具却直接作答，则补一次“强制检索”提示后重试。
# --------------------------------------------------------------------------- #
_FLIGHT_HINT_WORDS = ("航班", "班次", "机票", "飞机", "直飞", "机场")
_FLIGHT_PERSONAL_WORDS = ("我的", "我订", "我买", "已订", "我已")
_FLIGHT_TOOL_NAMES = ("search_flights", "list_my_flights")
# 系统预取的航班班次上下文标记（与 app/services/flight_intent.MARK_PREFIX 保持一致）
_FLIGHT_CTX_MARK = "【航班班次检索"


def _last_user_text(messages) -> str:
    """返回最后一条用户消息的文本，没有则返回空串。"""
    for m in reversed(messages or []):
        if isinstance(m, HumanMessage):
            content = m.content
            return content if isinstance(content, str) else str(content)
    return ""


def _is_flight_query(messages) -> bool:
    """最后一条用户消息是否为航班相关提问。"""
    text = _last_user_text(messages)
    return any(w in text for w in _FLIGHT_HINT_WORDS)


def _is_my_flight_query(messages) -> bool:
    """最后一条用户消息是否为“查询我本人的航班”。"""
    text = _last_user_text(messages)
    return any(w in text for w in _FLIGHT_HINT_WORDS) and any(
        w in text for w in _FLIGHT_PERSONAL_WORDS
    )


def _called_any_flight_tool(messages) -> bool:
    """本轮是否调用过任一航班工具。"""
    for m in messages or []:
        for tc in (getattr(m, "tool_calls", []) or []):
            if tc.get("name") in _FLIGHT_TOOL_NAMES:
                return True
    return False


def _has_prefetched_flight_ctx(messages) -> bool:
    """本轮是否已注入系统预取的航班班次结果（材料或无航班提示）。"""
    for m in messages or []:
        content = getattr(m, "content", "")
        if isinstance(content, str) and _FLIGHT_CTX_MARK in content:
            return True
    return False


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
        review_nudged = False  # 方案4：本轮是否已触发过“强制检索”提示
        flight_nudged = False  # 航班类提问是否已触发过“强制检索”提示
        while True:
            # 关键优化：仅用“裁剪后的最近对话”喂给大模型，避免 messages 用 add_messages
            # 无限累积导致轮次越多每次调用越慢（对标 trip_assistant 的 history[-6:] 思路）。
            # 这里只裁剪“喂给模型”的上下文，不改动持久化的 state，记忆/审批流程不受影响。
            trimmed = _MESSAGE_TRIMMER.invoke(state.get("messages") or [])
            local_state = {**state, "messages": trimmed}
            result = self.runnable.invoke(local_state)

            logger.info(
                "primary_assistant 模型返回 tool_calls=%s content_head=%s",
                [tc.get("name") for tc in (result.tool_calls or [])],
                (str(result.content)[:120] if result.content else ""),
            )

            # 方案4：评价类提问的后置校验。若本轮是评价类提问、模型既未调用 search_reviews、
            # 也没有系统预取的评价材料，却直接给出了文字回答，则补一次“强制检索”提示后重试，
            # 避免“凭自身知识编造评价 + 伪造来源链接”。
            if (
                not review_nudged
                and not result.tool_calls
                and result.content
                and _is_review_query(state.get("messages") or [])
                and not _called_search_reviews(state.get("messages") or [])
                and not _has_prefetched_review_ctx(state.get("messages") or [])
            ):
                review_nudged = True
                logger.info("评价类提问未检索即作答，触发一次强制检索提示")
                messages = state["messages"] + [
                    (
                        "user",
                        "请先调用 search_reviews 工具获取该景点的联网评价材料，再基于材料作答；"
                        "若确实无法获取，请如实说明。严禁凭自身知识编造评价或来源链接。",
                    )
                ]
                state = {**state, "messages": _MESSAGE_TRIMMER.invoke(messages)}
                continue

            # 航班类提问的后置校验：未调用任何航班工具却直接作答 → 强制调用对应工具后重试。
            # 仅在主助手层（未进入子流程）触发，避免干扰航班子助手的正常多轮交互。
            if (
                not flight_nudged
                and not result.tool_calls
                and result.content
                and not state.get("dialog_state")
                and _is_flight_query(state.get("messages") or [])
                and not _called_any_flight_tool(state.get("messages") or [])
                and not _has_prefetched_flight_ctx(state.get("messages") or [])
            ):
                flight_nudged = True
                if _is_my_flight_query(state.get("messages") or []):
                    hint = (
                        "请先调用 list_my_flights 查询当前登录用户本人的航班订单再作答；"
                        "若返回「还没有已预订的航班」，请如实转述。严禁编造航班号、时刻、机型。"
                    )
                else:
                    hint = (
                        "请先调用 search_flights 获取真实航班班次数据（可直接传中文城市名）再作答；"
                        "若查询不到请如实说明。严禁凭自身记忆编造航班号、起降时刻、机型或价格。"
                    )
                logger.info("航班类提问未调用工具即作答，触发一次强制检索提示")
                messages = state["messages"] + [("user", hint)]
                state = {**state, "messages": _MESSAGE_TRIMMER.invoke(messages)}
                continue

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
            "### 评价类问题的强制规则（最高优先级）"
            "当用户询问任何景点/地点的评价、口碑、点评、游客感受、是否值得去时："
            " - 若上下文中已包含系统预取的评价材料（以「【评价检索材料·预取】」开头），"
            "   请直接基于该材料聚合作答，不要再重复调用工具；"
            " - 若上下文标记为「【评价检索结果·无材料】」，说明系统已尝试检索但未获取到材料，"
            "   请如实告知用户当前无法提供该景点评价，不要编造；"
            " - 若上述上下文均不存在，你必须先调用 search_reviews 获取材料后再作答；"
            " - 严禁在没有任何检索材料的情况下，凭自身知识编造评价内容或来源链接。"
            ""
            "## 指令"
            ""
            "### 航班类问题的强制规则（最高优先级）"
            "涉及任何具体航班号、班次、起降时刻、机型、价格的询问："
            " - 若上下文中已包含系统预取的班次结果（以「【航班班次检索结果·预取】」开头），"
            "   请直接基于该数据如实作答，不要再重复调用 search_flights；"
            "   若标记为「【航班班次检索结果·无航班】」，说明系统已查库但无匹配，请如实告知、不要编造；"
            " - 其余情况必须先调用工具获取真实数据：查班次用 search_flights，查本人订单用 list_my_flights；"
            " - 只允许基于工具返回的数据作答；工具无结果时如实说明「未查询到」，不要编造；"
            " - 严禁凭自身记忆编造航班号（如 CA1501）、起降时刻、机型、价格或购票链接。"
            ""
            "### 查询类请求（主助手自行处理，不路由到专门助理）"
            "对于以下场景，您自己直接使用工具完成，不需要委派给专门助理："
            " - 搜索酒店、查找酒店信息 → 使用 amap_search_poi"
            " - 搜索景点、餐厅、POI → 使用 amap_search_poi 或 amap_search_around"
            " - 查询天气 → 使用 amap_get_weather / amap_get_forecast"
            " - 路线规划 → 使用 plan_route / get_route_distance"
            " - 查询两城之间的航班班次（如「北京到上海有哪些航班」）→ 使用 search_flights（直接传中文城市名，如「北京」）"
            " - 查询「我的航班 / 我的机票 / 我的行程 / 我的预订」→ 使用 list_my_flights（查本人订单）"
            " - 查看政策 → 使用 lookup_policy"
            " - 查看评价 → 使用 search_reviews（基于 Tavily 网页搜索的互联网公开游记/攻略材料）"
            ""
            "### 操作类请求（才需要路由到专门助理）"
            "只有在用户明确要求以下操作时，才调用对应的委派工具路由到专门助理："
            " - 预订航班 / 取消我的航班 → ToFlightBookingAssistant"
            " - 预订酒店/修改酒店/取消酒店 → ToHotelBookingAssistant"
            " - 查看旅行清单 / 把地点加入或移出旅行清单 → ToTravelList"
            ""
            "注意：当用户表达「看看我的旅行清单」「管理我的旅行清单」「把某某加入/移出清单」时，"
            "属于 ToTravelList 的职责，请委派给 ToTravelList。"
            ""
            "### 通用原则"
            "向客户提供详细的信息。"
            "您可以使用高德地图工具搜索真实的景点、酒店、餐厅等POI信息，使用天气工具查询目的地天气，使用路径规划工具规划多个地点之间的最佳路线。"
            "当用户提到多个想去的地点时，自动调用路径规划工具为用户规划最佳游览顺序。"
            "\n特别注意："
            " - search_reviews 返回的是互联网公开游记/攻略材料（标题、摘要、来源链接），请仅基于这些材料"
            "   聚合提炼游客评价，必须附上原始来源链接，严禁编造内容；材料有限时如实说明信息有限；"
            "   若返回「未检索到/暂不可用」等提示，请如实告知用户当前无法提供该景点评价，不要用自身知识编造。"
            "\n当前时间: {time}.",
        ),
        ("placeholder", "{messages}"),
    ]
).partial(time=datetime.now())

# 定义主助理使用的工具
primary_assistant_tools = [
    search_flights,  # 搜索航班班次的工具（任意城市之间）
    list_my_flights,  # 查询当前登录用户本人航班订单的工具
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
        ToTravelList,  # 用于转交旅行清单管理（加入/移出/查看）的任务
    ]
)

