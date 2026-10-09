# War3 视频增强与 MIX 管理器 v1.0.0

作者：半盏丶时光 · 由 GPT-6 制作 · QQ：1076755135。

[下载便携管理器 v1.0.0](dist/War3MixManager-1.0.0.zip?raw=true) · [工程经验](../../docs/war3-video-mix-lessons.md) · [更新记录](CHANGELOG.md) · [验证范围](VALIDATION.md)

## 作者使用

解压后运行 War3MixManager.exe。新建 MIX 自带启动器和播放器，导入 MP4（含音轨）并保存，再把 MIX 包分发给玩家。编辑器部分选择 KKWE/YDWE 安装目录，确认类型后“安装触发器动作”，重启后在“视频播放”分类填写包内文件名。“卸载触发器动作”只移除视频模块，保留其他配置、地图、MIX 与视频。

KKWE 注册 config.user，YDWE 注册 config。支持 bin、jass、share/mpq/config 布局；不支持的布局拒绝安装。重复安装/卸载安全，文件写入失败回滚。遇到权限拒绝可用管理员身份运行。

## 玩家使用

只需把作者分发的 MIX 包放到实际使用的魔兽根目录，无需使用管理器。未安装视频包时跳过视频表现。更新 MIX 后需重启魔兽，运行中的播放器不会自动换版本。

画面额外覆盖在魔兽窗口上，视频音量不受游戏内声音设置影响。视频表现不回写同步游戏状态；地图作者仍须在同步流程调用动作，不能依赖本地视频完成决定奖励或剧情结算。混装联机尚未实测。

## 当前功能与限制

- 播放给所有玩家/指定玩家，停止指定玩家/所有玩家；音量 0–100%，速率 0.25–4，自动读取时长并播放内置音轨。
- 玩家只分发一个 MIX，运行时按需创建播放器和 MP4 缓存。
- 游戏进程、请求、播放器、日志和窗口分别隔离；游戏退出后停止音频。
- 编辑器加载 MIX 时不会启用启动器；没有隐式全局 ESC 跳过，停止由地图动作控制。
- 导入导出不转码。建议 H.264/YUV420P + AAC MP4，具体解码依赖 Windows 媒体栈。
- 本机实测基于 Windows / War3 1.27a / 窗口化。YDWE 安装流程仅有布局夹具验证。独占全屏、KK 对战平台、Reforged、跨机器及混装未验证。

## 从源码构建

需要 Windows .NET Framework 4.x 与支持 x86-windows-gnu 的 Zig。版本唯一入口是 src/AppVersion.cs。

```powershell
.\build.ps1
.\build-autostart.ps1 -Zig C:\tools\zig\zig.exe
.\build-manager.ps1
```

先编译播放器和原生 DLL，再编译内嵌它们和触发器资源的管理器。原生构建只输出 DLL 模板，不会覆盖已封装 MIX。通过管理器保存或 --refresh 更新旧包，保留视频。

```text
War3MixManager.exe --pack output.mix movie.mp4
War3MixManager.exe --refresh input.mix output.mix
War3MixManager.exe --import input.mix output.mix movie.mp4
War3MixManager.exe --remove input.mix output.mix movie.mp4
War3MixManager.exe --export input.mix new-directory
War3MixManager.exe --list input.mix list.txt
War3MixManager.exe --install-gui editor-directory KKWE
War3MixManager.exe --uninstall-gui editor-directory YDWE
```

管理器是 Windows GUI 程序，脚本调用需等待进程结束并检查退出码。目录型注入与 GUI 安装不保存地图、不启动或关闭编辑器。

仓库不包含游戏、用户地图、视频、缓存或第三方解码库。MIX 结构、IAT 路由及证据边界见工程经验。
