# Warcraft III 命令桥

给朋友的 AI 助手：先读 [AI_HANDOFF.md](AI_HANDOFF.md)。这是可配置的源码起点；换项目和机器后须建立自己的运行证据。

包内包含单人演示运行器、JSON 文件协议、原生进程创建方、固定窗口消息启动、后台采样、LAN 发现与互斥，以及单人/双人项目适配示例。共享技能位于 `skills/war3-testing`。不包含地图、游戏资产、依赖 DLL、编译后的宿主、凭据或个人记忆。

## 配置与最短演示

支持已验证的 Windows / Python 3.10+ / War3 1.27a 与对应 KKWE 布局。复制 `runtime/config.example.json` 为 `runtime/config.json`，填本机 KKWE 根、游戏根和独立演示模板。模板必须是授权的测试模板，W3I v25、Player(0) 单真人；不要把正式项目地图当演示模板。KKWE 根应包含 bin、plugin、share；tools 可空，项目已有门禁仍须执行。

```powershell
python -X utf8 -B check_kit.py
python -X utf8 -B runtime/war3_bridge.py doctor
python -X utf8 -B runtime/war3_bridge.py build-demo --i-confirm-map-write
python -X utf8 -B runtime/war3_bridge.py launch --mode lan --i-confirm-map-write --i-confirm-game-launch
python -X utf8 -B runtime/war3_bridge.py run --require-background
```

只有用户已允许地图副本写入与游戏启动后才添加确认标志。宿主从 C# 源码本机编译。run 成功或失败均关闭所属游戏和主机；只有明确要求留看才使用 `--keep-open`。单条 request 的交互会话结束后执行 shutdown。不关闭编辑器或他人游戏。

启动只向原生创建方验证过的 War3 窗口发送固定消息，不使用全局键鼠、坐标、截图或 Computer Use。最小化条件由独立采样证明；启动仍需要可交互桌面，不能据此宣称锁屏可启动。file_view 默认为 native，只有核实兼容插件并复现大图视图差异后才选 kkwe_8m。

## 项目接入与双客户端

`reference/project_adapter` 展示正式业务入口、只读快照、有限批次、同步请求、去重和及时收尾。其源码路径、控件编号、成长字段及构建工具属于原项目，必须按自己的工程改写。`multiplayer.py` 是两个真人、槽位0/1的参考启动与流程用例，要求 fresh session/IPC、已校验候选图和两项授权标志；它不自动制作你项目的测试图，也不证明四客户端。

通用演示只支持单人。多人本地快照不得创建或销毁世界句柄、推进随机源；从 Lua 调用固定 JASS 入口使用已核对的 jass.code。主机 desync 告警独立于可见状态断言。实测范围见 [VALIDATION.md](VALIDATION.md)，复用经验见 [LESSONS.md](LESSONS.md)。

## 可选视频播放经验

[War3 视频 MIX 分发与 LAN 测试经验](docs/war3-video-mix-lessons.md)记录单文件包、进程隔离、指定玩家播放与停止、音频生命周期和编辑器宿主过滤。该文档是独立视频项目的经验总结；本命令桥仓库未包含视频插件实现或播放器发行包。实机与夹具证据、未验证平台及保存卡住问题的复测边界均单独说明。
