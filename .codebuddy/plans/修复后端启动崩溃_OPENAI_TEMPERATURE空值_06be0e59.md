---
name: 修复后端启动崩溃_OPENAI_TEMPERATURE空值
overview: 后端执行 python main.py 时在导入期崩溃：graph_chat/llm_config.py 第65行对空字符串调用 float() 抛出 ValueError。根因是 .env 中 OPENAI_TEMPERATURE 被置为空值，且 os.getenv 在变量"存在但为空"时返回 '' 而非默认值，导致 `or` 兜底失效。修复该行使其对空值健壮回退到默认温度 0.2，并清理 .env 中的空值行，使后端恢复正常启动。此问题与高德 API 无关。
todos:
  - id: fix-llm-temperature
    content: 修改 graph_chat/llm_config.py 第65行，使温度解析对空值回退默认0.2
    status: completed
  - id: clean-env
    content: 清理 .env 中 OPENAI_TEMPERATURE 空值行（删除或设为0.2）
    status: completed
  - id: verify-startup
    content: 运行 python main.py 验证启动越过导入期不再报 ValueError
    status: completed
    dependencies:
      - fix-llm-temperature
---

## 用户需求

运行 `python main.py` 启动后端时，在导入期即抛出 `ValueError: could not convert string to float: ''`，导致服务根本起不来。用户希望在解决高德 API 问题之前，先把后端启动恢复。

## 问题本质（已核实）

- 崩溃点：`graph_chat/llm_config.py:65` 的 `_resolve_llm_config()` 在模块被 import 时就执行（`llm = VectorengineChatOpenAI(**_resolve_llm_config(), ...)`），把温度值直接 `float()`。
- 当前 `.env` 第 32 行为 `OPENAI_TEMPERATURE=`（值为空）。`runtime.openai_temperature` 来自 `app/core/runtime_config.py` 的 `_get_env('OPENAI_TEMPERATURE')`，空值返回 `''`；`'' or os.getenv("OPENAI_TEMPERATURE", 0.2)` 因该环境变量"存在但为空"，`os.getenv` 返回 `''` 而非默认值 `0.2`，最终 `float('')` 抛异常。
- 此问题与前序排查的高德 API 失效完全无关，是独立配置 bug；其余字段（model / api_key / base_url）均为字符串，空值不触发崩溃。已全局检索确认：项目内 `float(` 仅 `llm_config.py:65` 这一处会消费环境变量/运行时配置，其余 `float()` 均来自高德返回数据且带 `0` 默认值，安全。

## 修复目标

以最小改动让后端正常启动：使温度解析对空值健壮回退到默认 `0.2`，并清理 `.env` 中的空值残留。

## 技术栈

Python 3 + FastAPI + LangChain（`ChatOpenAI`）。配置经 `app/core/runtime_config.py` 与 `.env` 双向同步（前端"服务配置"页保存即写回 `.env` 并刷新 `os.environ`）。

## 实施方案

核心只改崩溃点一行，把"空字符串"纳入兜底，避免 `float('')`：

```python
# graph_chat/llm_config.py  _resolve_llm_config() 内，第 65 行
# 修改前：
"temperature": float(runtime.openai_temperature or os.getenv("OPENAI_TEMPERATURE", 0.2)),
# 修改后：
"temperature": float(runtime.openai_temperature or os.getenv("OPENAI_TEMPERATURE") or 0.2),
```

逻辑校验（消费侧防御）：

- `runtime` 为空且环境变量未设置 → `'' or None or 0.2` → `0.2`；
- `runtime` 为空且环境变量为空串 → `'' or '' or 0.2` → `0.2`；
- `runtime` 为合法值（如 `"0.7"`）→ 直接使用；
- 环境变量合法（如 `"0.5"`）且 `runtime` 为空 → 使用环境变量值。

## 实施要点

- 防御放在消费侧（`llm_config.py`）而非 `runtime_config.py`：改动最小、且即使前端再次保存空温度也不会再崩，比只改 `.env` 更稳。
- 不触碰与本次崩溃无关的任何代码（`route_planner.py`、高德相关、`runtime_config.py` 写回逻辑均不动）。
- `.env` 清理为辅助步骤：删除第 32 行空值或改为 `OPENAI_TEMPERATURE=0.2`（README.md:193 示例值即 `0.2`，与默认一致）。代码修复后此步非强制，但可消除空值残留、避免误导。

## 验证

再次 `python main.py`，确认越过 `llm_config` 导入、不再出现 `ValueError`，可观察到后续进入 `sync_flight_dataset()` 或端口监听（注意首次启动航班日期平移可能耗时，属正常）。

## 目录结构与受影响文件

- `graph_chat/llm_config.py`  [MODIFY] 第 65 行温度解析，兼容空值回退默认 `0.2`；模块导入期执行，修复即恢复启动。
- `.env`  [MODIFY] 第 32 行 `OPENAI_TEMPERATURE=` 清理为空行或填 `0.2`，消除空值残留（辅助）。