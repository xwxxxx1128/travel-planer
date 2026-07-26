from typing import List, Dict
import requests
import gradio as gr
import uuid
import hashlib
import asyncio
import aiohttp
from functools import lru_cache
from datetime import datetime, timedelta

from langchain_core.messages import ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.constants import START, END
from langgraph.graph import StateGraph
from langgraph.prebuilt import tools_condition

from graph_chat.assistant import CtripAssistant, assistant_runnable, primary_assistant_tools
from graph_chat.base_data_model import ToFlightBookingAssistant, ToHotelBookingAssistant, \
    ToBookExcursion
from graph_chat.build_child_graph import build_flight_graph, builder_hotel_graph, \
    builder_excursion_graph
from tools.flights_tools import fetch_user_flight_information
from graph_chat.draw_png import draw_graph
from graph_chat.state import State
from tools.init_db import update_dates
from tools.tools_handler import create_tool_node_with_fallback, _print_event

# FastAPI 后端地址
BACKEND_URL = "http://127.0.0.1:8000/api"

# 全局用户认证状态
user_state = {
    "logged_in": False,
    "token": None,
    "username": None
}

# 响应缓存：存储常见问题的回复
response_cache = {}
cache_expiry = {}  # 缓存过期时间

def get_cache_key(user_input: str) -> str:
    """生成缓存键"""
    return hashlib.md5(user_input.encode()).hexdigest()

def get_cached_response(user_input: str) -> str:
    """获取缓存的响应"""
    cache_key = get_cache_key(user_input)
    if cache_key in response_cache:
        expiry_time = cache_expiry.get(cache_key)
        if expiry_time and datetime.now() < expiry_time:
            return response_cache[cache_key]
        else:
            # 缓存已过期，删除
            del response_cache[cache_key]
            del cache_expiry[cache_key]
    return None

def set_cached_response(user_input: str, response: str, ttl_minutes=30):
    """设置缓存响应"""
    cache_key = get_cache_key(user_input)
    response_cache[cache_key] = response
    cache_expiry[cache_key] = datetime.now() + timedelta(minutes=ttl_minutes)

# 异步HTTP客户端
async def async_register_user(username, password, phone, email):
    """异步用户注册"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{BACKEND_URL}/register/", json={
                "username": username,
                "password": password,
                "phone": phone,
                "email": email,
                "real_name": username
            }) as response:
                if response.status == 200:
                    return "注册成功！请登录", True
                else:
                    data = await response.json()
                    return f"注册失败: {data.get('detail', '未知错误')}", False
    except Exception as e:
        return f"注册失败: {str(e)}", False

async def async_login_user(username, password):
    """异步用户登录"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{BACKEND_URL}/login/", json={
                "username": username,
                "password": password
            }) as response:
                if response.status == 200:
                    data = await response.json()
                    user_state["logged_in"] = True
                    user_state["token"] = data.get("token")
                    user_state["username"] = data.get("username")
                    return f"登录成功！欢迎 {data.get('username')}", True
                else:
                    data = await response.json()
                    return f"登录失败: {data.get('detail', '未知错误')}", False
    except Exception as e:
        return f"登录失败: {str(e)}", False

def register_user(username, password, phone, email):
    """用户注册"""
    try:
        response = requests.post(f"{BACKEND_URL}/register/", json={
            "username": username,
            "password": password,
            "phone": phone,
            "email": email,
            "real_name": username
        })
        if response.status_code == 200:
            return "注册成功！请登录", True
        else:
            return f"注册失败: {response.json().get('detail', '未知错误')}", False
    except Exception as e:
        return f"注册失败: {str(e)}", False

def login_user(username, password):
    """用户登录"""
    try:
        response = requests.post(f"{BACKEND_URL}/login/", json={
            "username": username,
            "password": password
        })
        if response.status_code == 200:
            data = response.json()
            user_state["logged_in"] = True
            user_state["token"] = data.get("token")
            user_state["username"] = data.get("username")
            return f"登录成功！欢迎 {data.get('username')}", True
        else:
            return f"登录失败: {response.json().get('detail', '未知错误')}", False
    except Exception as e:
        return f"登录失败: {str(e)}", False

def logout_user():
    """用户登出"""
    user_state["logged_in"] = False
    user_state["token"] = None
    user_state["username"] = None
    return "已登出", True

def get_user_status():
    """获取用户登录状态"""
    if user_state["logged_in"]:
        return f"当前用户: {user_state['username']}"
    else:
        return "未登录"

# 定义了一个流程图的构建对象
builder = StateGraph(State)


def get_user_info(state: State):
    """
    获取用户的航班信息并更新状态字典。
    参数:
        state (State): 当前状态字典。
    返回:
        dict: 包含用户信息的新状态字典。
    """
    return {"user_info": fetch_user_flight_information.invoke({})}


