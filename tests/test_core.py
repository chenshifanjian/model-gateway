import pytest
import sys
from pathlib import Path

# 让测试能 import app
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as app_module


# ============================================================
# 辅助：构造 provider
# ============================================================
def provider(name="P", models=None, disabled=None):
    return {
        "name": name,
        "base_url": "http://x/v1",
        "api_key": "k",
        "models": models or [],
        "disabled_models": disabled or [],
    }


# ============================================================
# get_enabled_models
# ============================================================
def test_enabled_models_filters_disabled():
    p = provider(models=["a", "b", "c"], disabled=["b"])
    assert app_module.get_enabled_models(p) == ["a", "c"]


def test_enabled_models_no_disabled():
    p = provider(models=["a", "b"])
    assert app_module.get_enabled_models(p) == ["a", "b"]


def test_enabled_models_empty():
    p = provider(models=[])
    assert app_module.get_enabled_models(p) == []


# ============================================================
# is_chat_model / is_free_model
# ============================================================
def test_chat_model_true():
    assert app_module.is_chat_model("deepseek-ai/deepseek-v4-flash") is True


def test_chat_model_false_for_embedding():
    assert app_module.is_chat_model("text-embedding-3") is False


def test_free_model_by_pricing_zero():
    info = {"pricing": {"prompt": "0", "completion": "0"}}
    assert app_module.is_free_model(info) is True


def test_free_model_by_pricing_zero_decimal():
    info = {"pricing": {"prompt": "0.00", "completion": "0E-10"}}
    assert app_module.is_free_model(info) is True


def test_not_free_model():
    info = {"pricing": {"prompt": "0.001", "completion": "0.002"}}
    assert app_module.is_free_model(info) is False


def test_free_model_no_pricing():
    assert app_module.is_free_model({}) is False


# ============================================================
# mask_key
# ============================================================
def test_mask_key_long():
    # 前6字符 "nvapi-" + "****" + 后4字符 "lmno"
    assert app_module.mask_key("nvapi-abcdefghijklmno") == "nvapi-****lmno"


def test_mask_key_short():
    assert app_module.mask_key("short") == "****"


def test_mask_key_empty():
    assert app_module.mask_key("") == ""


# ============================================================
# merge_reasoning (透传，不合并)
# ============================================================
def test_merge_reasoning_preserves_both():
    obj = {"choices": [{"delta": {"reasoning_content": "think", "content": "hi"}}]}
    out = app_module.merge_reasoning(obj)
    assert out["choices"][0]["delta"]["content"] == "hi"
    assert out["choices"][0]["delta"]["reasoning_content"] == "think"


def test_merge_reasoning_only_reasoning():
    obj = {"choices": [{"delta": {"reasoning_content": "think"}}]}
    out = app_module.merge_reasoning(obj)
    assert out["choices"][0]["delta"]["reasoning_content"] == "think"
    assert "content" not in out["choices"][0]["delta"]


def test_merge_reasoning_no_reasoning():
    obj = {"choices": [{"delta": {"content": "hi"}}]}
    out = app_module.merge_reasoning(obj)
    assert out["choices"][0]["delta"]["content"] == "hi"


def test_merge_reasoning_message_key():
    obj = {"choices": [{"message": {"reasoning_content": "think", "content": "hi"}}]}
    out = app_module.merge_reasoning(obj)
    assert out["choices"][0]["message"]["content"] == "hi"
    assert out["choices"][0]["message"]["reasoning_content"] == "think"


def test_merge_reasoning_no_choices():
    obj = {"id": "x"}
    assert app_module.merge_reasoning(obj) == {"id": "x"}



# ============================================================
# compress / restore hermes
# ============================================================
def test_compress_then_restore_roundtrip():
    body = {"messages": [{"role": "user", "content": "mcp_hermes_studio_use_hermes_studio_use_tool"}]}
    compressed = app_module.compress_hermes(body)
    assert "mcp_hsu_" in compressed["messages"][0]["content"]
    s = app_module.restore_hermes_text("__mcp_hsu_tool__")
    assert "mcp_hermes_studio_use_hermes_studio_use_" in s


