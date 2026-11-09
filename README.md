# Traffic Orb for v2rayN

macOS 上的小型透明流量悬浮球：上传为橙色、下载为蓝色，显示今日代理用量，可设置每日限额并弹窗预警。随 v2rayN 启停，所有统计保存在本机。

## 三步安装

1. 安装并配置 [v2rayN](https://github.com/2dust/v2rayN)，使用 **Xray 核心**。在参数设置中打开“流量统计”和“实时速度”，重启服务。
2. 在 [Releases](https://github.com/yunyangge/v2rayn-traffic-orb/releases) 下载与你的 Mac 匹配的 ZIP，解压后双击 **`Install.command`**。
3. 打开 v2rayN，悬浮球随之出现。右键 → **设置每日限额**，默认 80 GB。

安装包包含独立采集器，接收者无需安装 Python、Homebrew 或开发工具。安装位置为 `~/Applications/TrafficOrb.app`，无需管理员密码。

**平台：macOS 13 及以上。** `arm64` 用于 Apple Silicon；`x86_64` 用于 Intel。当前发布提供的架构以 Release 附件为准。

安装包使用本地 ad-hoc 签名，**没有 Apple Developer ID 公证**。macOS 首次打开可能阻止未识别开发者的软件；确认来自本仓库、校验附件 SHA-256 后，可按系统提供的“仍要打开”流程操作。安装器不会关闭 Gatekeeper 或修改系统安全策略。

## 使用

- 拖动移动；双击打开详细统计；右键显示操作菜单。
- 默认每日 80 GB，可保存其他数值，重启后保留。
- 达到限额的 **80%、95%、100%** 时弹窗并响铃，每档每天一次。仅提醒，不自动断网。
- 当天用量为 **代理上传 + 下载**，直连单独列出，不计入该限额。
- 每天按 Mac 本地时间 00:00 开始新一天；历史记录保留。1 GB = 1,000,000,000 字节。
- Option + 单击或右键“测试限额提醒”可预览弹窗，不改变实际用量。
- 退出 v2rayN 进程会退出悬浮球与采集器；仅关闭 v2rayN 窗口不会停止进程。
- 如果手动退出悬浮球，本次 v2rayN 会话不会强制重开；下次重启 v2rayN 会恢复。

**统计起点**：首次运行本工具。之前的流量无法补回。采集器停机期间不能精确恢复跨日用量；Xray 重启前未被采样的最后一小段流量也可能缺失。此统计采用 Xray 口径，不等同于运营商账单或含协议开销的网卡统计。

## 数据与隐私

发布包不包含任何节点地址、UUID、密码、订阅链接、VPN 配置、访问日志或个人历史用量。安装器也不会配置节点或改动路由。

运行时仅从当前用户的 v2rayN 配置中定位 **本机 Xray 统计端口**，请求 `/debug/vars`，提取出口字节计数。不会把节点设置复制进自己的数据文件，也不会上传统计。HTTP 页面只监听 `127.0.0.1:18863`，拒绝非本机 Host。

- 配置：`~/Library/Application Support/TrafficOrb/settings.json`
- 日统计：`~/Library/Application Support/TrafficOrb/data/usage.json`
- 启停监听：`~/Library/LaunchAgents/app.trafficorb.lifecycle.plist`

仅支持常见 v2rayN 的 Xray 配置/统计格式。切换到 sing-box 时可能显示等待，不代表零流量；自定义数据目录请参见 [开发与排错](docs/development.md)。Traffic Orb 不隶属于 v2rayN 项目。

## 内置 Codex skill

需要让 Codex 协助安装、检查连接或调整限额时，双击 **`Install-Skill.command`**，再重启 Codex/开启新会话。可输入：

> 使用 $traffic-orb 检查我的悬浮球连接，并把每日限额改为 100 GB。

skill 是可选的，不影响 App 使用；它不会自动发布日志或更改 VPN 节点。源文件在 [`skills/traffic-orb`](skills/traffic-orb)。

## 卸载 / 升级

双击 `Uninstall.command`：移除启停监听、停止本工具，把 App 移到废纸篓。**不删除统计和配置**，也不退出 v2rayN。升级重新运行 `Install.command`；已有 App 会保存为 `.previous`，已有数据保留。

## 从源码构建

需要 macOS、匹配的 Xcode Command Line Tools SDK 和 Python 3.9+（只在构建机需要）：

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-build.txt
BUILD_PYTHON="$PWD/.venv/bin/python" bash scripts/build.sh
```

输出在 `dist/`，包含 ZIP 与 SHA-256。CI 可构建 Apple Silicon/Intel 两种架构。详见 [开发与排错](docs/development.md)。

本项目代码采用 MIT 许可；打包的第三方运行时保留各自许可，参见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
