"""vector_store Chroma 客户端选择单元测试（mock，离线）。

验证：配置了 CHROMA_HTTP_URL 时走 chromadb.HttpClient（连独立服务），
未配置时退回本地嵌入式 PersistentClient（本地开发兜底）。
通过 monkeypatch 掉模块级 chromadb / settings，避免真实安装 chromadb 或连服务。
"""
from types import SimpleNamespace
import sys

import app.services.knowledge.vector_store  # 触发子模块加载

# 注意：app.services.knowledge.__init__ 里 `vector_store = ChromaStore()` 用同名实例变量
# 遮蔽了子模块，因此 `app.services.knowledge.vector_store` 指向的是实例而非模块。
# 必须从 sys.modules 取真正的模块对象，才能 monkeypatch chromadb / settings 全局。
vs_module = sys.modules["app.services.knowledge.vector_store"]
from app.services.knowledge.vector_store import ChromaStore


class _Recorder:
    calls = []

    def __init__(self, *a, **k):
        _Recorder.calls.append((self.__class__.__name__, a, k))


class _FakeHttpClient(_Recorder):
    pass


class _FakePersistent(_Recorder):
    pass


def _fake_chromadb():
    return type("chromadb", (), {"HttpClient": _FakeHttpClient, "PersistentClient": _FakePersistent})


def test_vector_store_uses_http_client(monkeypatch):
    _Recorder.calls.clear()
    monkeypatch.setattr(vs_module, "chromadb", _fake_chromadb())
    monkeypatch.setattr(
        vs_module,
        "settings",
        SimpleNamespace(CHROMA_PERSIST_DIR="/tmp/chroma_http_test", CHROMA_HTTP_URL="http://chroma:8000"),
    )
    store = ChromaStore()
    assert store.available() is True
    assert any(name == "_FakeHttpClient" for name, _, _ in _Recorder.calls)
    http_call = [c for c in _Recorder.calls if c[0] == "_FakeHttpClient"][0]
    assert http_call[2].get("host") == "chroma"
    assert http_call[2].get("port") == 8000


def test_vector_store_uses_persistent_fallback(monkeypatch):
    _Recorder.calls.clear()
    monkeypatch.setattr(vs_module, "chromadb", _fake_chromadb())
    monkeypatch.setattr(
        vs_module,
        "settings",
        SimpleNamespace(CHROMA_PERSIST_DIR="/tmp/chroma_embed_test", CHROMA_HTTP_URL=""),
    )
    store = ChromaStore()
    assert store.available() is True
    assert any(name == "_FakePersistent" for name, _, _ in _Recorder.calls)