# ============================================================
# pick_available_models：disabled 过滤
# ============================================================
def test_pick_skips_disabled(monkeypatch):
    monkeypatch.setattr(app_module, "providers", [
        provider(name="NVIDIA", models=["a", "b"], disabled=["b"])
    ])
    monkeypatch.setattr(app_module, "health_status", {
        "NVIDIA||a": {"status": "ok"},
        "NVIDIA||b": {"status": "ok"},
    })
    cands = app_module.pick_available_models()
    models = [m for _, m in cands]
    assert "a" in models
    assert "b" not in models


def test_pick_respects_health(monkeypatch):
    monkeypatch.setattr(app_module, "providers", [
        provider(name="NVIDIA", models=["a", "b"])
    ])
    monkeypatch.setattr(app_module, "health_status", {
        "NVIDIA||a": {"status": "ok"},
        "NVIDIA||b": {"status": "fail"},
    })
    cands = app_module.pick_available_models()
    models = [m for _, m in cands]
    assert "a" in models
    assert "b" not in models


def test_pick_explicit_model_without_prefix_bypasses_health(monkeypatch):
    # 显式指定裸模型名，跳过健康检查，直接透传给上游
    monkeypatch.setattr(app_module, "providers", [
        provider(name="NVIDIA", models=["a", "b"])
    ])
    monkeypatch.setattr(app_module, "health_status", {
        "NVIDIA||a": {"status": "ok"},
        "NVIDIA||b": {"status": "fail"},
    })
    cands = app_module.pick_available_models("b")
    models = [m for _, m in cands]
    assert "b" in models  # 显式指定时不过滤，直接透传


def test_pick_force_bypasses_health(monkeypatch):
    monkeypatch.setattr(app_module, "providers", [
        provider(name="NVIDIA", models=["a", "b"])
    ])
    monkeypatch.setattr(app_module, "health_status", {
        "NVIDIA||a": {"status": "ok"},
        "NVIDIA||b": {"status": "fail"},
    })
    cands = app_module.pick_available_models("b", force=True)
    models = [m for _, m in cands]
    assert "b" in models


def test_pick_returns_empty_when_no_providers(monkeypatch):
    monkeypatch.setattr(app_module, "providers", [])
    monkeypatch.setattr(app_module, "health_status", {})
    assert app_module.pick_available_models() == []


# ============================================================
# 熔断
# ============================================================
def test_circuit_opens_after_threshold(monkeypatch):
    monkeypatch.setattr(app_module, "circuit_breaker", {})
    k = "X||y"
    for _ in range(app_module.CIRCUIT_FAIL_THRESHOLD):
        app_module.record_fail(k)
    assert app_module.is_circuit_open(k) is True


def test_circuit_resets_on_success(monkeypatch):
    monkeypatch.setattr(app_module, "circuit_breaker", {})
    k = "X||y"
    app_module.record_fail(k)
    app_module.record_success(k)
    assert app_module.is_circuit_open(k) is False


# ============================================================
# 质量分
# ============================================================
def test_quality_optimistic_when_no_data(monkeypatch):
    monkeypatch.setattr(app_module, "model_quality", {})
    assert app_module.get_quality_score("missing") == 1.0


def test_quality_tracks_ok_fail(monkeypatch):
    monkeypatch.setattr(app_module, "model_quality", {})
    k = "X||y"
    app_module.update_model_quality(k, {"status": "ok", "latency_ms": 100})
    app_module.update_model_quality(k, {"status": "ok", "latency_ms": 200})
    app_module.update_model_quality(k, {"status": "fail"})
    assert app_module.get_quality_score(k) == pytest.approx(2 / 3)


# ============================================================
# is_1m_model
# ============================================================
def test_is_1m_model_true(monkeypatch):
    monkeypatch.setattr(app_module, "model_details", {})
    # context_limits 里有 1M 的
    assert app_module.is_1m_model("deepseek-ai/deepseek-v4-flash") is True


def test_is_1m_model_false(monkeypatch):
    monkeypatch.setattr(app_module, "model_details", {})
    assert app_module.is_1m_model("sensenova-u1-fast") is False


# ============================================================
# /api/page-diag 前端诊断回传（去重 + 端点契约）
# ============================================================
def test_page_diag_dedup_window():
    t0 = 1000.0
    assert app_module.page_diag_dedup("diag-payload-A", t0) is True
    assert app_module.page_diag_dedup("diag-payload-B", t0 + 1) is True   # 不同内容互不影响
    assert app_module.page_diag_dedup("diag-payload-A", t0 + 30) is False  # 60s 内重复抑制
    assert app_module.page_diag_dedup("diag-payload-A", t0 + 61) is True   # 过窗恢复


