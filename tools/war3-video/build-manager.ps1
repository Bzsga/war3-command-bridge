$ErrorActionPreference='Stop'
$framework='C:\Windows\Microsoft.NET\Framework64\v4.0.30319'
$guiResources=@('action.txt','call.txt','define.txt','War3VideoGUI.j','War3VideoGUI.cfg') | ForEach-Object {"/resource:$PSScriptRoot\kkwe-gui\$_,gui.$_"}
& "$framework\csc.exe" /nologo /target:winexe /platform:anycpu "/out:$PSScriptRoot\War3MixManager.exe" "/r:$framework\System.Windows.Forms.dll" "/r:$framework\System.Drawing.dll" "/resource:$PSScriptRoot\War3Video.dll,bootstrap" "/resource:$PSScriptRoot\War3Video.exe,player" "/resource:$PSScriptRoot\启用魔兽本地文件读取.reg,local-files-registry" @guiResources "$PSScriptRoot\src\MixManager.cs" "$PSScriptRoot\src\MixPackage.cs" "$PSScriptRoot\src\GuiInstaller.cs" "$PSScriptRoot\src\AppVersion.cs" "$PSScriptRoot\src\QuickCreator.cs"
if($LASTEXITCODE -ne 0){throw 'Manager build failed'}
