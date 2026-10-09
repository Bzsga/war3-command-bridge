# 来源与依赖

命令桥部分提供自建包装源码、协议、演示与接入说明，不包含地图、游戏素材、依赖二进制、编译后的宿主、个人配置、长期记忆或凭据。

接收方提供合法可用的 Warcraft III、兼容 KKWE 组件、JASS编译链、w3x2lni、ydhost与本机.NET Framework x86编译器。原依赖许可证不因本包改变。

上游接口资料：[YDWE源码](https://github.com/actboy168/YDWE)、[War3自动测试参考](https://github.com/kingslayer15/wc3-ai-autotest)。接口、版本与行为以实际安装和本机验证为准。

阅读接入边界后再执行。源码和示例不授予地图写入、产品启动或外部发布权限。

## 视频增强与 MIX 管理器

视频工具已迁移至独立仓库 https://github.com/Bzsga/war3-video-mix 。命令桥当前版本不再携带视频工具源码或发行包，保留工程经验和迁移入口。

## 桌面工作台子项目

`desktop-workbench/`保存工作台源码和自建宿主源码；Windows发行包在独立Release，包含本次编译的宿主和动态Qt/Python运行库。上述命令桥源码包边界不扩大为桌面附件不含运行库；桌面组件许可见子项目NOTICE.md及docs/licenses。游戏与KKWE组件仍由使用者提供。