def test_page_diag_endpoint_ok():
    from fastapi.testclient import TestClient
    client = TestClient(app_module.app)  # 不进 with：跳过 lifespan/后台任务
    r = client.post("/api/page-diag", json={"kind": "unit-test", "msg": "hello"})
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_page_diag_endpoint_oversize_rejected():
    from fastapi.testclient import TestClient
    client = TestClient(app_module.app)
    r = client.post("/api/page-diag", content=b"x" * 20000)  # httpx 自动带 content-length
    assert r.status_code == 200
    assert r.json()["ok"] is False  # 超 8KB 不读 body、不记日志


# ============================================================
# AUTO_KILL 身份校验（只杀网关，不误杀同端口陌生进程）
# ============================================================
def test_looks_like_gateway():
    assert app_module._looks_like_gateway("/home/u/.venv/bin/python app.py") is True
    assert app_module._looks_like_gateway("/opt/dist/v1.6.1-网关客户端") is True
    assert app_module._looks_like_gateway("/opt/dist/v1.6.1-模型蓄水池") is True
    assert app_module._looks_like_gateway("C:\\app\\Model-Gateway.exe") is True
    assert app_module._looks_like_gateway("C:\\app\\ModelReservoir.exe") is True
    assert app_module._looks_like_gateway("/usr/sbin/nginx: master process") is False
    assert app_module._looks_like_gateway("") is False


def test_pid_is_gateway_excludes_self_and_invalid():
    import os as _os
    assert app_module._pid_is_gateway(_os.getpid()) is False  # 不能杀自己
    assert app_module._pid_is_gateway(0) is False
    assert app_module._pid_is_gateway(-1) is False


def test_pid_is_gateway_identifies_via_info(monkeypatch):
    monkeypatch.setattr(app_module, "_pid_info",
                        lambda pid: "python app.py" if pid == 1234 else "/usr/sbin/cron -f")
    assert app_module._pid_is_gateway(1234) is True
    assert app_module._pid_is_gateway(4321) is False


def _fake_ss(*_a, **_k):
    class R:
        stdout = 'LISTEN 0 4096 127.0.0.1:8000 0.0.0.0:* users:(("x",pid=7777,fd=5))'
    return R()


def test_kill_old_instance_spares_strangers(monkeypatch):
    import os as _os
    monkeypatch.setattr(app_module.sys, "platform", "linux")  # 钉死 ss 分支，三平台同一逻辑
    killed = []
    monkeypatch.setattr(app_module.subprocess, "run", _fake_ss)
    monkeypatch.setattr(app_module, "_pid_info", lambda pid: "nginx worker process")
    monkeypatch.setattr(_os, "kill", lambda pid, sig: killed.append((pid, sig)))
    assert app_module.kill_old_instance(8000) is False
    assert killed == []            # 陌生进程分毫不动


def test_kill_old_instance_kills_gateway(monkeypatch):
    import os as _os
    monkeypatch.setattr(app_module.sys, "platform", "linux")  # 钉死 ss 分支，三平台同一逻辑
    killed = []
    monkeypatch.setattr(app_module.subprocess, "run", _fake_ss)
    monkeypatch.setattr(app_module, "_pid_info", lambda pid: "/u/.venv/bin/python app.py")
    monkeypatch.setattr(_os, "kill", lambda pid, sig: killed.append((pid, sig)))
    assert app_module.kill_old_instance(8000) is True
    assert killed == [(7777, 15)]  # 只杀网关本体，SIGTERM


def _fake_cmds(cmd, **kw):
    """按命令返回三平台各自的探测输出。"""
    class R:
        stdout = ""
    out = R()
    if cmd[0] == "lsof":          # macOS: 一 pid 一行
        out.stdout = "7777\n"
    elif cmd[0] == "ss":          # Linux: ss -ltnpH
        out.stdout = 'LISTEN 0 4096 127.0.0.1:8000 0.0.0.0:* users:(("x",pid=7777,fd=5))'
    elif cmd[0] == "netstat":     # Windows: netstat -ano
        out.stdout = "  TCP    0.0.0.0:8000            0.0.0.0:0              LISTENING       7777"
    return out


