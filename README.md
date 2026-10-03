# Model Gateway · 无限额度 AI 模型网关

聚合多个 LLM 提供商额度，对外提供 **OpenAI 兼容接口**，支持智能轮询、流式故障转移、无感容灾切换。

> 本仓库 fork 自 [zk-2025/model-gateway](https://github.com/zk-2025/model-gateway)（原作者已声明项目终止、转向收费版）。原仓库删除了全部源码，本 fork 从 git 历史恢复了完整源码，并做了 **Windows / macOS / Linux 三端兼容**改造。
>
> 许可证：**CC BY-NC 4.0**（署名 + 非商用），沿用原仓库。
> **2026-10-03 原作者（东野 / ywtc000）已书面授权**本 fork 随意二次开发并开源（微信原话："可以的，随便改吧"）；本仓库在授权范围内免费开源，原作者署名保留。

## 功能

- OpenAI 兼容：`/v1/models`、`/v1/chat/completions`（含 SSE 流式）
- 多提供商聚合：智能轮询 + 滑动窗口质量分 + 流式故障转移/熔断重置
- Web 控制台：提供商管理、模型管理、稳定性监控、调用日志、一键配置
- 单实例运行、开机自启、公告推送（三端各自原生实现）

## 三端运行（源码模式）

通用前置：Python 3.11+。

```bash
git clone https://github.com/chenshifanjian/model-gateway.git
cd model-gateway
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Linux（Arch / 任意发行版）

```bash
# ① 原生窗口模式（推荐桌面用法）
# 注意：uv 建的 venv 看不到 pacman 装的 gi/WebKit2，
# 必须用系统 Python 建带 system-site-packages 的环境：
python3 -m venv --system-site-packages .venv-gui
.venv-gui/bin/pip install -r requirements.txt
GATEWAY_DATA_DIR=dist .venv-gui/bin/python app.py   # 弹原生窗口

# ② 无头模式（服务器 / 命令行）
GATEWAY_HEADLESS=1 python app.py     # 打开 http://127.0.0.1:8000
```

系统依赖：`webkit2gtk-4.1` + `python-gobject`（Arch 默认已带，缺则 `sudo pacman -S webkit2gtk-4.1 python-gobject`）。

> **Linux 默认关闭系统托盘**：pystray 的 GTK 后端会和 pywebview 抢 GLib 主循环导致段错误。
> 需要托盘时：`GATEWAY_TRAY=1 PYSTRAY_BACKEND=xorg ... python app.py`（需 Xwayland + python-xlib）。
> 无托盘时**关闭窗口即退出**，不留后台进程。

开机自启：设置页开关会写入 `~/.config/autostart/model-gateway.desktop`（XDG 标准，GNOME/KDE 等均支持）。

### macOS

```bash
python app.py                        # WKWebView 原生窗口（pywebview 自带）
# 或无头：GATEWAY_HEADLESS=1 python app.py
```

开机自启：开关会安装 `~/Library/LaunchAgents/com.modelgateway.client.plist`（launchd）。
打包产物数据目录：`~/Library/Application Support/ModelGateway`（.app 不可写）。

### Windows

```powershell
python app.py
```

开机自启写注册表 `HKCU\...\Run`；在线热更新（.exe 替换）为 Windows 独有功能。

## 打包

```bash
# Linux / macOS
./scripts/build.sh

# Windows（PowerShell）
pyinstaller 网关客户端.spec
```

spec 文件按平台自动裁剪：Windows 打进 WebView2 安装器与 win32 托盘，macOS 额外产出 `ModelGateway.app`，Linux 使用 appindicator 托盘。

## 测试

```bash
python -m pytest tests/ -q    # 29 passed
```

## 平台适配说明

| 能力 | Windows | macOS | Linux |
|---|---|---|---|
| 单实例锁 | `msvcrt` | `fcntl` | `fcntl` |
| 杀旧实例 | `netstat`+`taskkill` | `lsof` | `ss` |
| 开机自启 | 注册表 | LaunchAgent | XDG autostart |
| GUI | WebView2 | WKWebView | WebKitGTK（缺依赖自动回退浏览器） |
| 数据目录 | exe 同目录 | Application Support | 运行目录（可用 `GATEWAY_DATA_DIR` 覆盖） |
| 在线热更新 | ✅ | 手动更新 | 手动更新 |

环境变量：`GATEWAY_HEADLESS=1`（无头）、`GATEWAY_NO_BROWSER=1`（不自动开浏览器）、`GATEWAY_DATA_DIR`（数据目录）、`GATEWAY_AUTO_KILL=1`（启动时杀旧实例，测试用）。
