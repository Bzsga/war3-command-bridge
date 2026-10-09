# 来源与依赖

命令桥部分提供自建包装源码、协议、演示与接入说明，不包含地图、游戏素材、依赖二进制、编译后的宿主、个人配置、长期记忆或凭据。

接收方提供合法可用的 Warcraft III、兼容 KKWE 组件、JASS编译链、w3x2lni、ydhost与本机.NET Framework x86编译器。原依赖许可证不因本包改变。

上游接口资料：[YDWE源码](https://github.com/actboy168/YDWE)、[War3自动测试参考](https://github.com/kingslayer15/wc3-ai-autotest)。接口、版本与行为以实际安装和本机验证为准。

阅读接入边界后再执行。源码和示例不授予地图写入、产品启动或外部发布权限。

## 视频增强与 MIX 管理器

`tools/war3-video` 为独立自建视频工具源码，`dist` 提供对应版本的自建管理器二进制（内嵌自建播放器与启动 DLL）。不包含游戏、用户地图、MP4、个人配置或缓存，不携带第三方解码库；媒体解码依赖用户的 Windows 环境。其验证范围见该目录 VALIDATION.md，不能代替命令桥或其他平台验证。
