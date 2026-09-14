# 使用AI大模型

import os
import json

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from app.core.runtime_config import get_runtime_config

# 加载 .env 文件中的环境变量（作为兜底默认值）
load_dotenv()


class VectorengineChatOpenAI(ChatOpenAI):
    """修复非标准网关的兼容性问题。

    当 OPENAI_BASE_URL 配错（例如写成网站域名 www.siliconflow.cn 而非
    api.siliconflow.cn）时，网关会返回 HTML 首页而不是 JSON，SDK 会把它当成
    字符串，下游 ``response.model_dump()`` 便抛出
    ``'str' object has no attribute 'model_dump'``。

    这里统一走 ``self.client.create(**payload)`` 拿到 SDK 解析好的对象；若拿到的是
    字符串（HTML/非 JSON），则抛出清晰可读的错误，而不是崩溃。
    """

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        payload = self._get_request_payload(messages, stop=stop, **kwargs)
        if "response_format" in payload:
            payload.pop("stream", None)
            response = self.root_client.chat.completions.parse(**payload)
            return self._create_chat_result(response, None)
        elif self._use_responses_api(payload):
            # 真·OpenAI 走原来的逻辑（siliconflow 等网关不会走到这里）
            return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

        payload.pop("stream", None)
        response = self.client.create(**payload)
        # 防御：网关返回了非 JSON（如 HTML 错误页）时，给出清晰提示
        if isinstance(response, str):
            try:
                response = json.loads(response)
            except json.JSONDecodeError:
                head = response[:200].replace("\n", " ")
                raise ValueError(
                    "大模型接口返回的不是合法 JSON（很可能是指向了网站首页而非 API 端点）。"
                    "请检查 OPENAI_BASE_URL 是否正确（应使用 api.siliconflow.cn 而非 www.siliconflow.cn）。"
                    f"原始返回前 200 字符：{head}"
                )
        return self._create_chat_result(response, None)


# llm = ChatOpenAI(
#     temperature=0,
#     model="GLM-4-0520",
#     openai_api_key="YOUR_API_KEY",
#     openai_api_base="https://open.bigmodel.cn/api/paas/v4/",
# )


def _resolve_llm_config() -> dict:
    """优先取前端保存的运行时配置，未设置则回退到环境变量 / 默认值。"""
    runtime = get_runtime_config()
    return {
        "temperature": float(runtime.openai_temperature or os.getenv("OPENAI_TEMPERATURE", "0.2")),
        "model": runtime.openai_model or os.getenv("OPENAI_MODEL", "deepseek-ai/DeepSeek-V3"),
        "openai_api_key": runtime.openai_api_key or os.getenv("OPENAI_API_KEY"),
        "openai_api_base": runtime.openai_base_url or os.getenv("OPENAI_BASE_URL"),
    }


llm = VectorengineChatOpenAI(
    # 方案2：降温以提升 tool-calling 的指令遵循度与答案稳定性，减少“自由发挥/编造”。
    # 默认 0.2，可通过前端设置或环境变量 OPENAI_TEMPERATURE 调整。
    **_resolve_llm_config(),
    max_retries=1,  # 限流时快速失败，避免反复重试把额度打满、表现为"超时"
    timeout=45,  # 单次请求 45 秒超时，缩短整体耗时，避免长时间挂起导致前端超时
)

# llm = ChatOpenAI(  # openai的
#     temperature=0,
#     model='gpt-4o',
#     api_key="YOUR_API_KEY",
#     base_url="https://xiaoai.plus/v1")

# llm = ChatOpenAI(  # openai的
#     temperature=0,
#     model='claude-3-7-sonnet-20250219',
#     api_key="YOUR_API_KEY",
#     base_url="https://xiaoai.plus/v1")

# llm = ChatOpenAI(
#     temperature=0,
#     model='deepseek-chat',
#     api_key="YOUR_API_KEY",
#     base_url="https://api.deepseek.com")