# 新增：fetch_user_info节点首先运行，这意味着我们的助手可以在不采取任何行动的情况下看到用户的航班信息
builder.add_node('fetch_user_info', get_user_info)
builder.add_edge(START, 'fetch_user_info')

# 添加 三个业务助理 的 子工作流
builder = build_flight_graph(builder)
builder = builder_hotel_graph(builder)
builder = builder_excursion_graph(builder)

# 添加主助理
builder.add_node('primary_assistant', CtripAssistant(assistant_runnable))
builder.add_node(
    "primary_assistant_tools", create_tool_node_with_fallback(primary_assistant_tools)  # 主助理工具节点，包含各种工具
)


def route_primary_assistant(state: dict):
    """
    根据当前状态 判断路由到 子助手节点。
    :param state: 当前对话状态字典
    :return: 下一步应跳转到的节点名
    """
    route = tools_condition(state)  # 判断下一步的方向
    if route == END:
        return END  # 如果结束条件满足，则返回END
    tool_calls = state["messages"][-1].tool_calls  # 获取最后一条消息中的工具调用
    if tool_calls:
        if tool_calls[0]["name"] == ToFlightBookingAssistant.__name__:
            return "enter_update_flight"  # 跳转至航班预订入口节点
        elif tool_calls[0]["name"] == ToHotelBookingAssistant.__name__:
            return "enter_book_hotel"  # 跳转至酒店预订入口节点
        elif tool_calls[0]["name"] == ToBookExcursion.__name__:
            return "enter_book_excursion"  # 跳转至游览预订入口节点
        return "primary_assistant_tools"  # 否则跳转至主助理工具节点
    raise ValueError("无效的路由")  # 如果没有找到合适的工具调用，抛出异常


builder.add_conditional_edges(
    'primary_assistant',
    route_primary_assistant,
    [
        "enter_update_flight",  # 航班 子助手的入口节点
        "enter_book_hotel",  # 酒店 子助手的入口节点
        "enter_book_excursion",  # 旅游景点 子助手的入口节点
        "primary_assistant_tools",  # 主助手的工具： 全网搜索工具，查询企业政策的工具
        END,
    ]
)

builder.add_edge('primary_assistant_tools', 'primary_assistant')


# 每个委托的工作流可以直接响应用户。当用户响应时，我们希望返回到当前激活的工作流
def route_to_workflow(state: dict) -> str:
    """
    如果我们在一个委托的状态中，直接路由到相应的助理。
    :param state: 当前对话状态字典
    :return: 应跳转到的节点名
    """
    dialog_state = state.get("dialog_state")
    if not dialog_state:
        return "primary_assistant"  # 如果没有对话状态，返回主助理
    return dialog_state[-1]  # 返回最后一个对话状态


builder.add_conditional_edges("fetch_user_info", route_to_workflow)  # 根据获取用户信息进行路由

memory = MemorySaver()
graph = builder.compile(
    checkpointer=memory,
    interrupt_before=[
        "update_flight_sensitive_tools",
        "book_hotel_sensitive_tools",
        "book_excursion_sensitive_tools",
    ]
)

#
# draw_graph(graph, 'graph4.png')

session_id = str(uuid.uuid4())
# update_dates()  # 每次测试的时候：保证数据库是全新的，保证，时间也是最近的时间

# 配置参数，包含乘客ID和线程ID
config = {
    "configurable": {
        # passenger_id用于我们的航班工具，以获取用户的航班信息
        "passenger_id": "3442 587242",
        # 检查点由session_id访问
        "thread_id": session_id,
    }
}


def execute_graph(chat_bot) -> List:
    """ 执行工作流的函数（带缓存优化）"""
    # 更健壮地处理 Gradio 6.0 的消息格式
    user_input = ''
    
    if not chat_bot or len(chat_bot) == 0:
        return []
    
    last_message = chat_bot[-1]
    
    # 处理不同的消息格式
    if isinstance(last_message, dict):
        user_input = last_message.get('content', '')
    elif hasattr(last_message, 'content'):
        user_input = last_message.content
    elif isinstance(last_message, str):
        user_input = last_message
    elif isinstance(last_message, list) and len(last_message) > 0:
        # 处理嵌套列表的情况
        inner = last_message[-1]
        if isinstance(inner, dict):
            user_input = inner.get('content', '')
        elif hasattr(inner, 'content'):
            user_input = inner.content
        else:
            user_input = str(inner)
    else:
        user_input = str(last_message)
    
    # 确保 user_input 是字符串
    if not isinstance(user_input, str):
        user_input = str(user_input)
    
    # 检查缓存
    cached_result = get_cached_response(user_input)
    if cached_result:
        print(f"使用缓存响应: {user_input[:50]}...")
        chat_bot.append({'role': 'assistant', 'content': cached_result})
        return chat_bot
    
    result = ''  # AI助手的最后一条消息

    if user_input.strip().lower() != 'y':  # 正常的用户提问
        events = graph.stream({'messages': ('user', user_input)}, config, stream_mode='values')
    else:  # 用户输入的是一个： y，表示确认
        events = graph.stream(None, config, stream_mode='values')

    for event in events:
        messages = event.get('messages')
        if messages:
            if isinstance(messages, list):
                message = messages[-1] # 如果消息是列表，则取最后一个
            if message.__class__.__name__ == 'AIMessage':
                if message.content:
                    result = message.content  # 需要在Webui展示的消息
            msg_repr = message.pretty_repr(html=True)
            if len(msg_repr) > 1500:
                msg_repr = msg_repr[:1500] + " ... （已截断）"  # 超过最大长度则截断
            print(msg_repr)  # 输出消息的表示形式

    current_state = graph.get_state(config)
    if current_state.next:  # 出现了工作流的中断
        result = "AI助手马上根据你要求，执行相关操作。您是否批准上述操作？输入'y'继续；否则，请说明您请求的更改。\n"
    
    # 缓存结果（仅缓存成功的响应）
    if result and user_input.strip().lower() != 'y':
        set_cached_response(user_input, result, ttl_minutes=30)

    # 使用字典格式
    chat_bot.append({'role': 'assistant', 'content': result})
    return chat_bot


