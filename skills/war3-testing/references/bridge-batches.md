# 有限批次契约

运行器只接入已获授权启动的会话，不写地图或启动游戏。适配器是可信本地源码，外部JSON只能请求固定操作。

| 适配器成员 | 责任 |
|---|---|
| BOUNDARY | 正常流程、预置与未覆盖条件 |
| CASES | 有限用例名到函数的映射 |
| open_context(session_path, report, persist) | 校验会话并创建操作/观测上下文 |
| shutdown(session_path) | 通过原创建方关闭所属游戏与主机，返回真实回执 |
| context.finish()，可选 | 完成后台等条件观测，返回实际证据 |

```powershell
python -X utf8 -B scripts/run_bridge_batch.py --adapter <adapter.py> --session <session.json> --cases <用例名> --out <新目录>
```

相关用例可以有意共享状态。独立用例只有证明重置覆盖依赖后才复用局部重置，否则新建会话。准备阶段、正式操作、异步结算和重复边界各自验证；不以分发成功代替业务成功。

运行器记录business_passed、conditions_passed和cleanup_status。只有明确未启动且无相反痕迹，清理才标not_started；缺少启动文件本身不能跳过关闭。

本地查询保持只读，跨端不比较未经验证的句柄ID或本地发送计数。主机desync是独立失败条件。Lua数组、默认值和响应编码遵循实际协议；响应错误不等于业务未执行。

修改适配器后验证正常、失败和重复路径。源码检查不等于游戏运行；相同输入、组件与条件已有有效证据时复用，不重复无关矩阵。
