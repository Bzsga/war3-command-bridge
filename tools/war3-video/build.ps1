$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$framework = 'C:\Windows\Microsoft.NET\Framework64\v4.0.30319'
& "$framework\csc.exe" /nologo /target:winexe /platform:anycpu "/out:$taskRoot\War3Video.exe" "/r:$framework\WPF\PresentationFramework.dll" "/r:$framework\WPF\PresentationCore.dll" "/r:$framework\WPF\WindowsBase.dll" "/r:$framework\System.Xaml.dll" "/r:$framework\System.Windows.Forms.dll" "/r:$framework\System.Drawing.dll" "$taskRoot\src\VideoCompanion.cs" "$taskRoot\src\MixPackage.cs" "$taskRoot\src\AppVersion.cs"
if ($LASTEXITCODE -ne 0) { throw 'Compile failed' }

