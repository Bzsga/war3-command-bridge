param([Parameter(Mandatory=$true)][string]$Zig)
$ErrorActionPreference='Stop'
$nativeScratch=Join-Path $PSScriptRoot '..\..\work\native-bootstrap'
New-Item -ItemType Directory -Force -Path $nativeScratch | Out-Null
& $Zig dlltool -m i386 -k -d "$PSScriptRoot\src\kernel32-bootstrap.def" -l "$nativeScratch\kernel32.lib"
if($LASTEXITCODE -ne 0){throw 'Import library build failed'}
& $Zig cc -target x86-windows-gnu -nostdlib -shared -Os -fno-stack-protector '-Wl,--entry,DllMain@12' "$PSScriptRoot\src\AutoStart.c" "$nativeScratch\kernel32.lib" -o "$PSScriptRoot\War3Video.dll"
if($LASTEXITCODE -ne 0){throw 'Bootstrap build failed'}
# Keep the existing packaged MIX intact; the manager embeds this raw DLL.
