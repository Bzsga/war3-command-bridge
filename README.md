# Warcraft III 命令桥

通过固定命令驱动真实游戏逻辑，读取状态并自动判断测试结果，减少重复启动、手动操作和等待。适用于 Warcraft III 地图的快速复现与行为回归。

## 两种使用方式

| 目标 | 入口 |
|---|---|
| 先确认本机通道可用 | 配置并运行随包单人演示 |
| 测试自己的地图 | 按[接入指南](docs/INTEGRATION.md)实现固定业务操作和观测字段 |

当前运行器针对 **Windows、Python 3.10+、War3 1.27a 与兼容 KKWE**。其他版本须另行适配；同一接口名称不代表运行行为一致。

## 快速开始

1. 将 `runtime/config.example.json` 复制为 `runtime/config.json`，填写自己的 KKWE、游戏和独立演示模板路径。
2. 运行源码检查与环境诊断。
3. 在已获地图副本写入、游戏启动授权后运行演示。

```powershell
python -X utf8 -B check_kit.py
python -X utf8 -B runtime/war3_bridge.py doctor
python -X utf8 -B runtime/war3_bridge.py build-demo --i-confirm-map-write
python -X utf8 -B runtime/war3_bridge.py launch --mode lan --i-confirm-map-write --i-confirm-game-launch
python -X utf8 -B runtime/war3_bridge.py run
```

演示模板须为 W3I v25、Player(0) 单真人的独立测试模板；演示会替换副本中的运行脚本，不能使用正式地图充当模板。`run` 成功或失败均关闭所属游戏和主机。临时保留观看才使用 `--keep-open`，结束后执行 `shutdown`。

`file_view` 默认 `native`。仅确认实际兼容插件与大图文件视图差异后选择 `kkwe_8m`；不要为了通过检查删除门禁或修改正式资源。

## 接入与查阅

- [接入自己的地图](docs/INTEGRATION.md)：业务边界、适配器与最小示例。
- [文件协议](docs/PROTOCOL.md)：会话身份、固定操作、去重与错误处理。
- [多人接入](docs/MULTIPLAYER.md)：实例隔离、发现端口和同步验证。
- [故障排查](docs/TROUBLESHOOTING.md)：按启动阶段定位失败。
- [验证范围](VALIDATION.md)：已经证明的能力与迁移后需要重测的部分。
- [视频增强与 MIX 管理器 v1.1.2](tools/war3-video/README.md)：源码、便携下载、编辑器触发器安装/卸载与指定玩家播放。
- [视频播放工程经验](docs/war3-video-mix-lessons.md)：MIX 分发、进程隔离、媒体生命周期与验证边界。
- [给 AI 助手](AI_HANDOFF.md)：推荐工作顺序。

`runtime` 提供单人演示及通用基础组件；`examples/demo_batch.py` 是可运行的批次适配示例；`skills/war3-testing` 可独立安装为技能。包内不含任何特定地图的控件编号、养成系统、关卡流程或构建入口。

固定窗口消息只操作已验证的所属 War3 窗口，无需 Computer Use、全局键鼠或坐标截图。后台行为、最小化、视听与真实鼠标命中分别验证。组件许可与不包含的内容见 [NOTICE.md](NOTICE.md)。
