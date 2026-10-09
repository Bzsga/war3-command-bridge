"""Own one ydhost process handle until its session stop file appears."""
import ctypes
import json
from pathlib import Path
import subprocess
import sys
import time

folder=Path(sys.argv[1]); executable=Path(sys.argv[2])
def save(name,value):
    target=folder/name;temp=target.with_suffix('.tmp')
    temp.write_text(json.dumps(value,indent=2),encoding='utf-8');temp.replace(target)

with (folder/'host.log').open('wb') as out, (folder/'host-errors.log').open('wb') as err:
    process=subprocess.Popen([str(executable)],cwd=folder,stdout=out,stderr=err,
                             creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.QueryFullProcessImageNameW.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_uint32)]
        buffer=ctypes.create_unicode_buffer(32768);size=ctypes.c_uint32(len(buffer))
        if not kernel.QueryFullProcessImageNameW(int(process._handle),0,buffer,ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        save('host-process.json',{'pid':process.pid,'actual_executable':buffer.value,
                                 'source':'QueryFullProcessImageNameW on retained Popen handle'})
        while process.poll() is None and not (folder/'host.stop').exists():time.sleep(.1)
    finally:
        if process.poll() is None:process.terminate()
        code=process.wait(timeout=10)
        save('host-exited.json',{'pid':process.pid,'exit_code':code,'owned_handle':True})
