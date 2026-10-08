# 接入自己的地图

## 分层

| 层 | 责任 |
|---|---|
| 地图业务 | 正式初始化、战斗、资源、阶段与同步处理 |
| 地图桥 | 固定操作入口、只读状态和场景准备 |
| 会话传输 | 身份校验、文件交换、超时和去重 |
| 测试适配器 | 触发操作、等待状态、判断业务结果 |
| 运行器 | 有限用例、失败记录、条件观测与所属进程关闭 |

将自己的操作映射到少量有意义的命令，例如选择、准备、购买或退出。命令参数使用稳定业务标识；不要传入任意脚本或未经验证的跨端句柄ID。

只暴露判断结果所需字段：阶段、玩家身份、资源、对象是否存在、业务序号、错误与计时进度。字段来自正式数据，不能另维护一套测试战斗/结算逻辑。

需要快速到达后期内容时采用固定、受限前置条件，保留正常初始化并注明预置范围。多人世界修改必须经过正式同步路径。

## 最小批次示例

`examples/demo_batch.py` 使用通用演示协议，检查攻击→真实奖励→重复请求→重置。它只接入已启动会话，不写地图或启动游戏。

```powershell
python -X utf8 -B skills/war3-testing/scripts/run_bridge_batch.py --adapter examples/demo_batch.py --session <session.json> --cases attack_reward --out <新报告目录>
```

把示例中的操作和断言改成自己的协议即可。适配器须提供 `BOUNDARY`、`CASES`、`open_context(session_path, report, persist)` 和 `shutdown(session_path)`。context可选提供 `finish()` 返回背景等条件证据。

运行器无论接入、用例还是条件检查失败，都调用适配器的所属进程清理。具体契约见技能的 [批次说明](../skills/war3-testing/references/bridge-batches.md)。