def test_kill_old_instance_darwin_branch(monkeypatch):
    import os as _os
    monkeypatch.setattr(app_module.sys, "platform", "darwin")
    killed = []
    monkeypatch.setattr(app_module.subprocess, "run", _fake_cmds)
    monkeypatch.setattr(app_module, "_pid_info", lambda pid: "python app.py")
    monkeypatch.setattr(_os, "kill", lambda pid, sig: killed.append((pid, sig)))
    assert app_module.kill_old_instance(8000) is True
    assert killed == [(7777, 15)]


def test_kill_old_instance_win32_branch(monkeypatch):
    monkeypatch.setattr(app_module.sys, "platform", "win32")
    taskkilled = []

    def fake_run(cmd, **kw):
        if cmd[0] == "taskkill":
            taskkilled.append(cmd)
        return _fake_cmds(cmd, **kw)

    monkeypatch.setattr(app_module.subprocess, "run", fake_run)
    monkeypatch.setattr(app_module, "_pid_info", lambda pid: "模型蓄水池.exe")
    assert app_module.kill_old_instance(8000) is True
    assert taskkilled and taskkilled[0][:2] == ["taskkill", "/PID"]


def test_single_instance_lock_path(tmp_path, monkeypatch):
    """锁路径跨启动方式唯一：Linux 用 XDG_RUNTIME_DIR（缺省回退 /tmp/runtime-uid）。"""
    import sys as _sys
    monkeypatch.setattr(_sys, "platform", "linux")
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    p = app_module.single_instance_lock_path()
    assert p == tmp_path / "model-reservoir.lock"
    assert p.parent.is_dir()
    # Windows 无 os.getuid → mock 掉，三平台均可跑且 uid 确定
    monkeypatch.setattr(app_module.os, "getuid", lambda: 1000, raising=False)
    monkeypatch.delenv("XDG_RUNTIME_DIR")
    p2 = app_module.single_instance_lock_path()
    # Windows 的 Path 用反斜杠 stringify → 归一化后再断言
    s = str(p2).replace("\\", "/")
    assert s.startswith("/tmp/runtime-1000")
    assert s.endswith("model-reservoir.lock")


def test_image_to_argb():
    """SNI IconPixmap 载荷：ARGB 大端字节序。"""
    from PIL import Image
    img = Image.new("RGBA", (2, 1), (0, 0, 0, 0))
    img.putpixel((0, 0), (255, 0, 0, 255))  # 纯红不透明
    w, h, data = app_module.image_to_argb(img)
    assert (w, h) == (2, 1)
    assert data[0:4] == bytes((255, 255, 0, 0))   # A=255 R=255 G=0 B=0
    assert data[4:8] == bytes((0, 0, 0, 0))        # 透明像素全 0


def test_activate_endpoint():
    """/api/activate：第二实例唤起已有实例窗口（无窗口环境返回 ok=False，端点恒 200）。"""
    from fastapi.testclient import TestClient
    client = TestClient(app_module.app)
    r = client.post("/api/activate")
    assert r.status_code == 200
    assert "ok" in r.json()


