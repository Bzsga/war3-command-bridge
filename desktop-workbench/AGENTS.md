# War3 地图测试工作台

源码入口 `main.py`；`workbench/` 为桌面、适配和测试逻辑，`vendor/runtime/` 为已有桥的运行组件。项目事实和验证结果见 `docs/VALIDATION.md`。

开发：`python -m pip install -r requirements-dev.txt`，`python -m pytest tests -q`，`python main.py`。交付：`python build_release.py --method pyinstaller`；pyside6-deploy入口保留但须有可用C编译器。

正式地图只读；测试生成物放入用户选定项目的独立目录。地图测试只通过所属游戏/host创建方关闭，不结束用户已有编辑器或其他会话。AI只输出声明式命令映射和用例，不接受任意Shell/代码执行。密钥仅存Windows DPAPI，分享包不含密钥和会话。
