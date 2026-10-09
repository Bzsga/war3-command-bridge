# 组件与许可

本工具复用 [Bzsga/war3-command-bridge](https://github.com/Bzsga/war3-command-bridge) 的自建运行包装、协议与C#进程创建方，并使用本地自建WTG解析器。发行包包含本次编译的x86创建方，不包含Warcraft游戏、地图素材、KKWE、ydhost、JassHelper或w3x2lni二进制；这些依赖由使用者提供。

桌面界面使用PySide6/Qt。Qt DLL保持独立动态库；相应许可证与版权说明放入发行包licenses目录。PySide6/Qt官方许可信息：https://doc.qt.io/qtforpython-6/licenses.html 。使用者可按适用许可证替换这些动态库；源码与重新构建步骤随工具提供。

HTTP客户端使用httpx（BSD许可）；桌面打包使用PyInstaller的GPL许可及打包例外。工具不提供模型额度、模型API_KEY或任何账户凭据。

源码中的演示构造器从用户提供的独立模板生成新副本，演示地图未随通用分享包分发。已经验证的游戏条件仅见VALIDATION，不推定其他安装或地图已经验证。