def test_usage_all_days(monkeypatch, tmp_path):
    """/api/usage?days=0 = "全部"：不截断、不被钳到 1..30；days>30 仍钳到 30。"""
    import time as _time
    f = tmp_path / "usage.jsonl"
    old = _time.time() - 90 * 86400   # 90 天前的记录（旧逻辑30天会被清理/查询截掉）
    recent = _time.time() - 3600
    f.write_text(
        '{"ts": %d, "pt": 10, "ct": 20, "model": "m", "provider": "p"}\n' % old +
        '{"ts": %d, "pt": 1, "ct": 2, "model": "m", "provider": "p"}\n' % recent,
        encoding="utf-8")
    monkeypatch.setattr(app_module, "USAGE_FILE", f)

    # 底层: days<=0 不截断
    assert len(app_module._read_usage_sync(0)) == 2
    assert len(app_module._read_usage_sync(1)) == 1
    # cleanup: 90 天记录在 10 年保留期内 → 不删
    assert app_module._cleanup_usage_sync() == 0
    assert f.exists() and len(f.read_text(encoding="utf-8").splitlines()) == 2

    # 端点: days=0 原样返回全量
    from fastapi.testclient import TestClient
    client = TestClient(app_module.app)
    headers = {"Authorization": "Bearer " + app_module.LOCAL_API_KEY}
    r = client.get("/api/usage?days=0", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["days"] == 0
    assert body["total"]["requests"] == 2
    assert body["total"]["pt"] == 11
    # days>MAX 钳到 30（"近30天"语义不变）
    r2 = client.get("/api/usage?days=999", headers=headers)
    assert r2.json()["days"] == 30

def test_ensure_gtk_im_module(monkeypatch):
    """缺 GTK_IM_MODULE 时按已装模块补齐（中文输入根因修复）；已设则不覆盖。"""
    # 该函数 Linux-only（sys.platform 守卫）；CI 有 mac/win runner，mock 平台
    monkeypatch.setattr(app_module.sys, "platform", "linux")
    # 未设置 + fcitx 模块存在 -> 补 fcitx
    env = {}
    assert app_module.ensure_gtk_im_module(env, exists=lambda p: p.endswith("im-fcitx5.so")) is True
    assert env["GTK_IM_MODULE"] == "fcitx"
    # 只有 ibus -> 补 ibus
    env = {}
    assert app_module.ensure_gtk_im_module(env, exists=lambda p: p.endswith("im-ibus.so")) is True
    assert env["GTK_IM_MODULE"] == "ibus"
    # 什么模块都没有 -> 不瞎设
    env = {}
    assert app_module.ensure_gtk_im_module(env, exists=lambda p: False) is False
    assert "GTK_IM_MODULE" not in env
    # 已设 -> 不覆盖
    env = {"GTK_IM_MODULE": "ibus"}
    assert app_module.ensure_gtk_im_module(env, exists=lambda p: p.endswith(".so")) is False
    assert env["GTK_IM_MODULE"] == "ibus"


def test_ensure_gtk_im_module_file(monkeypatch):
    """打包版根因：PyInstaller 把 GTK_PATH 等指向包内且包里无 immodules.cache，
    必须补 GTK_IM_MODULE_FILE 指向系统缓存，否则 GTK 加载不到任何 IM 模块。"""
    monkeypatch.setattr(app_module.sys, "platform", "linux")
    cache = "/usr/lib/gtk-3.0/3.0.0/immodules.cache"
    # 缓存存在 -> 补 GTK_IM_MODULE_FILE（即使 GTK_IM_MODULE 已设，两变量独立补齐）
    env = {"GTK_IM_MODULE": "fcitx"}
    assert app_module.ensure_gtk_im_module(env, exists=lambda p: p == cache) is False
    assert env["GTK_IM_MODULE_FILE"] == cache
    # 两变量都缺 -> 一次补齐
    env = {}
    def exists(p):
        return p.endswith("im-fcitx5.so") or p == cache
    assert app_module.ensure_gtk_im_module(env, exists=exists) is True
    assert env["GTK_IM_MODULE"] == "fcitx"
    assert env["GTK_IM_MODULE_FILE"] == cache
    # 模块在但缓存文件不在（无 GTK 缓存的机器）-> 补 MODULE 不补 FILE
    env = {}
    assert app_module.ensure_gtk_im_module(env, exists=lambda p: p.endswith(".so")) is True
    assert env["GTK_IM_MODULE"] == "fcitx"
    assert "GTK_IM_MODULE_FILE" not in env
    # 彻底什么都没有 -> 不瞎设
    env = {}
    assert app_module.ensure_gtk_im_module(env, exists=lambda p: False) is False
    assert "GTK_IM_MODULE" not in env and "GTK_IM_MODULE_FILE" not in env
    # 已设不覆盖
    env = {"GTK_IM_MODULE_FILE": "/custom/immodules.cache"}
    app_module.ensure_gtk_im_module(env, exists=lambda p: True)
    assert env["GTK_IM_MODULE_FILE"] == "/custom/immodules.cache"


def test_call_log_no_100_cap():
    """调用记录不再 100 条截断（1 万条兜底），且每条带 ts 供相对时间显示。"""
    assert app_module.CALL_LOG_MAX >= 10000
    assert app_module.call_log.maxlen == app_module.CALL_LOG_MAX
    # ts 由 append 点写入：每个 time 行的下一行必须紧跟 ts 行（防回归）
    import inspect
    lines = inspect.getsource(app_module).splitlines()
    time_idx = [i for i, l in enumerate(lines) if '"time": time.strftime("%H:%M:%S"),' in l]
    assert len(time_idx) >= 9
    for i in time_idx:
        assert i + 1 < len(lines) and '"ts": time.time()' in lines[i + 1], f"call_log append 缺 ts: line {i}"


def test_infer_modality_rules():
    """模态能力自动辨别：七类规则 + 显式覆盖 + 兜底。"""
    im = app_module.infer_modality
    # 默认纯文本
    assert im("deepseek-v4-flash") == "text"
    # 向量模型防带偏（不吃 gemini/embedding 命名的生成/全模态规则）
    assert im("google/gemini-embedding-001") == "text"
    assert im("text-embedding-3-small") == "text"
    # 图像生成
    assert im("dall-e-3") == "image_gen"
    assert im("black-forest-labs/FLUX.1-schnell") == "image_gen"
    assert im("stabilityai/stable-diffusion-xl-base-1.0") == "image_gen"
    # 视频生成
    assert im("sora-2") == "video_gen"
    assert im("kling-v1.6") == "video_gen"
    # 音频生成
    assert im("gpt-4o-mini-tts") == "audio_gen"
    assert im("CosyVoice2-0.5B") == "audio_gen"
    # 音频理解
    assert im("whisper-large-v3") == "audio_in"
    assert im("SenseVoiceSmall") == "audio_in"
    # 图像理解
    assert im("Qwen/Qwen3-VL-8B-Instruct") == "vision"
    assert im("meta/llama-3.2-11b-vision-instruct") == "vision"
    assert im("microsoft/phi-3-vision-128k-instruct") == "vision"
    # 全模态
    assert im("nvidia/nemotron-3-nano-omni-30b-a3b-reasoning") == "omni"
    assert im("gpt-4o") == "omni"
    assert im("google/gemini-2.5-flash") == "omni"
    # 生成规则先于全模态（tts 不是 omni）
    assert im("gpt-4o-mini-tts") != "omni"
    # gpt-4o-mini 只是图像理解，不是全模态
    assert im("gpt-4o-mini") == "vision"
    # 显式覆盖（models_meta.modalities）优先于一切规则
    monkeypatch_key = "my-legacy-model"
    app_module.MODEL_MODALITIES[monkeypatch_key] = "video_gen"
    try:
        assert im(monkeypatch_key) == "video_gen"
        # 非法覆盖值被忽略，回退自动判定
        app_module.MODEL_MODALITIES[monkeypatch_key] = "banana"
        assert im(monkeypatch_key) == "text"
    finally:
        del app_module.MODEL_MODALITIES[monkeypatch_key]
    # 合法类别集合
    for m in ("text", "vision", "audio_in", "image_gen", "audio_gen", "video_gen", "omni"):
        assert m in app_module.MODALITY_CATEGORIES


def test_v1_models_modality_field(monkeypatch):
    """/v1/models 每项带 modality 字段；路由组=router。"""
    # 测试环境 DATA_DIR 无 providers.json → providers 为空，注入假数据
    monkeypatch.setattr(app_module, "providers", [
        {"name": "P1", "models": ["deepseek-v4-flash", "Qwen/Qwen3-VL-8B-Instruct", "sora-2", "whisper-large-v3"],
         "base_url": "http://x", "api_key": "k", "disabled_models": []},
    ], raising=False)
    monkeypatch.setattr(app_module, "ROUTERS", {"myroute": ["deepseek-v4-flash"]}, raising=False)
    # 清缓存强制重建
    app_module._models_cache["data"] = None
    from fastapi.testclient import TestClient
    client = TestClient(app_module.app)
    headers = {"Authorization": "Bearer " + app_module.LOCAL_API_KEY}
    resp = client.get("/v1/models", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    by_id = {d["id"]: d for d in data}
    assert by_id["P1-deepseek-v4-flash"]["modality"] == "text"
    assert by_id["P1-Qwen/Qwen3-VL-8B-Instruct"]["modality"] == "vision"
    assert by_id["P1-sora-2"]["modality"] == "video_gen"
    assert by_id["P1-whisper-large-v3"]["modality"] == "audio_in"
    assert by_id["myroute"]["modality"] == "router"
    # 每项都必须有 modality 且值合法
    for d in data:
        assert d.get("modality") in app_module.MODALITY_CATEGORIES, d
    # 复位缓存，避免污染其他用例
    app_module._models_cache["data"] = None