def do_graph(user_input, chat_bot):
    """输入框提交后，执行的函数"""
    if user_input:
        # 使用字典格式
        chat_bot.append({'role': 'user', 'content': user_input})
    return '', chat_bot


css = '''
#bgc {background-color: #7FFFD4}
.feedback textarea {font-size: 24px !important}
.function-card {
    border: 1px solid #ddd;
    border-radius: 8px;
    padding: 15px;
    margin: 10px 0;
    background-color: #f9f9f9;
}
'''

with gr.Blocks(title='出行规划智能助手') as instance:
    gr.Markdown("# 出行规划智能助手")
    
    # 用户状态显示
    with gr.Row():
        user_status = gr.Textbox(label="用户状态", value=get_user_status(), interactive=False)
        refresh_status_btn = gr.Button("刷新状态", size="sm")
    
    # 功能展示区域
    with gr.Accordion("可用功能", open=True):
        gr.Markdown("""
        ### 🛫 航班服务
        - 查询航班信息
        - 预订航班
        - 修改航班
        - 取消航班
        
        ### 🏨 酒店服务  
        - 搜索酒店
        - 预订酒店
        - 修改酒店预订
        - 取消酒店预订
        
        ### 🎯 旅游景点
        - 搜索旅游景点
        - 预订游览活动
        - 修改游览预订
        - 取消游览预订
        
        ### 🔍 其他服务
        - 全网搜索
        - 查询公司政策
        - 获取旅行推荐
        """)
    
    # 注册登录区域
    with gr.Tabs() as auth_tabs:
        with gr.Tab("登录"):
            with gr.Row():
                login_username = gr.Textbox(label="用户名", placeholder="请输入用户名")
                login_password = gr.Textbox(label="密码", type="password", placeholder="请输入密码")
            with gr.Row():
                login_btn = gr.Button("登录", variant="primary")
                login_result = gr.Textbox(label="登录结果", interactive=False)
        
        with gr.Tab("注册"):
            with gr.Row():
                reg_username = gr.Textbox(label="用户名", placeholder="请输入用户名")
                reg_password = gr.Textbox(label="密码", type="password", placeholder="请输入密码")
            with gr.Row():
                reg_phone = gr.Textbox(label="手机号", placeholder="请输入手机号")
                reg_email = gr.Textbox(label="邮箱", placeholder="请输入邮箱")
            with gr.Row():
                register_btn = gr.Button("注册", variant="primary")
                register_result = gr.Textbox(label="注册结果", interactive=False)
    
    # 登出按钮
    with gr.Row():
        logout_btn = gr.Button("登出", variant="stop")
    
    # 聊天区域
    gr.Markdown("## 💬 AI助手对话")
    chatbot = gr.Chatbot(height=400, label='AI助手')  # 聊天记录组件
    input_textbox = gr.Textbox(label='请输入你的问题📝', value='', placeholder="例如：帮我查询从北京到上海的航班")  # 输入框组件
    
    # 事件绑定
    refresh_status_btn.click(get_user_status, outputs=user_status)
    
    login_btn.click(
        login_user, 
        inputs=[login_username, login_password], 
        outputs=[login_result]
    ).then(
        get_user_status, 
        outputs=user_status
    )
    
    register_btn.click(
        register_user,
        inputs=[reg_username, reg_password, reg_phone, reg_email],
        outputs=[register_result]
    )
    
    logout_btn.click(
        logout_user,
        outputs=[login_result]
    ).then(
        get_user_status,
        outputs=user_status
    )
    
    input_textbox.submit(do_graph, [input_textbox, chatbot], [input_textbox, chatbot]).then(execute_graph, chatbot, chatbot)

if __name__ == '__main__':
    # 启动Gradio的应用
    instance.launch(debug=True, css=css)
