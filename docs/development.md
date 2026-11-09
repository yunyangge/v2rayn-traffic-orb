# 开发与排错

## 组件

- `src/TrafficOrb.swift`：AppKit 悬浮球、独立右键菜单、限额设置、非阻塞提醒。
- `src/Paths.swift`：运行目录、App 身份和端口。不要把构建机路径写入产品。
- `src/collector.py`：读取 Xray 本机指标、计算差值并持久化日用量。PyInstaller 打包后无需外部 Python。
- `src/LifecycleWatcher.swift`：观察 `2dust.v2rayN` 进程；登录后轻量驻留，不启动代理服务。
- `resources/`：只有公共页面和默认设置，不能加入个人配置。

v2rayN 默认配置位置由运行时 `Path.home()` 计算。支持 `metrics.listen` 和旧版 `metrics.tag` 对应入站端口两种格式。临时配置文件被删除或替换时，使用缓存的有效接口，并仅从当前用户正在运行的 v2rayN/Xray 进程发现回环监听端口。不会扫描其他本机服务；响应必须具有 Xray 指标结构。统计仅累加 `proxy*` 出口，`direct` 单独计算，避免入站/出站重复加总。

Xray 计数器重置或进程变化时重新基准；不能假定计数永远递增。跨午夜短采样间隔按时长拆分；长时间断采后没有足够信息推断各日真实分布。提醒按日期、限额和已达档位记忆，测试提醒不写入去重记录。

## 本地测试变量

- `TRAFFIC_ORB_HOME`：隔离本工具设置与日统计目录。
- `TRAFFIC_ORB_PORT`：本地页面端口，默认 18863。
- `TRAFFIC_ORB_CONFIG`：采集器使用的测试 Xray JSON 路径。

测试/CI 应设置这些变量并使用假统计服务，不连接真实 VPN，不运行生产安装器。安装器另支持 `TRAFFIC_ORB_INSTALL_DIR`、`TRAFFIC_ORB_AGENT_DIR` 和 `--dry-run`。

## 检查

```bash
python3 -m unittest discover -s tests -v
python3 scripts/privacy_check.py .
```

`TrafficOrb.app/Contents/MacOS/TrafficOrbCollector --diagnose` 只输出配置是否存在、统计是否开启等布尔值，不打印节点详情。

SDK 与 Swift 编译器必须匹配；如自动选择了更新 SDK，可通过 `SDKROOT` 指定已安装且匹配的 SDK。不要通过禁用证书检查解决网络错误。

## 发布边界

从干净源码构建。不要打包 `~/Library`、本机 v2rayN 目录、使用中的 App 数据或个人截图。源码和解包后的安装包分别扫描；第三方 Python 压缩归档也应展开检查。发布前检查 `git diff --cached` 和 SHA-256。

当前本地构建为 ad-hoc 签名；生产分发者可使用自己的 Developer ID 做签名与公证。仓库不保存签名证书或 GitHub 凭据。
