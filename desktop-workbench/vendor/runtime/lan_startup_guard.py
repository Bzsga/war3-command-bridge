"""Serialize local LAN startup; never terminate or operate another test.

Hold the lease from preflight through the matching ready handshake. Every project
using this game installation must reuse the same WBTestBridge lock path. Running
games/hosts still block after the lease is released. Remote LAN rooms are outside
this local process check.
"""
from contextlib import contextmanager
import os
import json
import msvcrt
from pathlib import Path
import subprocess


def local_products():
    command="""[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new();
Get-CimInstance Win32_Process -Filter "Name = 'war3.exe' OR Name = 'Warcraft III.exe' OR Name = 'ydhost.exe'" |
ForEach-Object { [PSCustomObject]@{name=$_.Name;pid=$_.ProcessId;parent=$_.ParentProcessId;path=$_.ExecutablePath;created=$_.CreationDate.ToUniversalTime().ToString('o')} } |
ConvertTo-Json -Compress"""
    result=subprocess.run([str(Path(os.environ.get('WINDIR',r'C:\Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'),'-NoProfile','-Command',command],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:raise RuntimeError('Cannot inspect competing LAN tests: '+result.stderr.decode('utf8',errors='replace'))
    text=result.stdout.decode('utf-8-sig').strip()
    if not text:return []
    value=json.loads(text)
    return value if isinstance(value,list) else [value]


def require_no_products(products):
    if products:
        raise RuntimeError('LAN startup blocked by another game/host; keep it untouched and retry after its owner finishes. Identities: '+json.dumps(products,ensure_ascii=False))


@contextmanager
def startup_lease(game_root):
    folder=Path(game_root)/'WBTestBridge';folder.mkdir(exist_ok=True)
    path=folder/'lan-startup.lock'
    with path.open('a+b') as handle:
        if handle.seek(0,2)==0:
            handle.write(b'0');handle.flush()
        handle.seek(0)
        try:msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
        except OSError as error:
            raise RuntimeError('Another LAN startup holds this installation lease; no product started') from error
        try:yield
        finally:
            handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
