# Warcraft III 命令桥：快速实机测试经验与源码

给地图作者与AI助手：先读 **AI_HANDOFF.md**，不要直接运行项目示例。此包是可配置源码起点，不承诺在新环境开箱即用。

## 为什么采用命令桥

通过受限的JSON命令，让地图计时器在游戏线程调用正式玩法入口，再读取实际状态进行断言。适合战斗结算、奖励、交易、进化继承与重复操作回归，减少重复启动、等待后期内容和逐步鼠标操作。画面、真实点击命中、音效和多人同步仍分别验证。

原环境中一次单机启动完成自然首战、领奖、营地购买及预置进化继承：前置15项、批次28项检查通过，批次约31秒（不含构建与载图），测试后自动关闭所属游戏。普通窗口失焦的LAN首战另有独立证据。新批次两次LAN自动入房超时，尚未定位；不承诺每次启动稳定，也不宣称跨机器开箱即用。

详细方法见 [LESSONS](LESSONS.md)，结果和限制见 [VALIDATION](VALIDATION.md)，接入步骤见 [AI_HANDOFF](AI_HANDOFF.md)。

## 内容

- runtime：通用单人演示桥、JSON文件协议、KKWE启动/关闭创建方、LAN配置、只读后台采样；辅助宿主从C#源码本地编译。
- reference/project_adapter：杖剑数码正式逻辑接入样例，展示正常初始化、观测、UI→同步接收器和自动收尾。其字段、按钮编号、编译入口仅属于原项目，必须改成目标项目自己的定义。
- LESSONS：成功条件、LAN大地图问题和失败经验。
- VALIDATION：已经验证的范围与迁移包自身检查范围。
- NOTICE：来源、依赖与不包含的内容。

## 配置与演示

仅支持Windows、Python 3.10+及已验证的War3 1.27a / KKWE组件布局；其他版本先诊断，不通过删除门禁强行运行。将 runtime/config.example.json 复制为 runtime/config.json，填实际KKWE安装根、游戏根和自有演示地图模板。安装根应同时包含bin、plugin、share；tools可空，项目已有门禁仍必须执行。

file_view默认native。只有独立确认客户端使用本包描述的大小兼容hook、且大图对照复现后才改成kkwe_8m；插件特征不匹配会拒绝，不修改客户端DLL。不要为让doctor通过静默改变Allow Local Files等设置。

```powershell
python -X utf8 -B runtime/war3_bridge.py doctor
python -X utf8 -B runtime/war3_bridge.py build-demo --i-confirm-map-write
python -X utf8 -B runtime/war3_bridge.py launch --mode lan --i-confirm-map-write --i-confirm-game-launch
python -X utf8 -B runtime/war3_bridge.py run --require-background
```

只有用户明确允许地图副本写入和游戏启动后才加确认标志。build-demo会替换模板运行脚本，故模板必须是明确授权的独立演示模板，绝不把朋友的正式项目地图当作演示模板。原模板不覆盖，输出和会话各有新编号。

run默认在finally关闭本次游戏和host，成功或失败都执行；只有明确要求保留观看时使用--keep-open。单条request用于交互式会话，整批结束后执行shutdown。不得按进程名批量终止，不关闭编辑器或他人游戏。

背景测试需由使用者手工切到其他程序；本包只采样窗口状态，不替人操作UI。最小化、锁屏、无桌面和多人各自验证。若只需检查包自身源码，运行 `python -X utf8 -B check_kit.py`，不会构建地图或启动游戏。

项目接入及权限细节见AI_HANDOFF。跨机器后重新建立本机证据，不能沿用原项目的成功数字。

## v2：有限批次与共享技能

`skills/war3-testing/` 包含共享技能、标准库运行器和场景契约；可按既有安装方式放入用户技能目录，已有版本请比较合并。技能链接的coding-discipline、kkwe与kkwe-tooling属于接收方既有领域技能，未随包复制；缺失时先依据项目授权、构建门禁与本包AI_HANDOFF完成适配，不能把缺失当作跳过权限的理由。

运行器只接入已授权启动的会话，不构建地图或启动游戏。参考 `reference/project_adapter/batch_adapter.py` 的三场景实现，重写自己的固定准备、观测、正式操作及断言；项目控件和阶段不能直接复用。调用方式见技能references/bridge-batches.md。批后默认关闭所属游戏/host；断言、握手或清理失败保留报告。选卡→确认等两步操作必须等待真实可用状态，不能只相信即时执行的mock。
