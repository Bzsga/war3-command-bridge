"""Read-only Windows desktop prerequisite for loader-driven LAN auto entry.

Never switches desktops, focuses windows, sends keys, or launches a product.
The map timer bridge can run in a normal background window; booting through
the loader's menu navigation is a separate prerequisite.
"""
import ctypes
from ctypes import wintypes


def probe():
    user=ctypes.WinDLL('user32',use_last_error=True)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    user.OpenInputDesktop.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    user.OpenInputDesktop.restype=wintypes.HANDLE
    user.CloseDesktop.argtypes=[wintypes.HANDLE]
    user.GetUserObjectInformationW.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD)]
    result={'input_desktop_accessible':False,'input_desktop':None,'errors':[]}
    handle=user.OpenInputDesktop(0,False,0x0101)
    if handle:
        result['input_desktop_accessible']=True
        try:
            name=ctypes.create_unicode_buffer(256);needed=wintypes.DWORD()
            if user.GetUserObjectInformationW(handle,2,name,ctypes.sizeof(name),ctypes.byref(needed)):
                result['input_desktop']=name.value
            else:result['errors'].append({'operation':'desktop_name','code':ctypes.get_last_error()})
        finally:user.CloseDesktop(handle)
    else:result['errors'].append({'operation':'open_input_desktop','code':ctypes.get_last_error()})
    user.GetForegroundWindow.restype=wintypes.HWND
    user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
    pid=wintypes.DWORD();window=user.GetForegroundWindow()
    if window:user.GetWindowThreadProcessId(window,ctypes.byref(pid))
    result['foreground_pid']=pid.value;result['foreground_image']=None
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    process=kernel.OpenProcess(0x1000,False,pid.value) if pid.value else None
    if process:
        try:
            name=ctypes.create_unicode_buffer(32768);size=wintypes.DWORD(len(name))
            if kernel.QueryFullProcessImageNameW(process,0,name,ctypes.byref(size)):
                result['foreground_image']=name.value.rsplit('\\',1)[-1]
        finally:kernel.CloseHandle(process)
    result['scope']='Read-only startup prerequisite; no background/locked game behavior proof'
    return result


def require_lan_desktop(state):
    if not state['input_desktop_accessible']:
        raise RuntimeError('LAN startup requires an accessible interactive desktop; unlock/reconnect before retrying')
    if state['input_desktop'] is None or state['input_desktop'].lower()!='default':
        raise RuntimeError('LAN startup input desktop is not Default: '+str(state['input_desktop']))
    if (state.get('foreground_image') or '').lower() in ('lockapp.exe','logonui.exe'):
        raise RuntimeError('LAN startup foreground is the lock/sign-in screen; unlock before retrying')


if __name__=='__main__':
    import json
    print(json.dumps(probe(),ensure_ascii=False,indent=2))
